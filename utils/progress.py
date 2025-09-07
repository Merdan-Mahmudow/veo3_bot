import asyncio
from contextlib import suppress
from typing import TypedDict, Dict
from aiogram import Bot, types


class _Progress(TypedDict):
    task: asyncio.Task
    chat_id: int
    message_id: int


PROGRESS: Dict[str, _Progress] = {}

# --- Прогресс‑бар ---


async def show_progress(msg: types.Message, stage: str):
    if stage == "prompt":
        stages = [
            ("5%",  "🧠◼️◼️◼️◼️◼️◼️◼️◼️◼️ 5%",  "💬 Внимаю идее"),
            ("15%", "🧠🧠◼️◼️◼️◼️◼️◼️◼️◼️ 15%", "💬 Развожу роли и образы"),
            ("30%", "🧠🧠🧠◼️◼️◼️◼️◼️◼️◼️ 30%", "💬 Плету структуру текста"),
            ("60%", "🧠🧠🧠🧠🧠🧠◼️◼️◼️◼️ 60%", "💬 Придаю ритм и ясность"),
            ("95%", "🧠🧠🧠🧠🧠🧠🧠🧠🧠◼️ 95%", "💬 Запечатываю замысел"),
            ("100%", "🧠🧠🧠🧠🧠🧠🧠🧠🧠🧠 100%", "💬 Промпт завершён 🌟"),
        ]
        delay = 10
    else:  # stage == "video"
        stages = [
            ("5%",  "📹◼️◼️◼️◼️◼️◼️◼️◼️◼️ 5%",  "🔴 REC Оживляю сцену"),
            ("15%", "📹📹◼️◼️◼️◼️◼️◼️◼️◼️ 15%", "🔴 REC Веду движение"),
            ("30%", "📹📹📹◼️◼️◼️◼️◼️◼️◼️ 30%", "🔴 REC Зажигаю свет и краски"),
            ("60%", "📹📹📹📹📹📹◼️◼️◼️◼️ 60%", "🔴 REC Устраняю тени и шум"),
            ("95%", "📹📹📹📹📹📹📹📹📹◼️ 95%", "🔴 REC Последний мазок"),
            ("100%", "📹📹📹📹📹📹📹📹📹📹 100%", "🔴 REC Картинка ожила ✨"),
        ]                       
        delay = 30

    for percent, bar, note in stages:
            text = f"{percent}\n{bar}\n{note}"
            with suppress(Exception):
                await msg.edit_text(text)
            await asyncio.sleep(delay)

async def show_progress_msg(bot: Bot, chat_id: int, message_id: int, stage: str):
    print("hello")
    if stage == "prompt":
        stages = [
            ("5%",  "🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 5%",  "Читаю идею, ловлю суть."),
            ("15%", "🟡🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 15%", "Разбираю: кто/что/где/стиль."),
            ("30%", "🟡🟡🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 30%", "Собираю структуру, убираю воду."),
            ("60%", "🟡🟡🟡🟡🟡🟡⚫️⚫️⚫️⚫️ 60%", "Шлифую формулировку, стыкую логику."),
            ("95%", "🟡🟡🟡🟡🟡🟡🟡🟡🟡⚫️ 95%", "Упаковываю финальный промпт."),
        ]
        delay = 10
    else:  # stage == "video"
        stages = [
            ("5%",  "🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 5%",  "Отправил на генерацию. Готовлю сцену."),
            ("15%", "🟡🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 15%", "Собираю кадры и движение."),
            ("30%", "🟡🟡🟡⚫️⚫️⚫️⚫️⚫️⚫️⚫️ 30%", "Добавляю свет, цвет, вайб."),
            ("60%", "🟡🟡🟡🟡🟡🟡⚫️⚫️⚫️⚫️ 60%", "Сглаживаю артефакты, финальные стыки."),
            ("95%", "🟡🟡🟡🟡🟡🟡🟡🟡🟡⚫️ 95%", "Готовлю ссылку. Ещё мгновение…"),
        ]
        delay = 30

    for percent, bar, note in stages:
        text = f"{percent}\n{bar}\n{note}"
        await bot.edit_message_text(text, chat_id=chat_id, message_id=message_id)
        await asyncio.sleep(delay)


async def finish_progress(task_id: str, bot: Bot):
    info = PROGRESS.pop(task_id, None)
    if not info:
        return
    task = info["task"]
    task.cancel()
    with suppress(asyncio.CancelledError):
        await task
    # пробуем удалить сообщение
    with suppress(Exception):
        await bot.delete_message(info["chat_id"], info["message_id"])
