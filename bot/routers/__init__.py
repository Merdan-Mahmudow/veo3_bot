from io import BytesIO
import logging
from typing import Optional
from aiogram import Router, types, F
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from bot import fsm
from bot.api import BackendAPI
from config import ENV
from services.kie import GenerateRequests
from aiogram.utils.keyboard import InlineKeyboardBuilder
from services.storage import YandexS3Storage

router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)
storage = YandexS3Storage()



def start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_photo")
    kb.button(text="💰 Пополнить баланс", callback_data="buy_coins")
    kb.button(text="Что умею?", callback_data="help")
    kb.button(text="Поддержка", url=f"https://t.me/{env.SUPPORT_USERNAME}")
    kb.adjust(1, 1)
    return kb.as_markup()

def prompt_options_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data="prompt_edit")
    kb.button(text="✅ Принять", callback_data="prompt_accept")
    kb.button(text="↻ Другой вариант", callback_data="prompt_other")
    kb.button(text="❌ Отклонить", callback_data="prompt_reject")
    kb.adjust(2)
    return kb.as_markup()

@router.message(Command("start"))
async def command_start(message: types.Message, state: FSMContext):
    

    # Проверяем наличие пользователя
    try:
        exists = await backend.check_user_exist(message.from_user.id)
    except Exception:
        await message.answer("Техническая ошибка соединения. Попробуй ещё раз позже.")
        return

    # Если нет — регаем
    if not exists:
        # Баннер
        await message.answer_photo(
            photo=types.URLInputFile(
                f"{env.yc_s3_endpoint_url}/veobot/photo_2025-08-12_00-07-56.jpg"),
            caption="Привет! Я генерирую для тебя лучшее видео по твоему запросу.\n\n"
        )

        await message.answer("Ты у нас впервые. Регистрирую…")
        nickname = (
            message.from_user.username
            or message.from_user.first_name
            or f"user_{message.from_user.id}"
        )
        try:
            res = await backend.register_user(message.from_user.id, nickname=nickname)
        except Exception:
            await message.answer("Техническая ошибка при регистрации. Напиши @softp04")
            return

        if not res.get("created", False) and res.get("reason") != "exists":
            await message.answer("Внутренняя ошибка регистрации. Напиши @softp04")
            return

    # Общая ветка после ensure user: получаем баланс и даём меню
    try:
        coins = await backend.get_coins(message.from_user.id)
    except Exception:
        coins = 0

    if not exists:
        text = (
            "Регистрация прошла успешно! Теперь давай сгенерируем видео!\n\n"
            f"У тебя {coins} генераций.\n\nВыбери способ генерации видео:"
        )
    else:
        text = (
            f"С возвращением!\n\nУ тебя {coins} генераций.\n\n"
            "Выбери способ генерации видео:"
        )

    sent_message: Optional[types.Message] = await message.answer(
        text,
        reply_markup=start_keyboard()
    )

    # Сохраняем id отправленного сообщения
    await state.update_data(start_message_id=sent_message.message_id)
    await state.set_state(fsm.BotState.start_message_id)


@router.callback_query(F.data == "generate_by_text")
async def callback_generate_by_text(callback: types.CallbackQuery, state: FSMContext):
    # аккуратно удалим предыдущее стартовое сообщение, если оно есть
    data = await state.get_data()
    start_message_id = data.get("start_message_id")
    chat_id = callback.message.chat.id

    if start_message_id:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=start_message_id)
        except Exception:
            pass

    await callback.answer()
    await callback.message.answer(
        "✍️ Введите описание своего видео для генерации.\n\n"
        "Если хотите оживить фото — нажмите /start и выберите генерацию по фото."
    )
    await state.clear()
    await state.update_data(mode="text")
    await state.set_state(fsm.BotState.waiting_for_text_description)


@router.message(fsm.BotState.waiting_for_text_description)
async def handle_text_description(message: types.Message, state: FSMContext):
    brief = (message.text or "").strip()
    if not brief:
        await message.answer("Опиши кратко сюжет будущего видео.")
        return

    # получаем промпт через бэкенд (первый вариант)
    try:
        suggestion = await backend.suggest_prompt(
            chat_id=str(message.chat.id),
            brief=brief,
            clarifications=None,
            attempt=1,
            previous_prompt=None,
            # aspect_ratio="16:9",
        )
    except Exception as e:
        logging.exception("Ошибка получения промпта: %s", e)
        await message.answer("Не удалось получить промпт. Попробуйте ещё раз.")
        return

    # сохраняем данные для последующих вариантов
    await state.update_data(
        prompt_brief=brief,
        prompt_last=suggestion,
        prompt_attempt=1,
        prompt_clarifications=[],
    )

    # показываем сгенерированный промпт и клавиатуру с 4 кнопками
    await message.answer(
        f"{suggestion}",
        reply_markup=prompt_options_kb(),  # см. ниже
    )
    await state.set_state(fsm.PromptAssistantState.reviewing)  # переходим в состояние выбора

