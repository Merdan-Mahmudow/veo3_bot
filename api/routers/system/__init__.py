from fastapi import Request
from aiogram.types import Update
from bot.manager import bot_manager

class SystemRoutesManager:
    def __init__(self):
        self.bot_dp = bot_manager.dp
        self.bot = bot_manager.bot
    
    async def webhook_updates(self, request: Request):
        data = await request.json()
        update = Update(**data)
        await self.bot_dp.feed_update(self.bot, update)
        return {"ok": True}