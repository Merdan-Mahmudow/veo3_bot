from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)

@router.callback_query(F.data == "my_referral_link")
async def show_my_referral_link(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Этот метод нужно будет создать в BackendAPI и на бэкенде
        ref_data = await backend.get_my_referral_info(callback.from_user.id)

        link = ref_data.get("link")
        if not link or not link.get("token"):
            await callback.answer("Ваша реферальная ссылка еще не создана. Попробуйте позже.", show_alert=True)
            return

        link_url = f"https://t.me/{ENV().BOT_USERNAME}?start={link.get('token')}"

        message_text = (
            "🔗 **Ваша реферальная ссылка**\n\n"
            "Пригласите друга, и после его **первой покупки** вы оба получите **1 бесплатную генерацию**!\n\n"
            f"Ваша ссылка:\n`{link_url}`\n\n"
            "**Статистика:**\n"
            f"- Друзей приглашено: `{ref_data.get('referrals_count', 0)}`\n"
            f"- Друзей совершили покупку: `{ref_data.get('referrals_purchased', 0)}`\n"
            f"- Бонусов получено: `{ref_data.get('bonuses_earned', 0)}`\n"
        )

        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Назад", callback_data="start_back")

        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Не удалось получить информацию о ссылке: {e}", show_alert=True)