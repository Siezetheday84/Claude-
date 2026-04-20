from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database import async_session, get_client, ClientStatus
from states import SetupStates
from utils.keyboards import industries_kb, regions_kb

router = Router()


@router.message(Command("settings"))
async def cmd_settings(message: Message, state: FSMContext):
    async with async_session() as session:
        client = await get_client(session, message.from_user.id)

    if not client or client.status not in (ClientStatus.SETUP, ClientStatus.ACTIVE):
        await message.answer("❌ Настройки доступны только для активных аккаунтов.")
        return

    selected = client.industries or []
    await state.update_data(selected_industries=selected)
    await message.answer(
        "⚙️ <b>Настройки профиля</b>\n\n"
        "Выберите отрасли, которые вас интересуют.\n"
        "Это определяет, какие темы и тренды мы будем предлагать.\n\n"
        "✅ — уже выбрано. Нажмите для снятия выбора.",
        reply_markup=industries_kb(selected),
        parse_mode="HTML"
    )
    await state.set_state(SetupStates.choosing_industries)


async def start_setup(message: Message, state: FSMContext):
    await state.update_data(selected_industries=[])
    await message.answer(
        "🎯 <b>Настройка профиля</b>\n\n"
        "Выберите отрасли, которые вас интересуют.\n"
        "Можно выбрать несколько. Это поможет нам подбирать актуальные темы.\n\n"
        "Нажмите «Продолжить», когда выберете нужное.",
        reply_markup=industries_kb([]),
        parse_mode="HTML"
    )
    await state.set_state(SetupStates.choosing_industries)


@router.callback_query(F.data.startswith("industry:"), SetupStates.choosing_industries)
async def toggle_industry(callback: CallbackQuery, state: FSMContext):
    industry = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected = list(data.get("selected_industries", []))

    if industry == "done":
        if not selected:
            await callback.answer("⚠️ Выберите хотя бы одну отрасль!", show_alert=True)
            return

        await callback.message.edit_text(
            f"✅ Выбрано отраслей: {len(selected)}\n\n"
            "Теперь выберите регион (или пропустите этот шаг):",
            reply_markup=regions_kb(),
            parse_mode="HTML"
        )
        await state.set_state(SetupStates.choosing_region)
    else:
        if industry in selected:
            selected.remove(industry)
        else:
            selected.append(industry)
        await state.update_data(selected_industries=selected)
        await callback.message.edit_reply_markup(reply_markup=industries_kb(selected))

    await callback.answer()


@router.callback_query(F.data.startswith("region:"), SetupStates.choosing_region)
async def choose_region(callback: CallbackQuery, state: FSMContext):
    region = callback.data.split(":", 1)[1]
    if region == "none":
        region = None

    data = await state.get_data()
    selected_industries = data.get("selected_industries", [])

    async with async_session() as session:
        client = await get_client(session, callback.from_user.id)
        if client:
            client.industries = selected_industries
            client.region = region
            if client.status == ClientStatus.SETUP:
                client.status = ClientStatus.ACTIVE
            await session.commit()

    region_text = region if region else "без привязки к региону"
    await callback.message.edit_text(
        f"✅ <b>Профиль настроен!</b>\n\n"
        f"📂 Отрасли: {', '.join(selected_industries)}\n"
        f"🌍 Регион: {region_text}\n\n"
        "Каждый понедельник в 11:00 вы будете получать 10 актуальных тем для ролика недели.\n\n"
        "Вы можете изменить настройки в любое время командой /settings",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()
