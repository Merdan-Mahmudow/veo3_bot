from aiogram.fsm.state import State, StatesGroup

class BotState(StatesGroup):
    start_message_id = State()
    waiting_for_text_description = State()
    waiting_for_photo = State()
    waiting_for_photo_caption = State()

class PromptAssistantState(StatesGroup):
    waiting_brief = State()
    waiting_clarifications = State()
    reviewing = State()
    editing = State()

    # --- Состояния FSM ---
class PhotoState(StatesGroup):
    waiting_photo = State()         # ждём фотографию
    reviewing = State()             # показываем промпт и ждём решение
    editing = State()               # ждём правки

class PaymentState(StatesGroup):
    choosing_plan = State()         # выбираем план
    processing_payment = State()    # ждём оплаты
    confirming = State()            # подтверждаем оплату
    choosing_method = State()

class PartnerState(StatesGroup):
    creating_link = State()
    requesting_payout = State()