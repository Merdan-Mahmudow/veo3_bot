from __future__ import annotations
import json
from aiogram import Router, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import LabeledPrice, PreCheckoutQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.fsm import PaymentState
from bot.api import BackendAPI
from config import ENV
env = ENV()

router = Router()

backend = BackendAPI(env.bot_api_token)


CURRENCY = "RUB"
PROVIDER_TOKEN = env.test_payment_token

PLANS: dict[int, tuple[str, int]] = {
    1:  ("1 генерация", 88),
    5:  ("5 генераций", 388),
    10: ("10 генераций", 666),
    50: ("50 генераций", 2999),
}

def rub_to_kopeks(rub: int | float) -> int:
    return int(round(float(rub) * 100))

def payment_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    for coins, (label, price_rub) in PLANS.items():
        kb.button(
            text=f"{label} — {price_rub}₽",
            callback_data=f"pay_gens:{coins}"
        )
    kb.adjust(1, 1, 1, 1)
    return kb.as_markup()


# ---------- Точка входа в оплату ----------

@router.message(PaymentState.choosing_plan)
async def payment_menu(message: types.Message, state: FSMContext):
    await message.answer("Выберите количество генераций:", reply_markup=payment_keyboard())

# ---------- Выбор тарифа → инвойс ----------

@router.callback_query(F.data.startswith("pay_gens:"))
async def pay_gens(callback: types.CallbackQuery):
    try:
        _, coins_str = callback.data.split(":")
        coins = int(coins_str)
    except Exception:
        await callback.answer("Неверный тариф", show_alert=True)
        return

    if coins not in PLANS:
        await callback.answer("Такого тарифа нет", show_alert=True)
        return

    label, price_rub = PLANS[coins]
    price_kop = rub_to_kopeks(price_rub)

    payload = f"buy:gens:{coins}"  # используем как ключ тарифа
    title = f"Покупка {label}"
    description = f"Пополнение баланса на {label.lower()} для бота."

    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=payload,
        currency=CURRENCY,
        provider_token=PROVIDER_TOKEN,
        prices=[LabeledPrice(label=label, amount=price_kop)],
        start_parameter=f"pay_{coins}",
        need_email=True,
        send_email_to_provider=True,
    )
    await callback.answer()

@router.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    """
    Можно дополнительно валидировать payload/сумму.
    Здесь просто подтверждаем.
    """
    print("hello its working")
    # *Если* хотите жёстко валидировать сумму:
    # expected_kop = expected_amount_from_payload(pre_checkout_query.invoice_payload)
    # ok = (pre_checkout_query.total_amount == expected_kop and pre_checkout_query.currency == CURRENCY)
    # await pre_checkout_query.answer(ok=ok, error_message="Сумма неверна") ; return
    await pre_checkout_query.answer(ok=True)
    return 


# ---------- Успешный платёж ----------

# Простейшая идемпотентность в памяти процесса (на случай ретраев Telegram)
_processed_payments: set[str] = set()

def expected_amount_from_payload(payload: str) -> tuple[int, int] | None:
    """
    Возвращает (coins, expected_kop) или None.
    """
    if not payload or not payload.startswith("buy:gens:"):
        return None
    try:
        coins = int(payload.split(":")[-1])
        if coins in PLANS:
            _, price_rub = PLANS[coins]
            return coins, rub_to_kopeks(price_rub)
    except Exception:
        pass
    return None

@router.message(F.successful_payment)
async def successful_payment(message: types.Message):
    sp = message.successful_payment
    payload = sp.invoice_payload
    total = sp.total_amount
    currency = sp.currency

    # Защита от повторного засчёта
    payment_id = sp.telegram_payment_charge_id or sp.provider_payment_charge_id or f"{message.chat.id}:{payload}:{total}"
    if payment_id in _processed_payments:
        await message.answer("Оплата уже учтена ✅")
        return

    # Валидация суммы/тарифа
    exp = expected_amount_from_payload(payload)
    if not exp:
        await message.answer("Оплата получена, но тариф не распознан. Напишите @softp04")
        return
    coins, expected_kop = exp

    if currency != CURRENCY or total != expected_kop:
        await message.answer("Оплата получена, но сумма не совпадает с тарифом. Напишите @softp04")
        return

    # Кредитуем монеты через backend
    try:
        new_coins = await backend.plus_coins(message.from_user.id, count=coins)
    except Exception:
        await message.answer("Платёж прошёл, но пополнить баланс не удалось. Напишите @softp04, укажи этот код: PAY-APPLY-ERR")
        return

    _processed_payments.add(payment_id)

    await message.answer(
        f"💳 Оплата успешно проведена!\n"
        f"➕ Начислено: {coins} генераций\n"
        f"💼 Текущий баланс: {new_coins} генераций"
    )
