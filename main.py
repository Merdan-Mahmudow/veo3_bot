from __future__ import annotations
import asyncio

from aiogram import Bot, Dispatcher
from config import ENV
import routers

env = ENV()
bot = Bot(token=env.BOT_TOKEN)
dp = Dispatcher()

async def main():
    dp.include_router(routers.router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

