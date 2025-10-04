from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from bot.api import BackendAPI
from config import ENV
from .links import router as links_router
from .payouts import router as payouts_router

router = Router()
router.include_router(links_router)
router.include_router(payouts_router)
backend = BackendAPI(ENV().bot_api_token)

class PartnerFilter(F.Filter):
    async def __call__(self, message_or_callback: types.Message | types.CallbackQuery) -> bool:
        # В реальном приложении проверка роли должна быть надежнее,
        # например, через запрос к API или кеширование роли в FSM/Redis.
        # Для простоты пока оставим так.
        try:
            user = await backend.get_user(message_or_callback.from_user.id)
            return user.get("role") == "partner"
        except Exception:
            return False

def partner_main_keyboard():
    kb = types.InlineKeyboardBuilder()
    kb.button(text="📊 Дашборд", callback_data="partner_dashboard")
    kb.button(text="🔗 Мои ссылки", callback_data="partner_links")
    kb.button(text="💸 Выплаты", callback_data="partner_payouts")
    kb.button(text="📈 Отчеты", callback_data="partner_reports")
    kb.button(text="⬅️ Назад в главное меню", callback_data="start_back")
    kb.adjust(1)
    return kb.as_markup()

@router.callback_query(F.data == "partner_reports", PartnerFilter())
async def partner_reports_stub(callback: types.CallbackQuery):
    await callback.answer("Раздел отчетов находится в разработке.", show_alert=True)

@router.callback_query(F.data == "partner_cabinet", PartnerFilter())
async def partner_cabinet_entry(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    try:
        dashboard_data = await backend.get_partner_dashboard(callback.from_user.id)

        balance_rub = dashboard_data.get('balance_minor', 0) / 100
        commission_total_rub = dashboard_data.get('total_commission_minor', 0) / 100

        message_text = (
            "🤝 **Кабинет партнера**\n\n"
            "**Ваш дашборд:**\n"
            f"- Регистраций (всего): `{dashboard_data.get('total_referrals', 0)}`\n"
            f"- Всего оплат: `{dashboard_data.get('total_purchases', 0)}`\n"
            f"- Сумма комиссий: `{commission_total_rub:.2f} RUB`\n"
            f"- Текущий баланс: `{balance_rub:.2f} RUB`\n"
        )

        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=partner_main_keyboard()
        )
    except Exception as e:
        await callback.answer(f"Не удалось загрузить данные дашборда: {e}", show_alert=True)
        # В случае ошибки показываем базовое меню
        await callback.message.edit_text(
            "Не удалось загрузить данные. Попробуйте позже.",
            reply_markup=partner_main_keyboard()
        )

    await callback.answer()

# Обработчик для кнопки "Дашборд" (пока просто дублирует вход)
@router.callback_query(F.data == "partner_dashboard", PartnerFilter())
async def partner_dashboard_show(callback: types.CallbackQuery, state: FSMContext):
    await partner_cabinet_entry(callback, state)