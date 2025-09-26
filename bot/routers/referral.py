from aiogram import Router, types, F
from bot.api import BackendAPI
from config import ENV

env = ENV()
router = Router()
backend = BackendAPI(env.bot_api_token)

@router.message(F.text == "/referral")
async def referral_command(message: types.Message):
    user = await backend.get_user(message.from_user.id)
    if not user:
        await message.answer("Сначала зарегистрируйтесь с помощью /start")
        return

    # For simplicity, we'll use the user's ID to create a referral link.
    # In a real application, this should be a unique, generated code.
    referral_link = f"https://t.me/{env.bot_username}?start=ref_{user['id']}"

    await message.answer(
        "Пригласите друга и получите по 1 видео в подарок!\n\n"
        "Ваша реферальная ссылка:\n"
        f"`{referral_link}`"
    )