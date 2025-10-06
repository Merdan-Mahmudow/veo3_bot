from aiogram import Router, F, types
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext

from config import Settings
from .users import router as users_router
from .partners import router as partners_router
from .requests import router as requests_router
from .filters import AdminFilter

router = Router()
router.include_router(users_router)
router.include_router(partners_router)
router.include_router(requests_router)
settings = Settings()

def admin_main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="👤 Управление пользователями", callback_data="admin_users")
    kb.button(text="🤝 Партнеры", callback_data="admin_partners")
    kb.button(text="📬 Заявки", callback_data="admin_requests")
    kb.button(text="📊 Отчеты", callback_data="admin_reports")
    kb.button(text="⬅️ Назад в главное меню", callback_data="start_back")
    kb.adjust(1)
    return kb.as_markup()

@router.callback_query(F.data == "admin_reports", AdminFilter())
async def admin_reports_stub(callback: types.CallbackQuery):
    await callback.answer("Раздел отчетов находится в разработке.", show_alert=True)

@router.callback_query(F.data == "admin_panel", AdminFilter())
async def admin_panel_entry(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Добро пожаловать в панель администратора!",
        reply_markup=admin_main_keyboard()
    )
    await callback.answer()

# Обработчик для кнопки "Назад" в админ-панели, доступный глобально
@router.callback_query(F.data == "admin_panel_main", AdminFilter())
async def back_to_admin_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Добро пожаловать в панель администратора!",
        reply_markup=admin_main_keyboard()
    )
    await callback.answer()