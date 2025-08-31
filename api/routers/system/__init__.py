from fastapi import Request
from aiogram.types import Update
from bot.manager import bot_manager

class SystemRoutesManager:
    def __init__(self):
        self.bot_dp = bot_manager.dp
        self.bot = bot_manager.bot
        self.api_manager = None
    
    async def webhook_updates(self, request: Request):
        data = await request.json()
        update = Update(**data)
        await self.bot_dp.feed_update(self.bot, update)
        return {"ok": True}
    
    def get_app(self):
        if self.api_manager is None:
            from api.app import FastAPIManager
            self.api_manager = FastAPIManager()
        return self.api_manager.get_app()