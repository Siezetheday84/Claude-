from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import ADMIN_IDS
from database import async_session, get_client, ClientStatus

router = Router()

SUPPORT_TRIGGER = "подключить аккаунта"


@router.message(Command("support"))
@router.message(F.text.lower() == SUPPORT_TRIGGER)
async def connect_support(message: Message, state: FSMContext):
    current_state = await state.get_state()

    async with async_session() as session:
        client = await get_client(session, message.from_user.id)

    client_info = ""
    if client:
        client_info = (
            f"📋 Тип: {client.contract_type.value if client.contract_type else 'не указан'}\n"
            f"📂 Отрасли: {', '.join(client.industries or []) or 'не выбраны'}\n"
            f"✅ Роликов: {client.videos_completed}/{client.videos_total}\n"
        )

    await message.answer(
        "🙋 <b>Запрос на подключение менеджера отправлен!</b>\n\n"
        "Менеджер подключится к диалогу в ближайшее время и поможет вам.\n\n"
        "Продолжайте писать — мы всё видим.",
        parse_mode="HTML"
    )

    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"🙋 <b>Клиент запросил менеджера</b>\n\n"
                f"👤 {message.from_user.full_name} (@{message.from_user.username or 'нет'})\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📍 Состояние: {current_state or 'нет'}\n\n"
                f"{client_info}\n"
                f"💬 Напишите клиенту: /reply_{message.from_user.id} <текст>",
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.callback_query(F.data == "support:connect")
async def connect_support_callback(callback: CallbackQuery, state: FSMContext):
    await connect_support(callback.message, state)
    await callback.answer("Запрос отправлен!")
