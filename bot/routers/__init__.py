import asyncio
from contextlib import suppress
import json
import logging
from typing import Optional

from aiogram import Router, types, F
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import fsm
from bot.api import BackendAPI
from config import ENV, Settings
from services.redis import RedisClient
from services.storage import YandexS3Storage
from utils.progress import PROGRESS, show_progress
from aiogram.enums import ParseMode
from utils.referral import ReferralService


router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)
storage = YandexS3Storage()
redis = RedisClient()
settings = Settings()
referral_service = ReferralService()


# --- Клавиатуры ---

def start_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_photo")
    kb.button(text="💰 Пополнить баланс", callback_data="select_pay_method")
    kb.button(text="Партнерская программа", callback_data="partner")
    kb.button(text="Что умею?", callback_data="help")
    kb.button(text="Поддержка", url=f"https://t.me/{env.SUPPORT_USERNAME}")
    if chat_id in settings.get_admins_chat_id():
        kb.button(text="Панель андминистратора", web_app=types.WebAppInfo(url=env.ADMIN_SITE))
    kb.adjust(1, 1, 1, 1, 2, 1)
    return kb.as_markup()


def help_keyboard(chat_id: int) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_photo")
    kb.button(text="💰 Пополнить баланс", callback_data="select_pay_method")
    kb.button(text="Назад", callback_data="start_back")
    kb.button(text="Поддержка", url=f"https://t.me/{env.SUPPORT_USERNAME}")
    if chat_id in settings.get_admins_chat_id():
        kb.button(text="Панель андминистратора", web_app=types.WebAppInfo(url=env.ADMIN_SITE))
    kb.adjust(1, 1, 1, 2, 1)
    return kb.as_markup()


def prompt_options_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить / Добавить", callback_data="prompt_edit")
    kb.button(text="✅ Принять", callback_data="prompt_accept")
    kb.button(text="↻ Другой вариант", callback_data="prompt_other")
    kb.button(text="❌ Отклонить", callback_data="prompt_reject")
    kb.adjust(2)
    return kb.as_markup()


def aspect_ratio_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="16:9 (горизонтальное)", callback_data="aspect_16_9")
    kb.button(text="9:16 (вертикальное)", callback_data="aspect_9_16")
    kb.button(text="Назад", callback_data="start_back")
    kb.adjust(1, 1, 2)
    return kb.as_markup()


def sent_prompt_kb(task_id: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Повторить генерацию",
              callback_data=f"repeat_generation:{task_id}")
    kb.button(text="🆕 Новый запрос", callback_data="new_generation")
    kb.button(text="🏠 Главное меню", callback_data="start_back")
    kb.adjust(1, 1, 1)
    return kb.as_markup()


async def _stop_task(task: asyncio.Task | None):
    if task:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


# --- Команда /start и возвращение в начало ---

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
                "https://storage.yandexcloud.net/veobot/photo_2025-08-12_00-07-56.jpg"),
            caption="Привет! Я генерирую для тебя лучшее видео по твоему запросу.\n\n"
        )

        await message.answer("Ты у нас впервые. Регистрирую…")
        nickname = (
            message.from_user.username
            or message.from_user.first_name
            or f"user_{message.from_user.id}"
        )
        try:
            # Handle referral link
            referral_payload = None
            command_args = message.text.split()
            if len(command_args) > 1:
                encoded_token = command_args[1]
                referral_payload = referral_service.decode_and_validate_token(encoded_token)
                if not referral_payload:
                    logging.warning(f"Invalid or expired referral token used by chat_id {message.from_user.id}")

            # Prepare registration data for the backend
            registration_data = {
                "chat_id": str(message.from_user.id),
                "nickname": nickname,
            }
            if referral_payload:
                registration_data["referrer_type"] = referral_payload.get("t")
                registration_data["referrer_id"] = referral_payload.get("rid")
                registration_data["ref_link_id"] = referral_payload.get("lid")

            res = await backend.register_user(**registration_data)
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
        coins = 0  # если не достали баланс — не роняем UX

    if not exists:
        text = (
            "Регистрация прошла успешно! Теперь давай сгенерируем видео!\n\n"
            f"У тебя {coins} генераций.\n\nШаг 1/3. Выбери способ создания видео:"
        )
    else:
        text = (
            f"С возвращением!\n\nУ тебя {coins} генераций.\n\n"
            "Шаг 1/3. Выбери способ создания видео::"
        )

    sent_message: Optional[types.Message] = await message.answer(
        text,
        reply_markup=start_keyboard(message.from_user.id)
    )

    # Сохраняем id отправленного сообщения
    await state.update_data(start_message_id=sent_message.message_id)
    await state.set_state(fsm.BotState.start_message_id)


