import logging
from aiogram import F, Router, types
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.api import BackendAPI
from config import ENV

router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)


def referral_user_keyboard(link: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="Скопировать ссылку", callback_data=f"copy_link:{link}")
    kb.button(text="Назад", callback_data="start_back")
    kb.adjust(1)
    return kb.as_markup()

def partner_cabinet_keyboard():
    kb = InlineKeyboardBuilder()
    kb.button(text="💰 Запросить выплату", callback_data="payout_request")
    kb.button(text="🔗 Мои ссылки", callback_data="partner_links")
    kb.button(text="➕ Запросить новую ссылку", callback_data="request_new_link")
    kb.button(text="Назад", callback_data="start_back")
    kb.adjust(2, 1, 1)
    return kb.as_markup()

async def _show_admin_panel(callback: types.CallbackQuery):
    """Helper function to render the admin panel with pending payout requests."""
    try:
        requests = await backend.list_payout_requests(
            actor_chat_id=str(callback.from_user.id),
            status="requested"
        )

        text = "<b>Активные заявки на выплату:</b>\n"
        kb = InlineKeyboardBuilder()

        if not requests:
            text = "✅ Нет активных заявок на выплату."
        else:
            for i, req in enumerate(requests, 1):
                payout_id = req.get('id')
                amount = req.get('amount_minor', 0) / 100
                partner_id_short = req.get('partner_id', 'N/A')[:8]
                requisites = req.get('requisites_json', {}).get('details', 'Не указаны')

                text += (
                    f"\n\n➖➖➖ <b>Заявка #{i}</b> ➖➖➖\n"
                    f"<b>ID:</b> <code>{payout_id}</code>\n"
                    f"<b>Партнер:</b> <code>{partner_id_short}</code>\n"
                    f"<b>Сумма:</b> {amount:,.2f} ₽\n"
                    f"<b>Реквизиты:</b> {requisites}"
                )

                approve_data = f"payout_approve:{payout_id}"
                reject_data = f"payout_reject:{payout_id}"

                kb.button(text=f"✅ Одобрить #{i}", callback_data=approve_data)
                kb.button(text=f"❌ Отклонить #{i}", callback_data=reject_data)

        # Adjust all approve/reject pairs to be on their own row
        kb.adjust(2)

        kb.row(types.InlineKeyboardButton(text="➕ Создать ссылку", callback_data="admin_create_link"))
        kb.row(types.InlineKeyboardButton(text="🔄 Обновить", callback_data="admin_panel_refresh"))
        kb.row(types.InlineKeyboardButton(text="Назад", callback_data="start_back"))

        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())

    except Exception as e:
        logging.error(f"Failed to load admin panel for {callback.from_user.id}: {e}")
        await callback.message.edit_text("❌ Не удалось загрузить админ-панель.", reply_markup=partner_cabinet_keyboard())


@router.callback_query(F.data == "referral_program")
async def referral_program_entry(callback: types.CallbackQuery):
    """
    Handles the entry point for the referral program section.
    Displays different information based on the user's role.
    """
    await callback.answer()
    chat_id = callback.from_user.id

    try:
        user = await backend.get_user(chat_id)
        user_role = user.get("role")
        user_id = user.get("id")

        if user_role == "partner":
            stats = await backend.get_partner_stats(user_id)
            regs = stats.get("registrations_count", 0)
            commission = stats.get("total_commission_minor", 0) / 100

            text = (
                "**Кабинет партнёра**\n\n"
                f"📈 Регистраций по вашим ссылкам: **{regs}**\n"
                f"💰 Заработано комиссии: **{commission:,.2f} ₽**"
            )
            await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=partner_cabinet_keyboard())
        elif user_role == "admin":
             await _show_admin_panel(callback)
        else: # Default to 'user' role
            links = await backend.get_user_links(user_id)
            user_link_obj = next((link for link in links if link.get("link_type") == "user"), None)

            if user_link_obj:
                bot_username = (await callback.bot.get_me()).username
                ref_link = f"https://t.me/{bot_username}?start={user_link_obj['token']}"

                text = (
                    "✨ **Ваша реферальная ссылка**\n\n"
                    "Пригласите друга и после его **первой покупки** вы оба получите по **1 генерации**!\n\n"
                    f"Ваша ссылка:\n`{ref_link}`"
                )
                await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=referral_user_keyboard(ref_link))
            else:
                await callback.message.edit_text("Не удалось найти вашу реферальную ссылку. Попробуйте позже.", reply_markup=partner_cabinet_keyboard())

    except Exception as e:
        logging.error(f"Failed to show referral program for user {chat_id}: {e}")
        await callback.message.edit_text("Не удалось загрузить раздел. Пожалуйста, попробуйте позже.", reply_markup=partner_cabinet_keyboard())


from aiogram.fsm.context import FSMContext
from bot.fsm import PayoutState, CreatePartnerLinkState
from api.models.referral import LinkType

