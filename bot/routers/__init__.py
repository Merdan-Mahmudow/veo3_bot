import asyncio
from contextlib import suppress
import logging
from typing import Dict, TypedDict

from aiogram import Router, types, F, Bot
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot import fsm
from bot.api import BackendAPI
from config import ENV
from services.storage import YandexS3Storage
from utils.progress import PROGRESS, show_progress


router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)
storage = YandexS3Storage()


# --- Клавиатуры ---

def start_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_photo")
    kb.button(text="💰 Пополнить баланс", callback_data="buy_coins")
    kb.button(text="Что умею?", callback_data="help")
    kb.button(text="Поддержка", url=f"https://t.me/{env.SUPPORT_USERNAME}")
    kb.adjust(1, 1, 1, 2)
    return kb.as_markup()

def help_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Сгенерировать по тексту", callback_data="generate_by_text")
    kb.button(text="Сгенерировать по фото", callback_data="generate_photo")
    kb.button(text="💰 Пополнить баланс", callback_data="buy_coins")
    kb.button(text="Назад", callback_data="start_back")
    kb.button(text="Поддержка", url=f"https://t.me/{env.SUPPORT_USERNAME}")
    kb.adjust(1, 1, 1, 2)
    return kb.as_markup()

def prompt_options_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✏️ Изменить", callback_data="prompt_edit")
    kb.button(text="✅ Принять", callback_data="prompt_accept")
    kb.button(text="↻ Другой вариант", callback_data="prompt_other")
    kb.button(text="❌ Отклонить", callback_data="prompt_reject")
    kb.adjust(2)
    return kb.as_markup()

def aspect_ratio_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="16:9 (горизонтальное)", callback_data="aspect_16_9")
    kb.button(text="9:16 (вертикальное)", callback_data="aspect_9_16")
    kb.button(text="Назад", callback_data="start_back")
    kb.adjust(1, 1, 2)
    return kb.as_markup()

def sent_prompt_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🔁 Повторить генерацию", callback_data="repeat_generation")
    kb.button(text="🆕 Новый запрос", callback_data="new_generation")
    kb.button(text="🏠 Главное меню", callback_data="start_back")
    kb.adjust(1, 1, 1)
    return kb.as_markup()


# --- Команда /start и возвращение в начало ---

