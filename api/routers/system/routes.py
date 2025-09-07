from __future__ import annotations
import asyncio
from typing import List, Union
from fastapi import APIRouter, Depends, Request
from api.crud.user import UserService
from api.database import get_async_session
from api.routers.system import SystemRoutesManager
from api.routers.system.schemas import BotMessage
from api.security import require_bot_service
from bot.manager import bot_manager
from sqlalchemy.ext.asyncio import AsyncSession
from scalar_fastapi import get_scalar_api_reference
from aiogram import types
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

router = APIRouter()

SRM = SystemRoutesManager()
user = UserService()


@router.post("/bot", include_in_schema=False)
async def webhook_handler(request: Request):
    await SRM.webhook_updates(request=request)


@router.on_event("startup")
async def startup():
    await bot_manager.bot_start()


@router.on_event("shutdown")
async def startup():
    await bot_manager.bot_stop()


@router.get("/check-health", include_in_schema=False)
def check_health():
    return {"ok": True}


@router.get("/scalar", include_in_schema=False)
def get_scalar():
    app = SRM.get_app()
    
    return get_scalar_api_reference(
        title=app.title,
        openapi_url=app.openapi_url,
    )


async def _resolve_chat_id(raw: Union[str, int]):
    s = str(raw).strip()
    # username → реальный id
    if s.startswith("@"):
        chat = await bot_manager.bot.get_chat(s)
        return chat.id
    # просто число (в т.ч. -100… для супергрупп/каналов)
    return int(s)

async def _send(dto: "BotMessage", chat_id: int):
    # Валидация доступа/существования
    chat = await bot_manager.bot.get_chat(chat_id)

    if dto.img_url and not dto.video_url:
        await bot_manager.bot.send_photo(chat_id=chat_id, photo=dto.img_url, caption=dto.text or None)
    elif dto.video_url and not dto.img_url:
        await bot_manager.bot.send_video(chat_id=chat_id, video=dto.video_url, caption=dto.text or None)
    elif dto.img_url and dto.video_url:
        media = [
            types.InputMediaPhoto(media=dto.img_url, caption=dto.text or None),
            types.InputMediaVideo(media=dto.video_url),
        ]
        await bot_manager.bot.send_media_group(chat_id=chat_id, media=media)
    else:
        await bot_manager.bot.send_message(chat_id=chat_id, text=dto.text)

@router.post(
    "/post-message",
    summary="Рассылка и личное сообщение",
    dependencies=[Depends(require_bot_service)]
)
async def post_message(
        dto: "BotMessage",
        session: "AsyncSession" = Depends(get_async_session)
):
    users = await user.list_user_chat_ids(session)
    if dto.chat_id:
        users = [dto.chat_id]

    # Нормализация и дедуп
    norm_ids: List[int] = []
    for raw in users:
        try:
            cid = await _resolve_chat_id(raw)
            norm_ids.append(cid)
        except Exception:
            # Сильно шуметь не будем — просто пропустим и залогируем ниже
            pass
    norm_ids = list(dict.fromkeys(norm_ids))

    failures = []
    sent = 0

    # Ограничим параллелизм, чтобы не ловить 429
    sem = asyncio.Semaphore(20)

    async def _safe_send(cid: int):
        nonlocal sent
        try:
            async with sem:
                await _send(dto, cid)
                sent += 1
        except TelegramBadRequest as e:
            # Автомиграция супергрупп
            # У aiogram 3 в e.params может прилететь migrate_to_chat_id
            new_id = getattr(getattr(e, "parameters", None), "migrate_to_chat_id", None)
            if new_id:
                try:
                    await _send(dto, new_id)
                    sent += 1
                    # важно: обнови у себя в БД chat_id на new_id
                    await user.update_chat_id(session, old_id=cid, new_id=new_id)
                    return
                except Exception as e2:
                    failures.append((cid, f"migrated→{new_id} failed: {e2!r}"))
                    return
            failures.append((cid, f"{type(e).__name__}: {e.message}"))
        except TelegramForbiddenError as e:
            failures.append((cid, "forbidden (user blocked bot / no access)"))
        except Exception as e:
            failures.append((cid, f"{type(e).__name__}: {e!r}"))

    await asyncio.gather(*[_safe_send(cid) for cid in norm_ids])

    # Возвращаем аккуратный ответ (и можно ещё это логировать)
    return {
        "total": len(norm_ids),
        "sent": sent,
        "failed": [{"chat_id": cid, "reason": reason} for cid, reason in failures]
    }