import asyncio
from typing import Optional
from aiogram import Router, types, F
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from bot import fsm
from bot.api import BackendAPI
from config import ENV
from services.kie import GenerateRequests

router = Router()
env = ENV()
backend = BackendAPI(env.bot_api_token)


def start_keyboard():
    kb = [
        [
            types.InlineKeyboardButton(
                text="📽️ Генерация видео по тексту", callback_data="generate_by_text")
        ],
        [
            types.InlineKeyboardButton(
                text="🎥 Генерация видео по фото", callback_data="generate_by_photo")
        ]
    ]
    inline_kb = types.InlineKeyboardMarkup(inline_keyboard=kb)
    return inline_kb


@router.message(Command("start"))
async def command_start(message: types.Message, state: FSMContext):
    

    # Проверяем наличие пользователя
    try:
        exists = await backend.check_user_exist(message.from_user.id)
    except Exception:
        await message.answer("Техническая ошибка соединения. Попробуй ещё раз позже.")
        return

    # Если нет — регаем
    if not exists:
        # Баннер
        await message.answer_photo(
            photo=types.URLInputFile(
                "https://storage.yandexcloud.net/veobot/photo_2025-08-12_00-07-56.jpg"),
            caption="Привет! Я генерирую для тебя лучшее видео по твоему запросу.\n\n"
        )

        await message.answer("Ты у нас впервые. Регистрирую…")
        nickname = (
            message.from_user.username
            or message.from_user.first_name
            or f"user_{message.from_user.id}"
        )
        try:
            res = await backend.register_user(message.from_user.id, nickname=nickname)
        except Exception:
            await message.answer("Техническая ошибка при регистрации. Напиши @softp04")
            return

        if not res.get("created", False) and res.get("reason") != "exists":
            await message.answer("Внутренняя ошибка регистрации. Напиши @softp04")
            return

    # Общая ветка после ensure user: получаем баланс и даём меню
    try:
        coins = await backend.get_coins(message.from_user.id)
    except Exception:
        coins = 0  # если не достали баланс — не роняем UX

    if not exists:
        text = (
            "Регистрация прошла успешно! Теперь давай сгенерируем видео!\n\n"
            f"У тебя {coins} генераций.\n\nВыбери способ генерации видео:"
        )
    else:
        text = (
            f"С возвращением!\n\nУ тебя {coins} генераций.\n\n"
            "Выбери способ генерации видео:"
        )

    sent_message: Optional[types.Message] = await message.answer(
        text,
        reply_markup=start_keyboard()
    )

    # Сохраняем id отправленного сообщения
    await state.update_data(start_message_id=sent_message.message_id)
    await state.set_state(fsm.BotState.start_message_id)


@router.callback_query(F.data == "generate_by_text")
async def callback_generate_by_text(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    start_message_id = data.get("start_message_id")
    chat_id = callback.message.chat.id
    await callback.bot.delete_message(chat_id=chat_id, message_id=start_message_id)
    await callback.answer()
    await callback.message.answer("✍️ Введите описание своего видео для генерации. Если хотите оживить фото, нажмите /start и выберите генерацию по фото:")
    await state.set_state(fsm.BotState.waiting_for_text_description)


@router.message(fsm.BotState.waiting_for_text_description)
async def handle_text_description(message: types.Message, state: FSMContext):
    text = message.text
    success = False
    await message.answer(f"🎬 Генерирую видео по описанию:\n\n{text}")
    generate = GenerateRequests()
    data = await generate.generate_video_by_text(text)
    print(data)

    if data["code"] == 200:
        while not success:
            result = await generate.get_video_info(data["data"]["taskId"])
            print(result)
            print("-------------------------------------------")

            if result["data"]["successFlag"] == 1:
                success = True
                video = types.URLInputFile(
                    result['data']['response']['resultUrls'][0])
                await message.answer_video(video, caption=text, show_caption_above_media=True)
            else:
                pass
            await asyncio.sleep(3)


@router.message(Command("test"))
async def test_details(message: types.Message, command: CommandObject):
    args = command.args
    generate = GenerateRequests()
    if args is None:
        await message.answer(
            "Ошибка: не переданы аргументы"
        )
        return
    req = await generate.get_video_info(args.replace(" ", ""))
    print(req)
