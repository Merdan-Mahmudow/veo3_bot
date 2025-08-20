from __future__ import annotations
from typing import List, Optional
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
import logging

from services.gpt import PromptAI
from bot.fsm import PromptAssistantState

router = Router()
prompt_ai = PromptAI()

def prompt_review_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Принять", callback_data="prompt_accept")
    kb.button(text="↻ Отклонить", callback_data="prompt_reject")
    kb.adjust(2)
    return kb.as_markup()

@router.callback_query(F.data == "prompt_help")
async def prompt_help_entry(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await state.update_data(
        prompt_attempt=0,
        prompt_brief=None,
        prompt_last=None,
        prompt_clarifications=[],  # List[str]
    )
    await callback.message.answer(
        "Окей. Кратко опиши, какое видео ты хочешь получить: тема/сцена, настроение, стилистика.\n"
        "Например: «неоновый город ночью, дождь, киберпанк, динамичный ракурс»."
    )
    await state.set_state(PromptAssistantState.waiting_brief)

@router.message(PromptAssistantState.waiting_brief)
async def prompt_receive_brief(message: types.Message, state: FSMContext):
    brief = (message.text or "").strip()
    if not brief:
        await message.answer("Опиши в 1–2 предложениях, что должно быть в видео.")
        return

    await state.update_data(prompt_brief=brief, prompt_attempt=0, prompt_clarifications=[])
    await message.answer("Готовлю первый вариант…")
    await _generate_and_show(message, state)

# ---- Кнопки Принять / Отклонить ----

@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_accept")
async def prompt_accept(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    accepted = data.get("prompt_last") or ""
    await callback.answer("Принято ✅")
    # Здесь можно сразу предложить запустить генерацию видео этим промптом
    await callback.message.answer(
        "Отлично! Промпт принят:\n\n"
        f"{accepted}\n\n"
        "Хочешь запустить генерацию видео с этим промптом?",
        # можно дать тут же клавиатуру: [Сгенерировать видео]
    )
    await state.clear()

@router.callback_query(PromptAssistantState.reviewing, F.data == "prompt_reject")
async def prompt_reject(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    attempt = int(data.get("prompt_attempt", 0))
    attempt += 1
    await state.update_data(prompt_attempt=attempt)
    await callback.answer("Сделаем другой вариант…")

    # Каждые 2 отклонения — просим уточнения
    if attempt % 2 == 0:
        await callback.message.answer(
            "Чтобы попасть точнее, уточни детали: стиль, динамика, ракурс или то, чего точно не нужно."
        )
        await state.set_state(PromptAssistantState.waiting_clarifications)
        return

    # Иначе — сразу генерим следующий вариант
    await _generate_and_show(callback.message, state)

# ---- Получаем уточнения ----

@router.message(PromptAssistantState.waiting_clarifications)
async def prompt_receive_clarifications(message: types.Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text:
        await message.answer("Напиши пару уточнений словами — это поможет попасть точнее.")
        return

    data = await state.get_data()
    clar: List[str] = data.get("prompt_clarifications", [])
    clar.append(text)
    await state.update_data(prompt_clarifications=clar)
    await message.answer("Спасибо! Уточнения учёл. Готовлю новый вариант…")
    await _generate_and_show(message, state)

# ---- Вспомогательная функция генерации и показа ----

async def _generate_and_show(target_message: types.Message, state: FSMContext):
    data = await state.get_data()
    brief: str = data.get("prompt_brief", "")
    clar: List[str] = data.get("prompt_clarifications", [])
    last: Optional[str] = data.get("prompt_last")
    attempt: int = int(data.get("prompt_attempt", 0)) + 1  # следующая попытка

    try:
        suggestion = await prompt_ai.suggest_prompt(
            brief=brief,
            clarifications=clar,
            attempt=attempt,
            previous_prompt=last,
            aspect_ratio="16:9",
        )
    except Exception as e:
        print(e)
        await target_message.answer("❌ Не удалось запросить ассистента промптов. Попробуй ещё раз.")
        return

    await state.update_data(prompt_last=suggestion, prompt_attempt=attempt)
    await target_message.answer(
        f"Вариант #{attempt}:\n\n{suggestion}",
        reply_markup=prompt_review_kb()
    )
    await state.set_state(PromptAssistantState.reviewing)
