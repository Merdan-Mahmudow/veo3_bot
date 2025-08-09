from __future__ import annotations

from aiogram import Bot, Dispatcher
from config import ENV
from bot import routers

class BotManager:
    def __init__(self):
        self.env = ENV()
        self.bot = Bot(token=self.env.BOT_TOKEN)
        self.dp = Dispatcher()
        self.webhook_endpoint = self.env.webhook_endpoint

    def add_routes(self):
        self.dp.include_router(routers.router)

    
    async def bot_start(self):
        await self.bot.set_webhook(self.webhook_endpoint)

    async def bot_stop(self):
        await self.bot.delete_webhook()
        await self.bot.session.close()