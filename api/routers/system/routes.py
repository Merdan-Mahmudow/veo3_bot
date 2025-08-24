from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from api.crud.user import UserService
from api.database import get_async_session
from api.routers.system import SystemRoutesManager
from bot.manager import bot_manager
from sqlalchemy.ext.asyncio import AsyncSession
from aiogram import types

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

@router.get("/check-health")
def check_health():
    return {"ok": True}

class BotMessage(BaseModel):
    text: str
    chat_id: str | None = None
    img_url: str | None = None
    video_url: str | None = None

@router.post("/post-message")
async def post_message(
    dto: BotMessage,
    session: AsyncSession = Depends(get_async_session)):
    users = await user.list_user_chat_ids(session)
    if dto.chat_id:
        users = [dto.chat_id]
    for chat in users:
        if dto.img_url and not dto.video_url:
            await bot_manager.bot.send_photo(chat_id=int(chat), photo=dto.img_url, caption=dto.text)
        elif dto.video_url and not dto.img_url:
            await bot_manager.bot.send_video(chat_id=int(chat), video=dto.video_url, caption=dto.text)
        elif dto.img_url and dto.video_url:
            await bot_manager.bot.send_media_group(
                chat_id=int(chat),
                media=[
                    {"type": 'photo', "media": dto.img_url,},
                    {"type": 'video', "media": dto.video_url, "caption": dto.text},
                ],
            )
        else:
            await bot_manager.bot.send_message(chat_id=int(chat), text=dto.text,)