from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from .filters import AdminFilter
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)


def requests_main_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 На выплату", callback_data="admin_req_payouts")
    kb.button(text="🔗 На новые ссылки", callback_data="admin_req_links") # Этот раздел пока не реализован
    kb.button(text="⬅️ Назад", callback_data="admin_panel_main")
    kb.adjust(2, 1)
    return kb.as_markup()

@router.callback_query(F.data == "admin_requests", AdminFilter())
async def manage_requests_start(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "Выберите тип заявок для просмотра:",
        reply_markup=requests_main_keyboard()
    )
    await callback.answer()

def payout_requests_keyboard(requests: list):
    kb = InlineKeyboardBuilder()
    for req in requests:
        # Кнопки для каждой заявки
        kb.button(text=f"✅ Одобрить (ID: {req['id'][:8]})", callback_data=f"payout_approve:{req['id']}")
        kb.button(text=f"❌ Отклонить (ID: {req['id'][:8]})", callback_data=f"payout_reject:{req['id']}")
    kb.button(text="🔄 Обновить", callback_data="admin_req_payouts")
    kb.button(text="⬅️ Назад", callback_data="admin_requests")
    kb.adjust(2) # По 2 кнопки в ряд для одобрения/отклонения
    kb.adjust(1, 1) # Кнопки "Обновить" и "Назад" по одной в ряду
    return kb.as_markup()

@router.callback_query(F.data == "admin_req_payouts", AdminFilter())
async def list_payout_requests(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Получаем только заявки в статусе 'requested'
        requests = await backend.get_payout_requests("requested")

        if not requests:
            await callback.message.edit_text(
                "Активных заявок на выплату нет.",
                reply_markup=InlineKeyboardBuilder().button(text="⬅️ Назад", callback_data="admin_requests").as_markup()
            )
            await callback.answer()
            return

        message_text = "💰 **Активные заявки на выплату:**\n\n"
        for req in requests:
            amount_rub = req['amount_minor'] / 100
            message_text += (
                f"**ID:** `{req['id']}`\n"
                f"**Партнер ID:** `{req['partner_id']}`\n"
                f"**Сумма:** `{amount_rub:.2f} RUB`\n"
                f"**Реквизиты:** `{req['requisites_json']}`\n"
                f"**Дата:** `{req['created_at']}`\n"
                f"-------------------\n"
            )

        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=payout_requests_keyboard(requests)
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Ошибка при получении заявок: {e}", show_alert=True)


@router.callback_query(F.data.startswith("payout_approve:"), AdminFilter())
async def approve_payout_request(callback: types.CallbackQuery, state: FSMContext):
    request_id = callback.data.split(":")[1]
    try:
        await backend.approve_payout_request(request_id)
        await callback.answer("✅ Заявка одобрена!", show_alert=True)
        # Обновляем список, чтобы убрать обработанную заявку
        await list_payout_requests(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка при одобрении: {e}", show_alert=True)


@router.callback_query(F.data.startswith("payout_reject:"), AdminFilter())
async def reject_payout_request(callback: types.CallbackQuery, state: FSMContext):
    request_id = callback.data.split(":")[1]
    try:
        await backend.reject_payout_request(request_id)
        await callback.answer("❌ Заявка отклонена!", show_alert=True)
        # Обновляем список
        await list_payout_requests(callback, state)
    except Exception as e:
        await callback.answer(f"Ошибка при отклонении: {e}", show_alert=True)


# Заглушка для заявок на ссылки
@router.callback_query(F.data == "admin_req_links", AdminFilter())
async def list_link_requests(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Раздел для заявок на ссылки в разработке.", show_alert=True)