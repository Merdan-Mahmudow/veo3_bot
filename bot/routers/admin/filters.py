from aiogram import F, types
from config import Settings
from aiogram.filters import Filter


settings = Settings()

# Фильтр для проверки, является ли пользователь администратором
class AdminFilter(Filter):
    def __call__(self, message_or_callback: types.Message | types.CallbackQuery) -> bool:
        return message_or_callback.from_user.id in settings.get_admins_chat_id()