@router.callback_query(F.data == "start_back")
async def back_to_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    coins = await backend.get_coins(user_id)
    sent = await callback.message.answer(
        f"У тебя {coins} генераций.\n\nШаг 1/3. Выбери способ создания видео:",
        reply_markup=start_keyboard(user_id)
    )
    await state.update_data(start_message_id=sent.message_id)
    await state.set_state(fsm.BotState.start_message_id)


# --- Партнерская программа ---

def partner_cabinet_kb() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Дашборд", callback_data="partner:dashboard")
    kb.button(text="🔗 Мои ссылки", callback_data="partner:links")
    kb.button(text="📈 История начислений", callback_data="partner:commissions")
    kb.button(text="💰 Выплаты", callback_data="partner:payouts")
    kb.button(text="🏠 Назад в главное меню", callback_data="start_back")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

@router.callback_query(F.data == "partner")
async def partner_program_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    try:
        user_roles = await backend.get_user_roles(user_id)
        is_partner = "partner" in user_roles
        if is_partner:
            await partner_dashboard_handler(callback, state) # Go directly to dashboard
        else:
            await show_user_referral_info(callback, user_id)
    except Exception as e:
        logging.error(f"Failed to load partner program data for user {user_id}: {e}", exc_info=True)
        await callback.message.answer("Не удалось загрузить данные партнерской программы. Попробуйте позже.")

async def show_user_referral_info(callback: types.CallbackQuery, user_id: int):
    link_data = await backend.get_user_referral_link(user_id)
    stats_data = await backend.get_user_referral_stats(user_id)
    link = link_data.get("url", "Не удалось получить ссылку.")
    stats = stats_data
    text = (
        "🎉 **Ваша реферальная программа**\n\n"
        "Пригласите друга и получите по **1 бесплатной генерации** каждый "
        "после его первой покупки!\n\n"
        "🔗 **Ваша персональная ссылка:**\n"
        f"`{link}`\n\n"
        "📊 **Статистика:**\n"
        f"  - Друзей зарегистрировано: **{stats.get('registrations', 0)}**\n"
        f"  - Совершили первую покупку: **{stats.get('first_purchases', 0)}**\n"
        f"  - Бонусов заработано: **{stats.get('bonuses_earned', 0)}** генераций"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="Назад", callback_data="start_back")
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode=ParseMode.MARKDOWN)

