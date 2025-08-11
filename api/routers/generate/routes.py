from fastapi import APIRouter
from bot.manager import bot_manager


router = APIRouter()

@router.post("/msg_test")
async def send_message_to_bot(chat_id: int):
    await bot_manager.bot.send_message(chat_id, text="Hello its from FastAPI")