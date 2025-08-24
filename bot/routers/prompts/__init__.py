from __future__ import annotations
from typing import List, Optional
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from bot.api import BackendAPI
from bot.routers import prompt_options_kb
from config import ENV
from services.gpt import PromptAI
from bot.fsm import PhotoState, PromptAssistantState

router = Router()
prompt_ai = PromptAI()
env = ENV()
backend = BackendAPI(env.bot_api_token)


@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_accept")
async def prompt_accept(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    accepted = data.get("prompt_last")
    if not accepted:
        await callback.answer("Нет промпта для принятия", show_alert=True)
        return
    await callback.answer("Промпт принят ✅")
    # запускаем генерацию видео по тексту или фото (определите по data['mode'])
    # пример для текста:
    task = await backend.generate_text(chat_id=str(callback.from_user.id), prompt=accepted)
    await callback.message.answer(f"Генерация запущена! После завершения бот пришлёт результат.")
    await state.clear()

@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_other")
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
            aspect_ratio="16:9",
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

@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_edit")
async def prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Напишите, что нужно изменить/добавить:")
    await state.set_state(PromptAssistantState.editing)  # новое состояние для правок

@router.message(PromptAssistantState.editing)
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
        aspect_ratio="16:9",
    )
    await state.update_data(prompt_clarifications=clar, prompt_last=suggestion, prompt_attempt=attempt)
    await message.answer(
        f"{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await state.set_state(PromptAssistantState.reviewing)

@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_reject")
async def prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Промпт отклонён")
    await callback.message.answer("Окей, вернёмся к главному меню.")



# --- Хэндлер выбора режима генерации по фото ---
@router.callback_query(F.data == "generate_photo")
async def start_photo_flow(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer()
    await callback.message.answer("Пришли фотографию и короткое описание (в подписи), чтобы я смог подготовить промпт.")
    await state.set_state(PhotoState.waiting_photo)

# --- Получаем фото с подписью ---
@router.message(PhotoState.waiting_photo)
async def handle_photo_input(message: types.Message, state: FSMContext):
    if not message.photo or not message.caption:
        await message.answer("Отправь именно фото с подписью, в которой кратко опиши сюжет.")
        return

    # сохраняем id файла (или скачиваем байты)
    file_id = message.photo[-1].file_id
    brief = message.caption.strip()

    # сохраняем исходные данные
    await state.update_data(
        photo_file_id=file_id,
        prompt_brief=brief,
        prompt_attempt=1,
        prompt_last=None,
        prompt_clarifications=[],
        mode="photo"
    )

    # запрашиваем первый вариант промпта
    suggestion = await backend.suggest_prompt(
        chat_id=str(message.chat.id),
        brief=brief,
        clarifications=None,
        attempt=1,
        previous_prompt=None,
        aspect_ratio="16:9",
    )

    await state.update_data(prompt_last=suggestion)
    await message.answer(
        f"Предложенный промпт:\n\n{suggestion}",
        reply_markup=prompt_options_kb()
    )
    await state.set_state(PhotoState.reviewing)

# --- Обработка кнопок в состоянии reviewing ---
@router.callback_query(PhotoState.reviewing, F.data == "prompt_accept")
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

@router.callback_query(PhotoState.reviewing, F.data == "prompt_other")
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
        aspect_ratio="16:9",
    )
    await state.update_data(prompt_last=suggestion, prompt_attempt=attempt)
    await callback.message.edit_text(
        f"Вариант #{attempt}:\n\n{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await callback.answer("Другой вариант готов!")

@router.callback_query(PhotoState.reviewing, F.data == "prompt_edit")
async def photo_prompt_edit(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("Опиши, что нужно изменить/добавить к запросу:")
    await state.set_state(PhotoState.editing)

@router.message(PhotoState.editing)
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
        aspect_ratio="16:9",
    )
    await state.update_data(prompt_clarifications=clar, prompt_last=suggestion, prompt_attempt=attempt)
    await message.answer(
        f"Вариант #{attempt} (с учётом правок):\n\n{suggestion}",
        reply_markup=prompt_options_kb(),
    )
    await state.set_state(PhotoState.reviewing)

@router.callback_query(PhotoState.reviewing, F.data == "prompt_reject")
async def photo_prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.answer("Отменено")
    await callback.message.answer("Понятно, вернёмся в главное меню.")
