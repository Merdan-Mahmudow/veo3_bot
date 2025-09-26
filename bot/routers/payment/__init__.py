from __future__ import annotations
import logging
from typing import Literal
from aiogram import Router, types, F
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
CURRENCY_STARS = "XTR"
PROVIDER_TOKEN = env.test_payment_token if env.DEBUG else env.life_payment_token

PLANS: dict[int, tuple[str, int]] = {
    1:  ("1 генерация", 88),
    5:  ("5 генераций", 388),
    10: ("10 генераций", 666),
    50: ("50 генераций", 2999),
}
PLANS_STARS: dict[int, tuple[str, int]] = {
    1:  ("1 генерация", 77),
    5:  ("5 генераций", 349),
    10: ("10 генераций", 599),
    50: ("50 генераций", 2699),
}

def rub_to_kopeks(rub: int | float) -> int:
    return int(round(float(rub) * 100))

def select_method_keyboard() -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
#    kb.button(text="СБП", callback_data="direct_pay")
    kb.button(text="Картой / SberPay", callback_data="buy_coins")
    kb.button(text="Telegram Stars", callback_data="stars_pay")
    kb.adjust(1, 1, 1)
    return kb.as_markup()
    
def sbp_url_button(url: str, amount: str) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    kb.button(text=f"Заплатить {amount} RUB", url=url.replace('"', ''))
    kb.adjust(1)
    return kb.as_markup()

def payment_keyboard(type: Literal["direct", "stars", "internal"]) -> types.InlineKeyboardMarkup:
    kb = InlineKeyboardBuilder()
    if type == "internal":
        for coins, (label, price_rub) in PLANS.items():
            kb.button(
                text=f"{label} — {price_rub}₽",
                callback_data=f"pay_gens:{coins}"
            )
    elif type == "direct":
        for coins, (label, price_rub) in PLANS.items():
            kb.button(
                text=f"{label} — {price_rub}₽",
                callback_data=f"pay_gens_direct:{coins}"
            )
    elif type == "stars":
        for coins, (label, price_rub) in PLANS_STARS.items():
            kb.button(
                text=f"{label} — {price_rub}🌟",
                callback_data=f"pay_gens_stars:{coins}"
            )
    kb.button(text="Назад", callback_data="start_back")
    kb.adjust(1, 1, 1, 1, 1)
    return kb.as_markup()


@router.callback_query(F.data == "select_pay_method")
async def select_payment_method(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentState.choosing_method)
    await callback.message.answer(
        "Выберите способ оплаты.",
        reply_markup=select_method_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "buy_coins")
async def buy_coins_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentState.choosing_plan)
    await callback.message.answer(
        "Выберите тариф для пополнения баланса генераций:",
        reply_markup=payment_keyboard("internal")
    )
    await callback.answer()
@router.callback_query(F.data == "stars_pay")
async def buy_coins_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentState.choosing_plan)
    await callback.message.answer(
        "Выберите тариф для пополнения баланса генераций:",
        reply_markup=payment_keyboard("stars")
    )
    await callback.answer()
@router.callback_query(F.data == "direct_pay")
async def buy_coins_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PaymentState.choosing_plan)
    await callback.message.answer(
        "Выберите тариф для пополнения баланса генераций:",
        reply_markup=payment_keyboard("direct")
    )
    await callback.answer()

# ---------- Выбор тарифа → инвойс ----------

@router.callback_query(F.data.startswith("pay_gens_stars:"))
async def pay_gens_stars(callback: types.CallbackQuery):
    await callback.answer()  # 1) ACK СРАЗУ
    try:
        _, coins_str = callback.data.split(":")
        coins = int(coins_str)
    except Exception:
        return await callback.answer("Неверный тариф", show_alert=True)

    if coins not in PLANS_STARS:
        return await callback.answer("Такого тарифа нет", show_alert=True)

    label, amount_stars = PLANS_STARS[coins]
    await callback.message.answer_invoice(
        title=f"Покупка {label}",
        description=f"Пополнение баланса на {label.lower()} для бота.",
        payload=f"buy:stars:{coins}",  # 2) payload для XTR
        currency=CURRENCY_STARS,       # "XTR"
        prices=[LabeledPrice(label=label, amount=amount_stars)],  # ровно 1 item
        start_parameter=f"pay_stars_{coins}",
    )

@router.callback_query(F.data.startswith("pay_gens:"))
async def pay_gens(callback: types.CallbackQuery):
    await callback.answer()
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

@router.callback_query(F.data.startswith("pay_gens_direct:"))
async def pay_gens_direct(callback: types.CallbackQuery):
    await callback.answer()
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
    description = f"Пополнение баланса на {label.lower()} для бота."
    payload = f"{callback.from_user.id}:{callback.from_user.username}:{coins}"


    url = await backend.get_sbp_url(amount=f"{price_rub}.00", desc=payload) or ""
    await callback.message.answer(description, reply_markup=sbp_url_button(url=url, amount=f"{price_rub}.00"))
    


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

def back_to_start():
    kb = InlineKeyboardBuilder()
    kb.button(text="На главную", callback_data="start_back")
    return kb.as_markup()

@router.message(F.successful_payment)
async def successful_payment(message: types.Message):
    sp = message.successful_payment
    payload = sp.invoice_payload
    total = sp.total_amount
    currency = sp.currency

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

    # Process referral rewards
    try:
        await backend.process_referral_payment(message.from_user.id, float(total / 100))
    except Exception as e:
        logging.error(f"Failed to process referral for payment {payment_id}: {e}")

    await message.answer(
        f"💳 Оплата успешно проведена!\n"
        f"➕ Начислено генераций: {coins}\n"
        f"💼 Текущий баланс: {new_coins} генераций",
        reply_markup=back_to_start() 
    )
