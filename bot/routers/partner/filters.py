from aiogram import types
from bot.api import BackendAPI
from config import ENV
from aiogram.filters import Filter

env = ENV()
backend = BackendAPI(api_key=env.bot_api_token)

class PartnerFilter(Filter):
    async def __call__(self, message_or_callback: types.Message | types.CallbackQuery) -> bool:
        # В реальном приложении проверка роли должна быть надежнее,
        # например, через запрос к API или кеширование роли в FSM/Redis.
        # Для простоты пока оставим так.
        try:
            user = await backend.get_user(message_or_callback.from_user.id)
            return user.get("role") == "partner"
        except Exception:
            return False
