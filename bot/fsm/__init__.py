from aiogram.fsm.state import State, StatesGroup

class BotState(StatesGroup):
    start_message_id = State()
    waiting_for_text_description = State()
    waiting_for_photo = State()
    waiting_for_photo_caption = State()