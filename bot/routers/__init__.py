from io import BytesIO
from typing import Optional
from aiogram import Router, types, F
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from bot import fsm
from bot.api import BackendAPI
from config import ENV
from services.kie import GenerateRequests
from aiogram.utils.keyboard import InlineKeyboardBuilder

router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)



def start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_by_photo")
    kb.button(text="Помощь с промптом", callback_data="prompt_help")  # <–– новая
    kb.adjust(1, 1, 1)
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
    await state.set_state(fsm.BotState.waiting_for_text_description)


@router.message(fsm.BotState.waiting_for_text_description)
async def handle_text_description(message: types.Message, state: FSMContext):
    prompt = message.text.strip()

    if not prompt:
        await message.answer("Нужно текстовое описание. Введи пару фраз 🙏")
        return

    await message.answer(f"🎬 Запускаю генерацию по описанию:\n\n{prompt}")

    # Шагаем в наш БЭК: /bot/veo/generate/text
    try:
        resp = await backend.generate_text(chat_id=message.from_user.id, prompt=prompt)
        # ожидаем {"ok": True, "task_id": "..."}
        task_id = resp.get("task_id")
        if not task_id:
            raise RuntimeError("Backend не вернул task_id")
    except Exception as e:
        # сюда попадут сетевые/любые ошибки клиента
        await message.answer("❌ Техническая ошибка при старте генерации. Попробуй ещё раз позже.")
        # опционально: логировать e
        return

    # Сохраним контекст (если хочешь переиспользовать дальше)
    await state.update_data(last_task_id=task_id, last_prompt=prompt)

    # Сообщаем пользователю и выходим: дальше придёт пуш из колбэка
    await message.answer(
        "✅ Принял! Я пришлю тебе готовое видео здесь, как только генерация завершится.\n\n"
        f"ID задачи: `{task_id}`",
        parse_mode="Markdown"
    )
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
    await message.answer("🎬 Запускаю генерацию по фото…")

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
