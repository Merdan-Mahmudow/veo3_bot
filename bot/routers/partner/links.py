from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from bot.api import BackendAPI
from .filters import PartnerFilter
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)

@router.callback_query(F.data == "partner_links", PartnerFilter())
async def list_partner_links(callback: types.CallbackQuery, state: FSMContext):
    try:
        links = await backend.get_partner_links(callback.from_user.id)

        if not links:
            message_text = "У вас пока нет партнерских ссылок."
        else:
            message_text = "🔗 **Ваши партнерские ссылки:**\n\n"
            for link in links:
                link_url = f"https://t.me/{ENV().BOT_USERNAME}?start={link.get('token')}"
                message_text += (
                    f"**Комментарий:** {link.get('comment', 'N/A')}\n"
                    f"**Процент:** {link.get('percent')}%\n"
                    f"**Ссылка:** `{link_url}`\n"
                    f"-------------------\n"
                )

        kb = types.InlineKeyboardBuilder()
        # TODO: Реализовать функционал запроса новой ссылки
        kb.button(text="➕ Запросить новую ссылку", callback_data="partner_request_link")
        kb.button(text="⬅️ Назад в кабинет", callback_data="partner_cabinet")
        kb.adjust(1)

        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=kb.as_markup(),
            disable_web_page_preview=True
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Ошибка при получении ссылок: {e}", show_alert=True)

# Заглушка для запроса новой ссылки
@router.callback_query(F.data == "partner_request_link", PartnerFilter())
async def request_new_link(callback: types.CallbackQuery):
    await callback.answer("Функционал запроса новых ссылок в разработке.", show_alert=True)