@router.callback_query(F.data.startswith("copy_link:"))
async def copy_link_handler(callback: types.CallbackQuery):
    """
    Handles the 'Copy link' button press, simply informs the user.
    """
    link = callback.data.split(":", 1)[1]
    await callback.answer(text=f"Ссылка скопирована:\n{link}", show_alert=True)


# --- Admin Panel ---

@router.callback_query(F.data == "admin_panel")
async def admin_panel_entry(callback: types.CallbackQuery):
    await callback.answer("Загружаю админ-панель...")
    await _show_admin_panel(callback)

@router.callback_query(F.data == "admin_panel_refresh")
async def admin_panel_refresh(callback: types.CallbackQuery):
    await callback.answer("🔄 Обновляю...")
    await _show_admin_panel(callback)

@router.callback_query(F.data.startswith("payout_approve:"))
async def approve_payout(callback: types.CallbackQuery):
    payout_id = callback.data.split(":", 1)[1]
    try:
        await backend.update_payout_status(
            payout_id=payout_id,
            actor_chat_id=str(callback.from_user.id),
            new_status="approved"
        )
        await callback.answer("✅ Заявка одобрена.", show_alert=False)
        await _show_admin_panel(callback)
    except Exception as e:
        logging.error(f"Failed to approve payout {payout_id} by {callback.from_user.id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)

@router.callback_query(F.data.startswith("payout_reject:"))
async def reject_payout(callback: types.CallbackQuery):
    payout_id = callback.data.split(":", 1)[1]
    try:
        await backend.update_payout_status(
            payout_id=payout_id,
            actor_chat_id=str(callback.from_user.id),
            new_status="rejected"
        )
        await callback.answer("❌ Заявка отклонена.", show_alert=False)
        await _show_admin_panel(callback)
    except Exception as e:
        logging.error(f"Failed to reject payout {payout_id} by {callback.from_user.id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# --- Payout FSM ---

@router.callback_query(F.data == "payout_request")
async def start_payout_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(PayoutState.waiting_for_amount)
    await callback.message.edit_text("Введите сумму для вывода в рублях (например, 1500):")


@router.message(PayoutState.waiting_for_amount)
async def process_payout_amount(message: types.Message, state: FSMContext):
    try:
        amount = int(message.text)
        if amount <= 0:
            raise ValueError
    except (ValueError, TypeError):
        await message.answer("Неверный формат. Пожалуйста, введите целое положительное число (например, 1500).")
        return

    await state.update_data(amount_minor=amount * 100)
    await state.set_state(PayoutState.waiting_for_requisites)
    await message.answer("Отлично. Теперь введите ваши платежные реквизиты (например, номер карты или кошелька).")


@router.message(PayoutState.waiting_for_requisites)
async def process_payout_requisites(message: types.Message, state: FSMContext):
    requisites_text = message.text
    if not requisites_text:
        await message.answer("Реквизиты не могут быть пустыми. Пожалуйста, введите их.")
        return

    data = await state.get_data()
    amount_minor = data.get("amount_minor")

    try:
        user = await backend.get_user(message.from_user.id)
        partner_id = user.get("id")

        await backend.create_payout_request(
            partner_id=partner_id,
            amount_minor=amount_minor,
            requisites={"details": requisites_text}
        )
        await message.answer("✅ Ваша заявка на выплату успешно создана! Администратор рассмотрит ее в ближайшее время.")
    except Exception as e:
        logging.error(f"Failed to create payout request for user {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при создании заявки. Пожалуйста, попробуйте позже или обратитесь в поддержку.")
    finally:
        await state.clear()


# --- Admin side of Link Request ---

@router.callback_query(F.data.startswith("link_req_approve:"))
async def approve_link_request(callback: types.CallbackQuery):
    request_id = callback.data.split(":")[1]
    try:
        # Process the request via API
        processed_request = await backend.process_link_request(
            request_id=request_id,
            actor_chat_id=str(callback.from_user.id),
            new_status="approved"
        )

        # Notify the partner
        partner_chat_id = processed_request.get("partner", {}).get("chat_id")
        if partner_chat_id:
            await callback.bot.send_message(
                partner_chat_id,
                "✅ Ваша заявка на новую реферальную ссылку была одобрена!"
            )

        # Update the admin's message
        await callback.answer("✅ Запрос одобрен.", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n<b>Статус: ОДОБРЕНО</b> ✅", parse_mode="HTML", reply_markup=None)

    except Exception as e:
        logging.error(f"Failed to approve link request {request_id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@router.callback_query(F.data.startswith("link_req_reject:"))
async def reject_link_request(callback: types.CallbackQuery):
    request_id = callback.data.split(":")[1]
    try:
        # Process the request via API
        processed_request = await backend.process_link_request(
            request_id=request_id,
            actor_chat_id=str(callback.from_user.id),
            new_status="rejected"
        )

        # Notify the partner
        partner_chat_id = processed_request.get("partner", {}).get("chat_id")
        if partner_chat_id:
            await callback.bot.send_message(
                partner_chat_id,
                "❌ Ваша заявка на новую реферальную ссылку была отклонена."
            )

        # Update the admin's message
        await callback.answer("❌ Запрос отклонен.", show_alert=True)
        await callback.message.edit_text(f"{callback.message.text}\n\n<b>Статус: ОТКЛОНЕНО</b> ❌", parse_mode="HTML", reply_markup=None)

    except Exception as e:
        logging.error(f"Failed to reject link request {request_id}: {e}")
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# --- Link Request FSM (Partner side) ---

def link_percentage_keyboard():
    kb = InlineKeyboardBuilder()
    percentages = [10, 20, 30, 40, 50]
    for p in percentages:
        kb.button(text=f"{p}%", callback_data=f"link_req_percent:{p}")
    kb.button(text="Отмена", callback_data="cancel_link_request")
    kb.adjust(5, 1)
    return kb.as_markup()

@router.callback_query(F.data == "request_new_link")
async def start_link_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(LinkRequestState.waiting_for_percentage)
    await callback.message.edit_text(
        "Выберите процент для новой партнерской ссылки:",
        reply_markup=link_percentage_keyboard()
    )

@router.callback_query(LinkRequestState.waiting_for_percentage, F.data.startswith("link_req_percent:"))
async def process_link_percentage(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    percent = int(callback.data.split(":")[1])
    await state.update_data(percentage=percent)
    await state.set_state(LinkRequestState.waiting_for_comment)
    await callback.message.edit_text("Отлично! Теперь введите короткий комментарий для этой ссылки (например, 'Кампания в VK').")

@router.callback_query(F.data == "cancel_link_request", FSMContext)
async def cancel_link_request(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Отменено")
    await state.clear()
    # Go back to the main referral menu
    await referral_program_entry(callback)


@router.message(LinkRequestState.waiting_for_comment)
async def process_link_comment(message: types.Message, state: FSMContext):
    comment = message.text
    data = await state.get_data()
    percentage = data.get("percentage")

    try:
        user = await backend.get_user(message.from_user.id)
        partner_id = user.get("id")

        # Create the request in the DB
        link_request = await backend.create_link_request(
            partner_id=partner_id,
            requested_percent=percentage,
            comment=comment
        )

        await message.answer("✅ Ваш запрос на новую ссылку отправлен администратору!")

        # Notify admins
        admin_ids = settings.get_admins_chat_id()
        admin_kb = InlineKeyboardBuilder()
        approve_data = f"link_req_approve:{link_request['id']}"
        reject_data = f"link_req_reject:{link_request['id']}"
        admin_kb.button(text="✅ Одобрить", callback_data=approve_data)
        admin_kb.button(text="❌ Отклонить", callback_data=reject_data)

        notification_text = (
            f"⚠️ Новый запрос на партнерскую ссылку!\n\n"
            f"От партнера: {user.get('nickname')} (<code>{message.from_user.id}</code>)\n"
            f"Процент: <b>{percentage}%</b>\n"
            f"Комментарий: {comment}"
        )
        for admin_id in admin_ids:
            try:
                await message.bot.send_message(
                    chat_id=admin_id,
                    text=notification_text,
                    reply_markup=admin_kb.as_markup(),
                    parse_mode="HTML"
                )
            except Exception as e:
                logging.error(f"Failed to send link request notification to admin {admin_id}: {e}")

    except Exception as e:
        logging.error(f"Failed to create link request for partner {message.from_user.id}: {e}")
        await message.answer("❌ Произошла ошибка при отправке запроса.")
    finally:
        await state.clear()


from config import Settings
settings = Settings()

# --- Partner Links ---

@router.callback_query(F.data == "partner_links")
async def show_partner_links(callback: types.CallbackQuery):
    await callback.answer()
    try:
        user = await backend.get_user(callback.from_user.id)
        links = await backend.get_user_links(user['id'])

        bot_username = (await callback.bot.get_me()).username
        text = "<b>Ваши партнерские ссылки:</b>\n\n"

        partner_links = [link for link in links if link.get("link_type") == "partner"]

        if not partner_links:
            text += "У вас пока нет партнерских ссылок."
        else:
            for link in partner_links:
                ref_url = f"https://t.me/{bot_username}?start={link['token']}"
                text += (
                    f"🔗 <code>{ref_url}</code>\n"
                    f"Процент: <b>{link['percent']}%</b>\n"
                    f"Комментарий: {link.get('comment', 'N/A')}\n\n"
                )

        kb = InlineKeyboardBuilder()
        kb.button(text="⬅️ Назад в кабинет", callback_data="referral_program")
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb.as_markup())

    except Exception as e:
        logging.error(f"Failed to show partner links for {callback.from_user.id}: {e}")
        await callback.message.edit_text("❌ Не удалось загрузить список ссылок.")