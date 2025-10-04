from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from bot.routers.admin import AdminFilter
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)

class PartnerLinkState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_percent = State()
    waiting_for_comment = State()

def partner_percent_keyboard():
    kb = InlineKeyboardBuilder()
    for i in range(10, 51, 10):
        kb.button(text=f"{i}%", callback_data=f"partner_set_percent:{i}")
    kb.button(text="⬅️ Отмена", callback_data="admin_partners")
    kb.adjust(5, 1)
    return kb.as_markup()

@router.callback_query(F.data == "admin_partners", AdminFilter())
async def manage_partners_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Введите ID пользователя (не Chat ID), которому нужно создать партнерскую ссылку:",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data="admin_panel_main").as_markup()
    )
    await state.set_state(PartnerLinkState.waiting_for_user_id)
    await callback.answer()

@router.message(PartnerLinkState.waiting_for_user_id, AdminFilter())
async def partner_user_id_received(message: types.Message, state: FSMContext):
    user_id = message.text.strip()
    # Простая валидация UUID
    if len(user_id) != 36:
        await message.answer("Неверный формат User ID. Попробуйте еще раз.")
        return

    await state.update_data(partner_user_id=user_id)
    await message.answer("Выберите процент для партнерской ссылки:", reply_markup=partner_percent_keyboard())
    await state.set_state(PartnerLinkState.waiting_for_percent)

@router.callback_query(F.data.startswith("partner_set_percent:"), PartnerLinkState.waiting_for_percent, AdminFilter())
async def partner_percent_received(callback: types.CallbackQuery, state: FSMContext):
    percent = int(callback.data.split(":")[1])
    await state.update_data(percent=percent)

    await callback.message.edit_text("Теперь введите комментарий для этой ссылки (например, 'Кампания в VK'):")
    await state.set_state(PartnerLinkState.waiting_for_comment)
    await callback.answer()

@router.message(PartnerLinkState.waiting_for_comment, AdminFilter())
async def partner_comment_received(message: types.Message, state: FSMContext):
    comment = message.text.strip()
    data = await state.get_data()
    user_id = data.get("partner_user_id")
    percent = data.get("percent")

    try:
        # Предполагаем, что в BackendAPI будет метод для создания партнерской ссылки
        link_data = await backend.create_partner_link(user_id, percent, comment)

        link_url = f"https://t.me/{ENV().BOT_USERNAME}?start={link_data.get('token')}"

        await message.answer(
            f"✅ **Партнерская ссылка успешно создана!**\n\n"
            f"**Владелец:** `{user_id}`\n"
            f"**Процент:** `{percent}%`\n"
            f"**Комментарий:** `{comment}`\n\n"
            f"🔗 **Ссылка:**\n`{link_url}`",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardBuilder().button(text="🏠 Главное меню админ-панели", callback_data="admin_panel_main").as_markup()
        )
        await state.clear()

    except Exception as e:
        await message.answer(f"❌ Не удалось создать ссылку: {e}")
        await state.clear()