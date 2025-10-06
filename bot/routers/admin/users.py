from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from .filters import AdminFilter
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)

class AdminUserState(StatesGroup):
    waiting_for_user_identifier = State()
    showing_user_profile = State()


def user_profile_keyboard(user_id: str, current_role: str):
    kb = InlineKeyboardBuilder()
    if current_role != 'partner':
        kb.button(text="Назначить партнером", callback_data=f"user_set_role:partner:{user_id}")
    else:
        kb.button(text="Снять роль партнера", callback_data=f"user_set_role:user:{user_id}")

    if current_role != 'admin':
        kb.button(text="Назначить администратором", callback_data=f"user_set_role:admin:{user_id}")
    else:
        kb.button(text="Снять роль администратора", callback_data=f"user_set_role:user:{user_id}")

    kb.button(text="⬅️ Назад к поиску", callback_data="admin_users")
    kb.button(text="🏠 Главное меню админ-панели", callback_data="admin_panel_main")
    kb.adjust(2, 1, 1)
    return kb.as_markup()

@router.callback_query(F.data == "admin_users", AdminFilter())
async def manage_users_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Введите Telegram Chat ID или никнейм пользователя для поиска:",
        reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data="admin_panel_main").as_markup()
    )
    await state.set_state(AdminUserState.waiting_for_user_identifier)
    await callback.answer()

@router.message(AdminUserState.waiting_for_user_identifier, AdminFilter())
async def find_user_by_identifier(message: types.Message, state: FSMContext):
    identifier = message.text.strip()
    try:
        # Предполагаем, что в BackendAPI будет метод для поиска пользователя
        user_data = await backend.find_user(identifier)
        if not user_data:
            await message.answer("Пользователь не найден. Попробуйте еще раз или вернитесь назад.",
                                 reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data="admin_users").as_markup())
            return

        user_id = user_data.get("id")
        role = user_data.get("role", "user")

        profile_text = (
            f"👤 **Профиль пользователя**\n\n"
            f"**ID:** `{user_data.get('id')}`\n"
            f"**Chat ID:** `{user_data.get('chat_id')}`\n"
            f"**Никнейм:** `{user_data.get('nickname')}`\n"
            f"**Роль:** `{role.upper()}`\n"
            f"**Генераций:** `{user_data.get('coins')}`\n\n"
            f"**Источник привлечения:**\n"
            f"  - **Тип:** `{user_data.get('referrer_type')}`\n"
            f"  - **ID реферера:** `{user_data.get('referrer_id')}`\n"
            f"  - **ID ссылки:** `{user_data.get('ref_link_id')}`"
        )

        await state.update_data(found_user_id=user_id, current_role=role)
        await message.answer(profile_text, parse_mode="Markdown", reply_markup=user_profile_keyboard(user_id, role))
        await state.set_state(AdminUserState.showing_user_profile)

    except Exception as e:
        await message.answer(f"Произошла ошибка при поиске: {e}")


@router.callback_query(F.data.startswith("user_set_role:"), AdminUserState.showing_user_profile, AdminFilter())
async def set_user_role(callback: types.CallbackQuery, state: FSMContext):
    _, role_to_set, user_id_str = callback.data.split(":")

    try:
        # Предполагаем, что в BackendAPI будет метод для смены роли
        await backend.set_user_role(user_id_str, role_to_set)

        await callback.answer(f"Роль пользователя успешно изменена на {role_to_set.upper()}", show_alert=True)

        # Обновляем профиль пользователя, чтобы показать новую роль
        user_data = await backend.get_user_by_id(user_id_str)
        role = user_data.get("role", "user")

        profile_text = (
            f"👤 **Профиль пользователя**\n\n"
            f"**ID:** `{user_data.get('id')}`\n"
            f"**Chat ID:** `{user_data.get('chat_id')}`\n"
            f"**Никнейм:** `{user_data.get('nickname')}`\n"
            f"**Роль:** `{role.upper()}`\n"
            f"**Генераций:** `{user_data.get('coins')}`\n\n"
            f"**Источник привлечения:**\n"
            f"  - **Тип:** `{user_data.get('referrer_type')}`\n"
            f"  - **ID реферера:** `{user_data.get('referrer_id')}`\n"
            f"  - **ID ссылки:** `{user_data.get('ref_link_id')}`"
        )

        await state.update_data(found_user_id=user_id_str, current_role=role)
        await callback.message.edit_text(profile_text, parse_mode="Markdown", reply_markup=user_profile_keyboard(user_id_str, role))

    except Exception as e:
        await callback.answer(f"Ошибка при смене роли: {e}", show_alert=True)