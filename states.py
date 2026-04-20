from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    choosing_contract_type = State()
    waiting_contract_confirmation = State()
    waiting_payment_confirmation = State()


class SetupStates(StatesGroup):
    choosing_industries = State()
    choosing_region = State()


class WeeklyStates(StatesGroup):
    waiting_topic_choice = State()
    waiting_script_feedback = State()
    waiting_disclaimers = State()
    uploading_assets = State()
    waiting_revision = State()


class SupportStates(StatesGroup):
    in_support_chat = State()


class AdminStates(StatesGroup):
    broadcasting = State()
    setting_topics = State()
    uploading_video = State()
    entering_act = State()