@router.callback_query(F.data == "partner:dashboard")
async def partner_dashboard_handler(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    user_id = callback.from_user.id
    try:
        dashboard_data = await backend.get_partner_dashboard(user_id)
        text = (
            "**🗄️ Кабинет партнера**\n\n"
            f"**Баланс:**\n"
            f"  - Доступно к выводу: **{dashboard_data.get('balance_available', 0) / 100:.2f} ₽**\n"
            f"  - В холде: **{dashboard_data.get('balance_hold', 0) / 100:.2f} ₽**\n\n"
            f"**Общая статистика:**\n"
            f"  - Всего регистраций: **{dashboard_data.get('total_registrations', 0)}**\n"
            f"  - Всего продаж: **{dashboard_data.get('total_sales', 0) / 100:.2f} ₽**\n"
            f"  - Всего заработано: **{dashboard_data.get('total_earned', 0) / 100:.2f} ₽**"
        )
        await callback.message.edit_text(text, reply_markup=partner_cabinet_kb(), parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logging.error(f"Failed to load partner dashboard for user {user_id}: {e}", exc_info=True)
        await callback.message.answer("Не удалось загрузить дашборд. Попробуйте позже.")

# Placeholders for other partner cabinet features
@router.callback_query(F.data == "partner:links")
async def partner_links_placeholder(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Эта функция в разработке.", show_alert=True)

@router.callback_query(F.data == "partner:commissions")
async def partner_commissions_placeholder(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Эта функция в разработке.", show_alert=True)

@router.callback_query(F.data == "partner:payouts")
async def partner_payouts_placeholder(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Эта функция в разработке.", show_alert=True)


# --- Меню помощи ---


@router.callback_query(F.data == "help")
async def help_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text = (
        "Я — Объективео 3. Что умею\n\n"

        "🎬 Видео по тексту\n"
        "Пишите как хотите — кратко или подробно. Я сам превращу текст в точный промпт и скину на проверку. Жмёте «Принять» — делаю короткий проф-ролик.\n"
        "Промпт писать не нужно.\n\n"

        "🖼️ Оживляю фото\n"
        "Пришлите фото/картинку и описание того, что должно происходить в кадре (действия, события, мимика/эмоции, движение камеры, спецэффекты). Я предложу промпт на проверку. Жмёте «Принять» — перехожу к превращению кадра в видео.\n\n"

        "✨ По референсу (через фото)\n"
        "Нажмите «Сгенерировать по фото», загрузите референс и ничего не пишите. Я опишу кадр и соберу промпт. Скопируйте его и запустите «Сгенерировать по тексту» — получите вашу версию. После «Принять» — запускаю генерацию.\n\n"

        "📝 По промпту\n"
        "Есть классный промпт? Пришлите его («Сгенерировать по тексту»). Верну подтверждение и русскую версию. После жмёте «Принять», запускаю генерацию.\n\n"

        "⸻\n\n"

        "✅ Согласование перед запуском\n"
        "• Вы видите человеческую версию промпта на русском (внутри я отправлю на английском).\n"
        "• После чтения выбираете одно действие:\n\n"

        "🎯 Действия\n"
        "• Принять — сразу запускаю генерацию.\n"
        "• Изменить — точечно правим детали (музыка, роли, диалоги, стиль/вайб, камера, темп).\n"
        "• Другой вариант — перегенерирую формулировку с учётом ваших пометок.\n"
        "• Отменить — останавливаем текущую попытку.\n\n"

        "⸻\n\n"

        "ℹ️ Пара полезностей\n"
        "• Можно писать текстом или голосовым.\n"
        "• Промпт собираю автоматически (ChatGPT, Gemini 2.5 Pro, Grok) — заточено под Veo 3.\n"
        "• Форматы: 9:16 и 16:9."
    )
    await callback.message.answer(text, reply_markup=help_keyboard(callback.from_user.id))

# --- Генерация по тексту ---


@router.callback_query(F.data == "generate_by_text")
async def callback_generate_by_text(callback: types.CallbackQuery, state: FSMContext):
    # удаляем стартовое сообщение
    data = await state.get_data()
    start_msg_id = data.get("start_message_id")
    if start_msg_id:
        with suppress(Exception):
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=start_msg_id)
    await callback.answer()
    await callback.message.answer("Шаг 2/3. Что должно быть в ролике?", reply_markup=InlineKeyboardBuilder().button(text="Назад", callback_data="start_back").as_markup())
    await state.update_data(mode="text")
    await state.set_state(fsm.BotState.waiting_for_text_description)


@router.message(fsm.BotState.waiting_for_text_description)
async def handle_text_description(message: types.Message, state: FSMContext):
    brief = (message.text or "").strip()
    if not brief:
        await message.answer("Опиши кратко сюжет будущего видео.")
        return

    # запускаем прогресс‑индикатор
    progress_msg = await message.answer("⏳ Собираю промпт…")
    progress_task = asyncio.create_task(
        show_progress(progress_msg, stage="prompt"))

    try:
        ru_text, en_text = await backend.suggest_prompt(
            chat_id=str(message.from_user.id),
            brief=brief,
            clarifications=None,
            attempt=1,
            previous_prompt=None,
        )
    except Exception as e:
        logging.exception("Ошибка генерации промпта: %s", e)
        await message.answer("Не удалось получить промпт. Попробуйте ещё раз.")
        return
    finally:
        await _stop_task(progress_task)

    await state.update_data(
        prompt_brief=brief,
        prompt_last=en_text,
        prompt_attempt=1,
        prompt_clarifications=[],
        mode="text"
    )
    await progress_msg.edit_text(f"`{ru_text}`", parse_mode="Markdown", reply_markup=prompt_options_kb())
    await state.set_state(fsm.PromptAssistantState.reviewing)

# --- Генерация по фото ---


@router.callback_query(F.data == "generate_photo")
async def start_photo_flow(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.update_data(mode="photo")
    await callback.message.answer("Шаг 2/3. Пришлите фото с описанием того, что будет происходить в кадре (для референса — без описания).", reply_markup=InlineKeyboardBuilder().button(text="Назад", callback_data="start_back").as_markup())
    await state.set_state(fsm.PhotoState.waiting_photo)


@router.message(fsm.PhotoState.waiting_photo)
async def handle_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Отправь изображение.")
        return

    # скачиваем фото
    photo_id = message.photo[-1].file_id
    file = await message.bot.get_file(photo_id)
    file_bytes = await message.bot.download_file(file.file_path)

    # загружаем на S3
    image_url = storage.save(file_bytes.getvalue(
    ), extension=".jpg", prefix="prompt_inputs/")
    await state.update_data(image_url=image_url, prompt_attempt=1, prompt_clarifications=[])

    # запускаем прогресс‑индикатор
    progress_msg = await message.answer("⏳ Анализирую фото и собираю промпт…")
    progress_task = asyncio.create_task(
        show_progress(progress_msg, stage="prompt"))

    try:
        # генерируем промпт, передав image_url в backend
        ru_text, en_text = await backend.suggest_prompt(
            chat_id=str(message.from_user.id),
            brief=message.caption or "",
            clarifications=None,
            attempt=1,
            previous_prompt=None,
            image_url=image_url,
        )
    except Exception as e:
        logging.exception("Ошибка генерации промпта по фото: %s", e)
        await message.answer("Не удалось получить промпт. Попробуйте ещё раз.")
        return
    finally:
        await _stop_task(progress_task)

    await state.update_data(prompt_last=en_text)
    await progress_msg.edit_text(f"`{ru_text}`", parse_mode="Markdown", reply_markup=prompt_options_kb())
    await state.set_state(fsm.PromptAssistantState.reviewing)

# --- Работа с промптом (общая) ---


@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_accept")
async def prompt_accept(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    # Переходим к выбору формата
    await callback.message.answer("Шаг 3/3. Выберите формат видео:", reply_markup=aspect_ratio_kb())


@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_other")
async def prompt_other(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    brief = data.get("prompt_brief") or ""
    clar = data.get("prompt_clarifications", [])
    last = data.get("prompt_last")
    attempt = int(data.get("prompt_attempt", 1)) + 1

    # закрываем callback сразу, чтобы он не протух
    await callback.answer("Готовлю новый вариант…", show_alert=False)

    # сообщение, в которое будем писать прогресс
    progress_msg = await callback.message.answer("⏳ Получаю новый вариант…")

    # запускаем прогресс‑бар параллельно
    progress_task = asyncio.create_task(
        show_progress(progress_msg, stage="prompt")
    )

    try:
        ru_text, en_text = await backend.suggest_prompt(
            chat_id=str(callback.from_user.id),
            brief=brief,
            clarifications=clar,
            attempt=attempt,
            previous_prompt=last,
        )
    except Exception as e:
        logging.exception("Ошибка получения нового варианта: %s", e)
        await progress_msg.edit_text("❌ Не удалось получить новый вариант. Попробуйте ещё раз.")
        return
    finally:
        await _stop_task(progress_task)

    # сохраняем обновлённые данные
    await state.update_data(prompt_last=en_text, prompt_attempt=attempt)

    # обновляем сообщение с вариантом
    await progress_msg.edit_text(
        f"Вариант #{attempt}:\n\n`{ru_text}`",
        parse_mode="Markdown",
        reply_markup=prompt_options_kb()
    )


@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_edit")
async def prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напишите, что нужно изменить/добавить:")
    await state.set_state(fsm.PromptAssistantState.editing)


@router.message(fsm.PromptAssistantState.editing)
async def prompt_receive_edit(message: types.Message, state: FSMContext):
    edit = (message.text or "").strip()
    if not edit:
        await message.answer("Напишите корректировку.")
        return

    data = await state.get_data()
    brief = data.get("prompt_brief") or ""
    clar = data.get("prompt_clarifications", [])
    clar.append(edit)
    last = data.get("prompt_last")
    attempt = int(data.get("prompt_attempt", 1)) + 1

    # отправляем сообщение о загрузке и запускаем прогресс‑бар
    progress_msg = await message.answer("⏳ Собираю новый вариант с учётом правок…")
    progress_task = asyncio.create_task(
        show_progress(progress_msg, stage="prompt")
    )

    try:
        ru_text, en_text = await backend.suggest_prompt(
            chat_id=str(message.from_user.id),
            brief=brief,
            clarifications=clar,
            attempt=attempt,
            previous_prompt=last
        )
    except Exception as e:
        logging.exception("Ошибка получения варианта с правками: %s", e)
        await progress_msg.edit_text("❌ Не удалось получить новый вариант. Попробуйте ещё раз.")
        return
    finally:
        await _stop_task(progress_task)

    # обновляем данные в FSM
    await state.update_data(prompt_clarifications=clar, prompt_last=en_text, prompt_attempt=attempt)
    # заменяем текст сообщения на новый вариант
    await progress_msg.edit_text(
        f"Вариант #{attempt}:\n\n`{ru_text}`",
        parse_mode="Markdown",
        reply_markup=prompt_options_kb()
    )
    # возвращаемся в состояние просмотра промпта
    await state.set_state(fsm.PromptAssistantState.reviewing)


@router.callback_query(fsm.PromptAssistantState.reviewing, F.data == "prompt_reject")
async def prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Промпт отклонён")
    await callback.message.answer("Окей, вернёмся к главному меню.")

# --- Выбор формата и запуск генерации ---


def pay_button() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Пополнить баланс", callback_data="select_pay_method")

    return kb.as_markup()


@router.callback_query(fsm.PromptAssistantState.reviewing, F.data.startswith("aspect_"))
async def aspect_ratio_chosen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    prompt_text = data.get("prompt_last")
    if not prompt_text:
        await callback.message.answer("Нет промпта для генерации.")
        return

    aspect_ratio = "16:9" if callback.data == "aspect_16_9" else "9:16"
    mode = data.get("mode")
    coins = await backend.get_coins(callback.from_user.id)
    if coins == 0:
        await callback.message.answer("У вас недостаточно генераций, пожалуйста пополните баланс по кнопке ниже ⬇️", reply_markup=pay_button())
        return

    try:
        if mode == "photo":
            image_url = data.get("image_url")
            if not image_url:
                await callback.message.answer("Не удалось найти изображение для генерации.")
                return
            task = await backend.generate_photo(
                chat_id=str(callback.from_user.id),
                prompt=prompt_text,
                image_url=image_url,
                aspect_ratio=aspect_ratio,
            )
        else:
            task = await backend.generate_text(
                chat_id=str(callback.from_user.id),
                prompt=prompt_text,
                aspect_ratio=aspect_ratio,
            )

        task_id = task["task_id"]
        # здесь формируем словарь с нужным контекстом для повторной генерации
        raw_ctx = {
            "prompt": prompt_text,
            "mode": mode,
            "aspect_ratio": aspect_ratio,
            "image_url": image_url if mode == "photo" else None,
        }

        # coхраняем контекст в БД – ошибки ловим по месту
        with suppress(Exception):
            await backend.save_task(task_id, str(callback.from_user.id), raw_ctx, is_video=(mode == "photo"), rating=0)

        await callback.message.answer(
            f"🚀 Приступил к генерации видео.\nОстаток: {coins -1}.\n"
            "По готовности пришлю уведомление.\n"
            "Сделать ещё?",
            reply_markup=sent_prompt_kb(task_id)
        )
        # запускаем прогресс‑бар для генерации видео
        progress_msg = await callback.message.answer("⏳ Генерирую видео…")
        progress_task = asyncio.create_task(
            show_progress(progress_msg, stage="video"))
        PROGRESS[task_id] = {
            "task": progress_task,
            "chat_id": callback.message.chat.id,
            "message_id": progress_msg.message_id,
        }
    except Exception as e:
        logging.exception("Ошибка запуска генерации: %s", e)
        await callback.message.answer("❌ Не удалось запустить генерацию.")
        return

# --- Повтор и новый запрос ---

# @router.callback_query(F.data == "repeat_generation")
# async def on_repeat_generation(callback: types.CallbackQuery, state: FSMContext):
#     data = await state.get_data()
#     prompt_text = data.get("prompt_last")
#     mode = data.get("mode")
#     if not prompt_text:
#         await callback.answer("Нет сохранённого промпта.", show_alert=True)
#         return

#     # повторяем генерацию с тем же aspect_ratio (по желанию можно дать пользователю выбрать заново)
#     aspect_ratio = "16:9"
#     try:
#         if mode == "photo":
#             image_url = data.get("image_url")
#             task = await backend.generate_photo(
#                 chat_id=str(callback.from_user.id),
#                 prompt=prompt_text,
#                 image_url=image_url,
#                 aspect_ratio=aspect_ratio,
#             )
#         else:
#             task = await backend.generate_text(
#                 chat_id=str(callback.from_user.id),
#                 prompt=prompt_text,
#                 aspect_ratio=aspect_ratio,
#             )
#         await callback.message.answer(
#             f"Повторная генерация запущена!",
#             parse_mode="Markdown"
#         )
#         task_id = task["task_id"]

#         # 2) потом заводим прогресс и регистрируем его для последующего finish
#         progress_msg = await callback.message.answer("⏳ Генерирую видео…")
#         progress_task = asyncio.create_task(show_progress(progress_msg, stage="video"))
#         PROGRESS[task_id] = {
#             "task": progress_task,
#             "chat_id": callback.message.chat.id,
#             "message_id": progress_msg.message_id,
#         }

#     except Exception as e:
#         logging.exception("Ошибка повторной генерации: %s", e)
#         await callback.message.answer("❌ Не удалось запустить повтор.")
#     finally:
#         await _stop_task(progress_task)


@router.callback_query(F.data.startswith("repeat_generation:"))
async def on_repeat_generation_by_task(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    _, task_id = callback.data.split(":", 1)
    progress_task: asyncio.Task | None = None

    coins = await backend.get_coins(callback.from_user.id)
    if coins == 0:
        await callback.message.answer("У вас недостаточно генераций, пожалуйста пополните баланс по кнопке ниже ⬇️", reply_markup=pay_button())
        return

    try:
        # получаем запись о задаче из БД
        task_record = await backend.get_task(task_id)

        # raw в БД хранится в виде JSON‑строки
        raw = json.loads(task_record.get("raw", "{}"))
        prompt = raw.get("prompt")
        mode = raw.get("mode")
        aspect_ratio = raw.get("aspect_ratio")
        image_url = raw.get("image_url", "")
        print(task_record)
        # для удобства восстанавливаем FSM – если дальше понадобится prompt_last и mode
        await state.update_data(prompt_last=prompt, mode=mode, image_url=image_url)

        # запускаем повторную генерацию
        if mode == "photo" and image_url:
            new_task = await backend.generate_photo(
                chat_id=str(callback.from_user.id),
                prompt=prompt,
                image_url=image_url,
                aspect_ratio=aspect_ratio,
            )
        else:
            new_task = await backend.generate_text(
                chat_id=str(callback.from_user.id),
                prompt=prompt,
                aspect_ratio=aspect_ratio,
            )

        new_task_id = new_task["task_id"]

        # сохраняем новый контекст (по желанию) и показываем клавиатуру
        with suppress(Exception):
            await backend.save_task(
                new_task_id,
                str(callback.from_user.id),
                raw,
                is_video=(mode == "photo"),
                rating=0,
            )
        await callback.message.answer(
            f"🚀 Приступил к генерации видео.\nОстаток: {coins -1}.\n"
            "По готовности пришлю уведомление.\n"
            "Сделать ещё?",
            reply_markup=sent_prompt_kb(task_id)
        )
        await callback.answer()
        # заводим прогресс и регистрируем его для последующего finish
        progress_msg = await callback.message.answer("⏳ Генерирую видео…")
        progress_task = asyncio.create_task(
            show_progress(progress_msg, stage="video"))
        PROGRESS[new_task_id] = {
            "task": progress_task,
            "chat_id": callback.message.chat.id,
            "message_id": progress_msg.message_id,
        }

    except Exception as e:
        logging.exception("Ошибка при повторной генерации: %s", e)
        await callback.answer("Не удалось повторить генерацию", show_alert=True)


@router.callback_query(F.data == "new_generation")
async def on_new_generation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Начинаем заново.\n\nШаг 1/3. Выбери способ создания видео:",
        reply_markup=start_keyboard(callback.from_user.id)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("rate:"))
async def on_rate(callback: types.CallbackQuery, state: FSMContext):
    try:
        _, task_id, rating_str = callback.data.split(":")
        rating = int(rating_str)
        if rating < 1 or rating > 5:
            raise ValueError("rating must be 1-5")
    except Exception:
        await callback.answer("Неверный формат оценки", show_alert=True)
        return

    try:
        await backend.rate_task(task_id, rating)
        message_id = await redis.get_del_msg(f"{callback.from_user.id}:{task_id}")
        await callback.bot.delete_message(chat_id=callback.from_user.id, message_id=message_id)
        await callback.message.answer(f"Спасибо за оценку {"⭐" * rating}!", reply_markup=sent_prompt_kb(task_id))

    except Exception as e:
        logging.exception("Ошибка отправки оценки: %s", e)
        await callback.answer("Не удалось отправить оценку", show_alert=True)


@router.callback_query(F.data == "hello")
async def testing(callback: types.CallbackQuery):
    progress_msg = await callback.message.answer("⏳ Генерирую видео…")
    progress_task = asyncio.create_task(
        show_progress(progress_msg, stage="video"))
    print(callback.bot, callback.from_user.id, progress_msg.message_id)
