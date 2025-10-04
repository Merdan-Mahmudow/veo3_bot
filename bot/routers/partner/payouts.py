from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from bot.routers.partner import PartnerFilter
from config import ENV

router = Router()
backend = BackendAPI(ENV().bot_api_token)

class PayoutRequestState(StatesGroup):
    waiting_for_amount = State()
    waiting_for_requisites = State()

@router.callback_query(F.data == "partner_payouts", PartnerFilter())
async def payouts_start(callback: types.CallbackQuery, state: FSMContext):
    try:
        # Получаем баланс и историю заявок
        balance_data = await backend.get_partner_dashboard(callback.from_user.id)
        history = await backend.get_payout_history(callback.from_user.id)

        balance_rub = balance_data.get('balance_minor', 0) / 100

        message_text = f"💸 **Выплаты**\n\n**Текущий баланс:** `{balance_rub:.2f} RUB`\n\n"

        if not history:
            message_text += "У вас пока нет истории заявок на выплату."
        else:
            message_text += "📜 **История заявок:**\n"
            for req in history:
                amount_rub = req['amount_minor'] / 100
                status = req['status'].upper()
                message_text += f"- `{req['created_at']}`: {amount_rub:.2f} RUB, Статус: **{status}**\n"

        kb = InlineKeyboardBuilder()
        if balance_rub > 0: # Показывать кнопку, только если есть что выводить
            kb.button(text="💰 Запросить выплату", callback_data="payout_request_new")
        kb.button(text="⬅️ Назад в кабинет", callback_data="partner_cabinet")
        kb.adjust(1)

        await callback.message.edit_text(
            message_text,
            parse_mode="Markdown",
            reply_markup=kb.as_markup()
        )
        await callback.answer()

    except Exception as e:
        await callback.answer(f"Ошибка при загрузке данных о выплатах: {e}", show_alert=True)

@router.callback_query(F.data == "payout_request_new", PartnerFilter())
async def payout_request_new(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Введите сумму для вывода в рублях (например, 1500.50):")
    await state.set_state(PayoutRequestState.waiting_for_amount)
    await callback.answer()

@router.message(PayoutRequestState.waiting_for_amount, PartnerFilter())
async def payout_amount_received(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text.strip().replace(',', '.'))
        if amount <= 0:
            raise ValueError("Сумма должна быть положительной")

        await state.update_data(amount_minor=int(amount * 100))
        await message.answer("Теперь введите реквизиты для выплаты (например, номер карты или кошелька):")
        await state.set_state(PayoutRequestState.waiting_for_requisites)

    except ValueError:
        await message.answer("Неверный формат суммы. Введите число, например: 1500.50")

@router.message(PayoutRequestState.waiting_for_requisites, PartnerFilter())
async def payout_requisites_received(message: types.Message, state: FSMContext):
    requisites = message.text.strip()
    data = await state.get_data()
    amount_minor = data.get("amount_minor")

    try:
        await backend.request_payout(message.from_user.id, amount_minor, {"details": requisites})
        await message.answer(
            "✅ **Ваша заявка на выплату успешно создана!**\n\n"
            "Администратор рассмотрит ее в ближайшее время.",
            reply_markup=InlineKeyboardBuilder().button(text="⬅️ В кабинет", callback_data="partner_cabinet").as_markup()
        )
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Не удалось создать заявку: {e}")
        await state.clear()