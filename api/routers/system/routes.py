from fastapi import APIRouter, Request
from api.routers.system import SystemRoutesManager
from bot.bot import BotManager

router = APIRouter()
SRM = SystemRoutesManager()

@router.post("/bot", include_in_schema=False)
async def webhook_handler(request: Request):
    await SRM.webhook_updates(request=request)

@router.on_event("startup")
async def startup():
    bot_manager = BotManager()

    await bot_manager.bot_start()

@router.on_event("shutdown")
async def startup():
    bot_manager = BotManager()

    await bot_manager.bot_stop()
