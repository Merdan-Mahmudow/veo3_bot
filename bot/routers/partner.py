from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.api import BackendAPI
from bot.fsm import PartnerState
from config import ENV

env = ENV()
router = Router()
backend = BackendAPI(env.bot_api_token)

def partner_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="Статистика", callback_data="partner_stats")
    kb.button(text="Создать ссылку", callback_data="partner_create_link")
    kb.button(text="Запросить выплату", callback_data="partner_payout")
    kb.adjust(1, 1, 1)
    return kb.as_markup()

@router.callback_query(F.data == "partner")
async def partner_menu(callback: types.CallbackQuery, state: FSMContext):
    partner = await backend.get_partner_by_chat_id(callback.from_user.id)
    if partner and partner.get("is_verified"):
        await callback.message.answer(
            "Добро пожаловать в кабинет партнера!",
            reply_markup=partner_keyboard()
        )
    else:
        await callback.message.answer("У вас нет доступа к кабинету партнера.")
    await callback.answer()

@router.callback_query(F.data == "partner_stats")
async def partner_stats(callback: types.CallbackQuery, state: FSMContext):
    partner = await backend.get_partner_by_chat_id(callback.from_user.id)
    if not partner:
        await callback.answer("Партнер не найден.", show_alert=True)
        return

    stats = await backend.get_partner_stats(partner["id"])
    if not stats:
        await callback.answer("Не удалось загрузить статистику.", show_alert=True)
        return

    await callback.message.edit_text(
        f"📊 Ваша статистика:\n"
        f"  - Регистраций: {stats['registrations']}\n"
        f"  - Оплат: {stats['payments']}\n"
        f"  - Заработано: {stats['total_earnings']:.2f} RUB",
        reply_markup=partner_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "partner_create_link")
async def create_link_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(PartnerState.creating_link)
    await callback.message.edit_text("Введите процент для новой реферальной ссылки (10-50%).")
    await callback.answer()

@router.message(PartnerState.creating_link)
async def create_link_process(message: types.Message, state: FSMContext):
    try:
        percentage = int(message.text)
        if not 10 <= percentage <= 50:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите число от 10 до 50.")
        return

    partner = await backend.get_partner_by_chat_id(message.from_user.id)
    if not partner:
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
        return

    link_data = await backend.create_referral_link(partner["id"], percentage)
    if not link_data:
        await message.answer("Не удалось создать ссылку. Попробуйте позже.")
        await state.clear()
        return

    await message.answer(
        f"✅ Ваша новая реферальная ссылка:\n`{link_data['link']}`",
        parse_mode="Markdown"
    )
    await state.clear()

@router.callback_query(F.data == "partner_payout")
async def payout_start(callback: types.CallbackQuery, state: FSMContext):
    partner = await backend.get_partner_by_chat_id(callback.from_user.id)
    if not partner:
        await callback.answer("Партнер не найден.", show_alert=True)
        return

    await state.set_state(PartnerState.requesting_payout)
    await callback.message.edit_text(f"Ваш баланс: {partner['balance']:.2f} RUB. Введите сумму для вывода:")
    await callback.answer()

@router.message(PartnerState.requesting_payout)
async def payout_process(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Пожалуйста, введите корректную сумму.")
        return

    partner = await backend.get_partner_by_chat_id(message.from_user.id)
    if not partner:
        await message.answer("Произошла ошибка. Попробуйте снова.")
        await state.clear()
        return

    if amount > partner['balance']:
        await message.answer("Недостаточно средств на балансе.")
        return

    payout_data = await backend.request_payout(partner["id"], amount)
    if not payout_data:
        await message.answer("Не удалось создать заявку на выплату. Попробуйте позже.")
        await state.clear()
        return

    await message.answer("✅ Заявка на выплату успешно создана. Администратор скоро свяжется с вами.")
    await state.clear()