@router.message(Command("start"))
async def command_start(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    nickname = message.from_user.username
    # регистрация и получение баланса
    await backend.ensure_user(str(user_id), nickname)
    coins = await backend.get_coins(user_id)

    await state.clear()
    sent = await message.answer(
        f"У тебя {coins} генераций.\n\nШаг 1/3. Выбери способ создания видео:",
        reply_markup=start_keyboard()
    )
    await state.update_data(start_message_id=sent.message_id)
    await state.set_state(fsm.BotState.start_message_id)

@router.callback_query(F.data == "start_back")
async def back_to_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    user_id = callback.from_user.id
    coins = await backend.get_coins(user_id)
    sent = await callback.message.answer(
        f"У тебя {coins} генераций.\n\nШаг 1/3. Выбери способ создания видео:",
        reply_markup=start_keyboard()
    )
    await state.update_data(start_message_id=sent.message_id)
    await state.set_state(fsm.BotState.start_message_id)

# --- Меню помощи ---

@router.callback_query(F.data == "help")
async def help_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    text = (
        "Я — Объективео3. Что умею:\n"
        "• 🎬 Видео по тексту — опиши кто/что/где/стиль.\n"
        "• 🖼 Оживляю фото — мимика/движение/камера.\n"
        "• 🎨 В стиле референса — повторю вайб и цвет.\n\n"
        "Дополнительно:\n"
        "• 🎤 Можно писать текстом или голосовым.\n"
        "• 🧠 Уточняю запрос на ChatGPT и собираю идеальный промпт для VEO3.\n"
        "• 📐 Поддержка форматов: 9:16 / 16:9 / 1:1"
    )
    await callback.message.answer(text, reply_markup=help_keyboard())

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
    await callback.message.answer("Шаг 2/3. Что должно быть в ролике?", reply_markup=InlineKeyboardBuilder().button(text="Назад", callback_data="start_back").as_markup())
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
    progress_task = asyncio.create_task(show_progress(message.bot, message.chat.id, progress_msg.message_id, stage="prompt"))

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
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
            

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
    await callback.message.answer("Шаг 2/3. Пришли фото (подпись не обязательна).", reply_markup=InlineKeyboardBuilder().button(text="Назад", callback_data="start_back").as_markup())
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
    image_url = storage.save(file_bytes.getvalue(), extension=".jpg", prefix="prompt_inputs/")
    await state.update_data(image_url=image_url, prompt_attempt=1, prompt_clarifications=[])

    # запускаем прогресс‑индикатор
    progress_msg = await message.answer("⏳ Анализирую фото и собираю промпт…")
    progress_task = asyncio.create_task(show_progress(message.bot, message.chat.id, progress_msg.message_id, stage="prompt"))

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
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
            

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
        show_progress(callback.bot, callback.from_user.id, progress_msg.message_id, stage="prompt")
    )

    try:
        ru_text, en_text = await backend.suggest_prompt(
            chat_id=str(callback.from_user.id),
            brief=brief,
            clarifications=clar,
            attempt=attempt,
            previous_prompt=last,
            # aspect_ratio="16:9",
        )
    except Exception as e:
        logging.exception("Ошибка получения нового варианта: %s", e)
        await progress_msg.edit_text("❌ Не удалось получить новый вариант. Попробуйте ещё раз.")
        return
    finally:
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
            

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
        show_progress(message.bot, message.chat.id, progress_msg.message_id, stage="prompt")
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
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
            

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
        coins = await backend.get_coins(callback.from_user.id)
        await callback.message.answer(
            f"🚀 Приступил к генерации видео.\nОстаток: {coins}.\n"
            "По готовности пришлю уведомление.\n"
            "Сделать ещё?",
            reply_markup=sent_prompt_kb()
        )
        # запускаем прогресс‑бар для генерации видео
        progress_msg = await callback.message.answer("⏳ Генерирую видео…")
        progress_task = asyncio.create_task(show_progress(callback.bot, callback.from_user.id, progress_msg.message_id, stage="video"))
        PROGRESS[task_id] = {
            "task": progress_task,
            "chat_id": callback.message.chat.id,
            "message_id": progress_msg.message_id,
        }
    except Exception as e:
        logging.exception("Ошибка запуска генерации: %s", e)
        await callback.message.answer("❌ Не удалось запустить генерацию.")
        return
    finally:
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
                
# --- Повтор и новый запрос ---

@router.callback_query(F.data == "repeat_generation")
async def on_repeat_generation(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    prompt_text = data.get("prompt_last")
    mode = data.get("mode")
    if not prompt_text:
        await callback.answer("Нет сохранённого промпта.", show_alert=True)
        return

    # повторяем генерацию с тем же aspect_ratio (по желанию можно дать пользователю выбрать заново)
    aspect_ratio = "16:9"
    try:
        if mode == "photo":
            image_url = data.get("image_url")
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
        await callback.message.answer(
            f"Повторная генерация запущена!",
            parse_mode="Markdown"
        )
        # запускаем прогресс‑бар для генерации видео
        progress_msg = await callback.message.answer("⏳ Генерирую видео…")
        progress_task = asyncio.create_task(show_progress(callback.bot, callback.from_user.id, progress_msg.message_id, stage="video"))
    except Exception as e:
        logging.exception("Ошибка повторной генерации: %s", e)
        await callback.message.answer("❌ Не удалось запустить повтор.")
    finally:
        # прекращаем прогресс, когда запрос завершился
        with suppress(Exception):
            progress_task.cancel()
            with suppress(asyncio.CancelledError):
                await progress_task
        

@router.callback_query(F.data == "new_generation")
async def on_new_generation(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer(
        "Начинаем заново.\n\nШаг 1/3. Выбери способ создания видео:",
        reply_markup=start_keyboard()
    )




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
        await callback.answer(f"Спасибо за оценку {"⭐" * rating}!", show_alert=True)
    except Exception as e:
        logging.exception("Ошибка отправки оценки: %s", e)
        await callback.answer("Не удалось отправить оценку", show_alert=True)