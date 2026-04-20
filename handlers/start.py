from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database import async_session, get_or_create_client, ClientStatus, ContractType
from states import OnboardingStates, SetupStates
from utils.keyboards import contract_type_kb

router = Router()

WELCOME_TEXT = """👋 Добро пожаловать в сервис создания актуальных видеороликов!

Мы создаём видео, привязанные к новостям, трендам и событиям — специально для вашей отрасли.

Всё управление — прямо здесь, через этот чат.

━━━━━━━━━━━━━━━━━━━━
📌 Выберите формат подключения:

🔹 <b>Договор</b>
• Срок: 4 недели (с автопролонгацией)
• Оплата: 50% до начала + 50% после
• Оформление по договору

🔹 <b>Подписка</b>
• Срок: 4 недели
• 1 ролик в неделю (всего 4)
• Оплата: 100% заранее
• Оформление по оферте
━━━━━━━━━━━━━━━━━━━━"""


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    async with async_session() as session:
        client = await get_or_create_client(session, message.from_user)

    if client.status == ClientStatus.ACTIVE:
        await message.answer(
            "✅ Ваш аккаунт уже активен!\n\n"
            "Используйте /status для проверки текущего статуса\n"
            "или напишите <b>«подключить аккаунта»</b> для связи с менеджером.",
            parse_mode="HTML"
        )
        return

    await state.clear()
    await message.answer(WELCOME_TEXT, reply_markup=contract_type_kb(), parse_mode="HTML")
    await state.set_state(OnboardingStates.choosing_contract_type)


@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📌 <b>Доступные команды:</b>\n\n"
        "/start — Начать / перезапустить\n"
        "/status — Статус текущего ролика\n"
        "/settings — Настройки профиля\n"
        "/support — Подключить менеджера\n\n"
        "💬 Напишите <b>«подключить аккаунта»</b> — и к вам подключится менеджер.",
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("contract:"), OnboardingStates.choosing_contract_type)
async def choose_contract(callback: CallbackQuery, state: FSMContext):
    contract_type = callback.data.split(":")[1]
    await state.update_data(contract_type=contract_type)

    async with async_session() as session:
        client = await get_or_create_client(session, callback.from_user)
        client.contract_type = ContractType(contract_type)
        await session.commit()

    if contract_type == "contract":
        text = (
            "📄 <b>Оформление договора</b>\n\n"
            "Мы подготовим договор и вышлем вам в ближайшее время.\n\n"
            "После получения договора:\n"
            "1. Подпишите и отсканируйте\n"
            "2. Пришлите скан нам\n"
            "3. Мы выставим счёт на <b>50% предоплаты</b>\n\n"
            "Нажмите, когда оплата произведена — мы проверим и активируем аккаунт."
        )
    else:
        text = (
            "🔄 <b>Подписка</b>\n\n"
            "Отличный выбор! Оформление по публичной оферте.\n\n"
            "Стоимость: <b>4 ролика за 4 недели</b>\n"
            "Оплата: <b>100% заранее</b>\n\n"
            "Реквизиты для оплаты вышлет менеджер в ближайшее время.\n"
            "После оплаты — уведомите нас здесь, мы проверим и активируем аккаунт."
        )

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 Я оплатил(а)", callback_data="onboarding:paid")],
        [InlineKeyboardButton(text="🙋 Связаться с менеджером", callback_data="support:connect")],
    ])

    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await state.set_state(OnboardingStates.waiting_payment_confirmation)
    await callback.answer()


@router.callback_query(F.data == "onboarding:paid", OnboardingStates.waiting_payment_confirmation)
async def payment_claimed(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_text(
        "✅ Спасибо! Ваша заявка на активацию принята.\n\n"
        "Менеджер проверит оплату и активирует ваш аккаунт в течение рабочего дня.\n\n"
        "Вы получите уведомление, как только всё будет готово!",
        parse_mode="HTML"
    )

    from aiogram import Bot
    from config import ADMIN_IDS
    bot: Bot = callback.bot
    data = await state.get_data()
    contract_type = data.get("contract_type", "неизвестно")
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 <b>Новый клиент ожидает активации</b>\n\n"
                f"👤 {callback.from_user.full_name} (@{callback.from_user.username})\n"
                f"🆔 ID: <code>{callback.from_user.id}</code>\n"
                f"📋 Тип: {contract_type}\n\n"
                f"Используйте /admin для управления клиентами.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()
    await callback.answer()