@router.callback_query(F.data == "generate_by_photo")
async def callback_generate_by_photo(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_message_id = data.get("start_message_id")
    chat_id = callback.message.chat.id
    if start_message_id:
        try:
            await callback.bot.delete_message(chat_id=chat_id, message_id=start_message_id)
        except Exception:
            pass

    await callback.answer()
    await callback.message.answer(
        "📷 Пришли фото **с подписью** — текстом опиши, что нужно получить.\n\n"
        "Пример: отправь фото и подпиши «стиль неон/киберпанк, динамичный город, сумерки».",
        parse_mode="Markdown"
    )
    await state.clear()
    await state.update_data(mode="photo")
    await state.set_state(fsm.BotState.waiting_for_photo)

# ---------- Получаем фото (с подписью) ----------

@router.message(fsm.BotState.waiting_for_photo, F.photo)
async def handle_photo_with_caption(message: types.Message, state: FSMContext):
    prompt = (message.caption or "").strip()
    
    if not prompt:
        # нет подписи — попросим отдельный текст
        # сохраним file_id, чтобы повторно не просить фото
        tg_photo = message.photo[-1]
        await state.update_data(pending_photo_file_id=tg_photo.file_id)
        await message.answer("✍️ Напиши описание (подпись к фото).")
        await state.set_state(fsm.BotState.waiting_for_photo_caption)
        return

    await _start_generate_by_photo(message, state, prompt, photo_file_id=message.photo[-1].file_id)

# ---------- Если сначала пришло фото, потом текст (подпись отдельно) ----------

@router.message(fsm.BotState.waiting_for_photo_caption, F.text)
async def handle_photo_caption(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id = data.get("pending_photo_file_id")
    if not file_id:
        await message.answer("Не вижу фото. Пришли фото ещё раз, пожалуйста.")
        await state.set_state(fsm.BotState.waiting_for_photo)
        return

    prompt = message.text.strip()
    if not prompt:
        await message.answer("Нужно описание. Напиши пару фраз 🙏")
        return

    await _start_generate_by_photo(message, state, prompt, photo_file_id=file_id)

# ---------- Запуск генерации по фото (общая функция) ----------

async def _start_generate_by_photo(message: types.Message, state: FSMContext, prompt: str, photo_file_id: str):
    # качаем файл из TG во временный буфер
    try:
        file = await message.bot.get_file(photo_file_id)
        buf = BytesIO()
        await message.bot.download(file, destination=buf)
        buf.seek(0)
        # попытаемся достать расширение из пути на стороне Telegram CDN
        if file.file_path and "." in file.file_path:
            ext = "." + file.file_path.rsplit(".", 1)[-1].lower()
        else:
            ext = ".jpg"
    except Exception:
        await message.answer("❌ Не удалось загрузить фото из Telegram. Пришли ещё раз.")
        return

    # зовём backend
    try:
        print(prompt)
        res = await backend.generate_photo(
            chat_id=message.from_user.id,
            prompt=prompt,
            file_bytes=buf.getvalue(),
            filename=f"photo{ext}",
        )
        task_id = (res or {}).get("task_id")
        if not task_id:
            raise RuntimeError("backend did not return task_id")
    except Exception as e:
        # читаем сообщение об ошибке — возможно, «нет монет»
        msg = str(e).lower()
        if "coin" in msg or "монет" in msg or "insufficient" in msg:
            await message.answer("🥲 Недостаточно генераций. Пополни баланс и попробуй снова.")
            return
        await message.answer("❌ Техническая ошибка при старте генерации. Попробуй ещё раз.")
        return

    # успех: чистим состояние и даём подтверждение
    await state.clear()
    await message.answer(
        "✅ Принял! Как только видео будет готово — пришлю сюда ссылку.\n"
        f"ID задачи: `{task_id}`",
        parse_mode="Markdown",
    )

# ---------- Текстовая генерация: доработки об ошибках монет ----------

@router.message(fsm.BotState.waiting_for_text_description)
async def handle_text_description(message: types.Message, state: FSMContext):
    prompt = (message.text or "").strip()
    if not prompt:
        await message.answer("Нужно текстовое описание. Введи пару фраз 🙏")
        return

    await message.answer(f"🎬 Запускаю генерацию по описанию:\n\n{prompt}")
    try:
        res = await backend.generate_text(chat_id=message.from_user.id, prompt=prompt)
        task_id = (res or {}).get("task_id")
        if not task_id:
            raise RuntimeError("backend did not return task_id")
    except Exception as e:
        msg = str(e).lower()
        if "coin" in msg or "монет" in msg or "insufficient" in msg:
            await message.answer("🥲 Недостаточно генераций. Пополни баланс и попробуй снова.")
            return
        await message.answer("❌ Техническая ошибка при старте генерации. Попробуй ещё раз.")
        return

    await state.clear()
    await message.answer(
        "✅ Принял! Я пришлю готовое видео, как только всё сгенерируется.\n"
        f"ID задачи: `{task_id}`",
        parse_mode="Markdown",
    )

# ---------- Отмена сценария ----------

@router.message(Command("cancel"))
async def cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❎ Отменил. Можем начать заново: /start")

    
@router.message(Command("test"))
async def test_details(message: types.Message, command: CommandObject):
    args = command.args
    generate = GenerateRequests()
    if args is None:
        await message.answer(
            "Ошибка: не переданы аргументы"
        )
        return
    req = await generate.get_video_info(args.replace(" ", ""))
    print(req)


@router.callback_query(F.data == "prompt_help")
async def prompt_help_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.update_data(
        prompt_attempt=0,
        prompt_brief=None,
        prompt_last=None,
        prompt_clarifications=[],
    )
    await callback.message.answer(
        "Окей. Кратко опиши, какое видео ты хочешь получить: тема/сцена, настроение, стилистика.\n"
        "Например: «неоновый город ночью, дождь, киберпанк, динамичный ракурс»."
    )
    await state.set_state(fsm.PromptAssistantState.waiting_brief)



@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_accept")
async def prompt_accept(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt_text = data.get("prompt_last")
    if not prompt_text:
        await callback.answer("Нет промпта для принятия", show_alert=True)
        return

    mode = data.get("mode")  # 'text' или 'photo'
    await callback.answer("Промпт принят ✅")

    try:
        if mode == "photo":
            # Получаем URL (или id) ранее сохранённого изображения
            image_url = data.get("image_url")
            if not image_url:
                await callback.message.answer("Не удалось найти изображение для генерации.")
                await state.clear()
                return

            # Вызываем генерацию по фото, используя один и тот же image_url
            task = await backend.generate_photo(
                chat_id=str(callback.from_user.id),
                prompt=prompt_text,
                image_url=image_url,
                )

        else:
            # Генерация по тексту
            task = await backend.generate_text(
                chat_id=str(callback.from_user.id),
                prompt=prompt_text,
            )

        await callback.message.answer(
            "Генерация запущена! После завершения бот пришлёт результат."
        )

    except Exception as e:
        logging.exception("Ошибка запуска генерации: %s", e)
        await callback.message.answer("❌ Не удалось запустить генерацию.")
    finally:
        await state.clear()

@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_other")
async def prompt_other(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brief = data.get("prompt_brief")
    clar = data.get("prompt_clarifications", [])
    last = data.get("prompt_last")
    attempt = int(data.get("prompt_attempt", 1)) + 1

    try:
        suggestion = await backend.suggest_prompt(
            chat_id=str(callback.from_user.id),
            brief=brief,
            clarifications=clar,
            attempt=attempt,
            previous_prompt=last,
            # aspect_ratio="16:9",
        )
    except Exception as e:
        logging.exception("Ошибка получения нового варианта: %s", e)
        await callback.answer("Не удалось получить новый вариант")
        return

    await state.update_data(prompt_last=suggestion, prompt_attempt=attempt)
    await callback.message.edit_text(
        f"Вариант #{attempt}:\n\n{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await callback.answer("Новый вариант готов!")

@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_edit")
async def prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напишите, что нужно изменить/добавить:")
    await state.set_state(fsm.PromptAssistantState.editing)  # новое состояние для правок

@router.message(fsm.PromptAssistantState.editing)
async def prompt_receive_edit(message: types.Message, state: FSMContext):
    edit = (message.text or "").strip()
    if not edit:
        await message.answer("Напишите, какие правки внести.")
        return
    data = await state.get_data()
    brief = data.get("prompt_brief")
    clar = data.get("prompt_clarifications", [])
    clar.append(edit)
    attempt = int(data.get("prompt_attempt", 1)) + 1
    last = data.get("prompt_last")

    # запрашиваем промпт с учётом правок
    suggestion = await backend.suggest_prompt(
        chat_id=str(message.chat.id),
        brief=brief,
        clarifications=clar,
        attempt=attempt,
        previous_prompt=last,
        # aspect_ratio="16:9",
    )
    await state.update_data(prompt_clarifications=clar, prompt_last=suggestion, prompt_attempt=attempt)
    await message.answer(
        f"{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await state.set_state(fsm.PromptAssistantState.reviewing)

@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_reject")
async def prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Промпт отклонён")
    await callback.message.answer("Окей, вернёмся к главному меню.")



# --- Хэндлер выбора режима генерации по фото ---
@router.callback_query(F.data == "generate_photo")
async def start_photo_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await state.update_data(mode="photo")
    await callback.answer()
    await callback.message.answer("Пришли фотографию и короткое описание (в подписи), чтобы я смог подготовить промпт.")
    await state.set_state(fsm.PhotoState.waiting_photo)

@router.message(fsm.PhotoState.waiting_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Отправь изображение.")
        return

    photo_id = message.photo[-1].file_id
    # Скачиваем файл один раз
    file = await message.bot.get_file(photo_id)
    file_bytes = await message.bot.download_file(file.file_path)

    # Загружаем на S3 и получаем URL
    image_url = storage.save(file_bytes.getvalue(), extension=".jpg", prefix="prompt_inputs/")

    # Сохраняем URL в состоянии – пригодится при генерации видео
    await state.update_data(image_url=image_url, prompt_attempt=1, prompt_clarifications=[])

    # Просим GPT сгенерировать промпт, передав image_url
    suggestion = await backend.suggest_prompt(
        chat_id=str(message.chat.id),
        brief=message.caption or "",
        clarifications=None,
        attempt=1,
        previous_prompt=None,
        # aspect_ratio="16:9",
        image_url=image_url,
    )

    await state.update_data(prompt_last=suggestion)
    await message.answer(
        f"Предложенный промпт:\n\n{suggestion}",
        reply_markup=prompt_options_kb()
    )
    await state.set_state(fsm.PromptAssistantState.reviewing)

# --- Обработка кнопок в состоянии reviewing ---
@router.callback_query(fsm.PhotoState.reviewing, F.data == "prompt_accept")
async def photo_prompt_accept(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt_text = data.get("prompt_last")
    file_id = data.get("photo_file_id")
    if not prompt_text or not file_id:
        await callback.answer("Не хватает данных", show_alert=True)
        return

    await callback.answer("Запускаю генерацию видео 🎬")

    # скачиваем фото и отправляем в бэкенд
    try:
        # получаем байты файла через aiogram
        file = await callback.bot.get_file(file_id)
        file_bytes = await callback.bot.download_file(file.file_path)
        image_ext = ".jpg"
        task = await backend.generate_photo(
            chat_id=str(callback.from_user.id),
            prompt=prompt_text,
            image_bytes=file_bytes.getvalue(),
            image_ext=image_ext,
        )
        await callback.message.answer(f"Генерация запущена! ID задачи: {task['task_id']}")
    except Exception as e:
        logging.exception("Ошибка генерации по фото: %s", e)
        await callback.message.answer("Не удалось запустить генерацию.")
    finally:
        await state.clear()

@router.callback_query(fsm.PhotoState.reviewing, F.data == "prompt_other")
async def photo_prompt_other(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brief = data.get("prompt_brief", "")
    clar = data.get("prompt_clarifications", [])
    last = data.get("prompt_last")
    attempt = int(data.get("prompt_attempt", 1)) + 1

    suggestion = await backend.suggest_prompt(
        chat_id=str(callback.from_user.id),
        brief=brief,
        clarifications=clar,
        attempt=attempt,
        previous_prompt=last,
        # aspect_ratio="16:9",
    )
    await state.update_data(prompt_last=suggestion, prompt_attempt=attempt)
    await callback.message.edit_text(
        f"Вариант #{attempt}:\n\n{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await callback.answer("Другой вариант готов!")

@router.callback_query(fsm.PhotoState.reviewing, F.data == "prompt_edit")
async def photo_prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Опиши, что нужно изменить/добавить к запросу:")
    await state.set_state(fsm.PhotoState.editing)

@router.message(fsm.PhotoState.editing)
async def photo_prompt_receive_edit(message: types.Message, state: FSMContext):
    edit = (message.text or "").strip()
    if not edit:
        await message.answer("Напиши корректировку.")
        return
    data = await state.get_data()
    brief = data.get("prompt_brief", "")
    clar = data.get("prompt_clarifications", [])
    clar.append(edit)
    last = data.get("prompt_last")
    attempt = int(data.get("prompt_attempt", 1)) + 1

    suggestion = await backend.suggest_prompt(
        chat_id=str(message.chat.id),
        brief=brief,
        clarifications=clar,
        attempt=attempt,
        previous_prompt=last,
        # aspect_ratio="16:9",
    )
    await state.update_data(prompt_clarifications=clar, prompt_last=suggestion, prompt_attempt=attempt)
    await message.answer(
        f"Вариант #{attempt} (с учётом правок):\n\n{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await state.set_state(fsm.PhotoState.reviewing)

@router.callback_query(fsm.PhotoState.reviewing, F.data == "prompt_reject")
async def photo_prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("Понятно, вернёмся в главное меню.")
