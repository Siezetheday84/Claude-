from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from config import PRODUCTION_HOURS, TIMEZONE
from database import (
    async_session, get_client, get_active_project,
    ClientStatus, ProjectStatus, Project,
)
from states import WeeklyStates
from utils.keyboards import (
    script_kb, assets_done_kb, video_review_kb, final_accept_kb, support_kb
)
from utils.ai import generate_script

import pytz

router = Router()
tz = pytz.timezone(TIMEZONE)

STATUS_LABELS = {
    ProjectStatus.TOPIC_SELECTION: "⏳ Выбор темы",
    ProjectStatus.TOPIC_MISSED: "❌ Тема не выбрана",
    ProjectStatus.SCRIPT_REVIEW: "📝 Согласование сценария",
    ProjectStatus.ASSETS_UPLOAD: "📎 Загрузка материалов",
    ProjectStatus.IN_PRODUCTION: "🎬 В производстве",
    ProjectStatus.REVIEW: "👀 На проверке",
    ProjectStatus.REVISION: "✏️ Правки",
    ProjectStatus.COMPLETED: "✅ Завершён",
}


@router.message(Command("status"))
async def cmd_status(message: Message):
    async with async_session() as session:
        client = await get_client(session, message.from_user.id)
        if not client or client.status != ClientStatus.ACTIVE:
            await message.answer("❌ У вас нет активного аккаунта. Напишите /start для начала.")
            return

        project = await get_active_project(session, message.from_user.id)

    if not project:
        await message.answer(
            "📋 <b>Статус аккаунта</b>\n\n"
            f"✅ Роликов выполнено: {client.videos_completed} из {client.videos_total}\n\n"
            "Ожидайте темы в следующий понедельник в 11:00.",
            parse_mode="HTML"
        )
        return

    status_label = STATUS_LABELS.get(project.status, project.status.value)
    text = (
        f"📋 <b>Статус ролика #{project.week_number}</b>\n\n"
        f"Статус: {status_label}\n"
    )

    if project.selected_topic:
        text += f"📌 Тема: {project.selected_topic}\n"

    if project.production_deadline and project.status == ProjectStatus.IN_PRODUCTION:
        deadline_local = project.production_deadline.replace(tzinfo=pytz.utc).astimezone(tz)
        text += f"⏱ Готово к: {deadline_local.strftime('%d.%m %H:%M')}\n"

    text += f"\n✅ Завершено роликов: {client.videos_completed} из {client.videos_total}"

    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data.startswith("topic:"), WeeklyStates.waiting_topic_choice)
async def select_topic(callback: CallbackQuery, state: FSMContext):
    topic_index = int(callback.data.split(":")[1]) - 1
    data = await state.get_data()
    topics = data.get("topics", [])

    if topic_index < 0 or topic_index >= len(topics):
        await callback.answer("❌ Неверный выбор", show_alert=True)
        return

    selected_topic = topics[topic_index]
    project_id = data.get("project_id")

    await callback.message.edit_text(
        f"✅ Отличный выбор!\n\n"
        f"📌 <b>Тема:</b> {selected_topic}\n\n"
        "⏳ Генерирую сценарий...",
        parse_mode="HTML"
    )

    async with async_session() as session:
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        client = await get_client(session, callback.from_user.id)

        if project and client:
            project.selected_topic = selected_topic
            project.status = ProjectStatus.SCRIPT_REVIEW
            await session.commit()

            industries = client.industries or ["общая тематика"]
            region = client.region or ""

    try:
        script = await generate_script(selected_topic, ", ".join(industries), region)
    except Exception as e:
        script = f"[Сценарий будет подготовлен менеджером]\n\nОшибка генерации: {e}"

    async with async_session() as session:
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.script = script
            await session.commit()

    await callback.message.answer(
        f"📝 <b>Сценарий для темы:</b>\n«{selected_topic}»\n\n"
        f"{script}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "Согласуйте сценарий или напишите правки:",
        reply_markup=script_kb(),
        parse_mode="HTML"
    )
    await state.set_state(WeeklyStates.waiting_script_feedback)
    await callback.answer()


@router.callback_query(F.data == "script:approve", WeeklyStates.waiting_script_feedback)
async def approve_script(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project_id = data.get("project_id")

    async with async_session() as session:
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.status = ProjectStatus.ASSETS_UPLOAD
            await session.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✅ <b>Сценарий согласован!</b>\n\n"
        "Теперь пришлите дополнительные материалы:\n\n"
        "• Дисклеймеры и юридические формулировки (текстом)\n"
        "• Обязательные упоминания\n"
        "• Логотипы, рендеры, картинки-референсы\n\n"
        "Отправляйте всё в этот чат. Когда всё загружено — нажмите кнопку ниже.",
        reply_markup=assets_done_kb(),
        parse_mode="HTML"
    )
    await state.set_state(WeeklyStates.uploading_assets)
    await callback.answer()


@router.callback_query(F.data == "script:revise", WeeklyStates.waiting_script_feedback)
async def request_script_revision(callback: CallbackQuery, state: FSMContext):
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✏️ Напишите ваши правки или пожелания к сценарию.\n\n"
        "Мы учтём их и доработаем.",
        parse_mode="HTML"
    )
    await state.set_state(WeeklyStates.waiting_script_feedback)
    await callback.answer()


@router.message(WeeklyStates.waiting_script_feedback, F.text)
async def receive_script_feedback(message: Message, state: FSMContext):
    if message.text.lower() in ("подключить аккаунта", "/support"):
        return

    data = await state.get_data()
    project_id = data.get("project_id")

    async with async_session() as session:
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.script_feedback = message.text
            await session.commit()

    await message.answer(
        "✅ Правки приняты! Менеджер доработает сценарий и пришлёт обновлённую версию.",
        reply_markup=support_kb()
    )

    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"✏️ <b>Правки к сценарию</b>\n\n"
                f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📋 Проект #{project_id}\n\n"
                f"Правки:\n{message.text}",
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.message(WeeklyStates.uploading_assets)
async def receive_assets(message: Message, state: FSMContext):
    data = await state.get_data()
    project_id = data.get("project_id")
    asset_ids = data.get("asset_ids", [])

    if message.document:
        asset_ids.append({"type": "document", "file_id": message.document.file_id, "name": message.document.file_name})
        await state.update_data(asset_ids=asset_ids)
        await message.answer(f"📎 Файл «{message.document.file_name}» загружен. Продолжайте или нажмите «Всё загружено».")

    elif message.photo:
        asset_ids.append({"type": "photo", "file_id": message.photo[-1].file_id})
        await state.update_data(asset_ids=asset_ids)
        await message.answer("🖼 Фото загружено. Продолжайте или нажмите «Всё загружено».", reply_markup=assets_done_kb())

    elif message.video:
        asset_ids.append({"type": "video", "file_id": message.video.file_id})
        await state.update_data(asset_ids=asset_ids)
        await message.answer("🎬 Видео загружено. Продолжайте или нажмите «Всё загружено».", reply_markup=assets_done_kb())

    elif message.text and message.text.lower() not in ("подключить аккаунта", "/support"):
        async with async_session() as session:
            from sqlalchemy import select as sa_select
            result = await session.execute(sa_select(Project).where(Project.id == project_id))
            project = result.scalar_one_or_none()
            if project:
                existing = project.disclaimers or ""
                project.disclaimers = (existing + "\n" + message.text).strip()
                await session.commit()
        await message.answer("📝 Текстовые материалы сохранены.", reply_markup=assets_done_kb())


@router.callback_query(F.data == "assets:done", WeeklyStates.uploading_assets)
async def assets_done(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    project_id = data.get("project_id")
    asset_ids = data.get("asset_ids", [])
    now = datetime.utcnow()
    production_deadline = now + timedelta(hours=PRODUCTION_HOURS)

    async with async_session() as session:
        from sqlalchemy import select as sa_select
        result = await session.execute(sa_select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        client = await get_client(session, callback.from_user.id)
        if project:
            project.status = ProjectStatus.IN_PRODUCTION
            project.asset_file_ids = asset_ids
            project.production_started_at = now
            project.production_deadline = production_deadline
            await session.commit()

    deadline_local = production_deadline.replace(tzinfo=pytz.utc).astimezone(tz)
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "🎬 <b>Ролик передан в производство!</b>\n\n"
        f"⏱ Срок готовности: <b>{deadline_local.strftime('%d.%m.%Y %H:%M')}</b>\n\n"
        "Вы получите ролик прямо в этот чат. Ожидайте!",
        parse_mode="HTML"
    )

    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"🎬 <b>Ролик в производстве</b>\n\n"
                f"👤 {callback.from_user.full_name} (@{callback.from_user.username})\n"
                f"🆔 ID: <code>{callback.from_user.id}</code>\n"
                f"📋 Проект #{project_id}\n"
                f"📌 Тема: {project.selected_topic}\n"
                f"⏰ Дедлайн: {deadline_local.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"Используйте /admin для управления.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "video:accept")
async def accept_video(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        project = await get_active_project(session, callback.from_user.id)
        client = await get_client(session, callback.from_user.id)
        if project and (project.status == ProjectStatus.REVIEW or project.status == ProjectStatus.REVISION):
            project.status = ProjectStatus.COMPLETED
            project.accepted_at = datetime.utcnow()
            if client:
                client.videos_completed += 1
            await session.commit()
            videos_left = (client.videos_total - client.videos_completed) if client else 0

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✅ <b>Ролик принят!</b>\n\n"
        f"🎉 Отличная работа! Ролик #{project.week_number} завершён.\n\n"
        + (f"📊 Осталось роликов в периоде: {videos_left}\n\n" if videos_left > 0 else "📊 Все ролики периода выполнены!\n\n")
        + "Следующая тема придёт в понедельник в 11:00.",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "video:revise")
async def request_video_revision(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        project = await get_active_project(session, callback.from_user.id)
        if project and project.status == ProjectStatus.REVIEW:
            project.status = ProjectStatus.REVISION
            await session.commit()

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✏️ Напишите список правок к ролику.\n\n"
        "<b>Важно:</b> у вас есть 1 раунд правок. Опишите всё в одном сообщении.",
        parse_mode="HTML"
    )
    await state.set_state(WeeklyStates.waiting_revision)
    await callback.answer()


@router.message(WeeklyStates.waiting_revision, F.text)
async def receive_revision(message: Message, state: FSMContext):
    async with async_session() as session:
        project = await get_active_project(session, message.from_user.id)
        if project:
            project.revision_feedback = message.text
            await session.commit()
            project_id = project.id
            topic = project.selected_topic

    await message.answer(
        "✅ Правки приняты! Мы внесём изменения и пришлём финальную версию."
    )

    from config import ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await message.bot.send_message(
                admin_id,
                f"✏️ <b>Правки к ролику</b>\n\n"
                f"👤 {message.from_user.full_name} (@{message.from_user.username})\n"
                f"🆔 ID: <code>{message.from_user.id}</code>\n"
                f"📋 Проект #{project_id}\n"
                f"📌 Тема: {topic}\n\n"
                f"Правки:\n{message.text}",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await state.clear()


@router.callback_query(F.data == "video:final_accept")
async def final_accept_video(callback: CallbackQuery, state: FSMContext):
    async with async_session() as session:
        project = await get_active_project(session, callback.from_user.id)
        client = await get_client(session, callback.from_user.id)
        if project:
            project.status = ProjectStatus.COMPLETED
            project.accepted_at = datetime.utcnow()
            if client:
                client.videos_completed += 1
            await session.commit()
            videos_left = (client.videos_total - client.videos_completed) if client else 0

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✅ <b>Финальная версия принята!</b>\n\n"
        f"🎉 Ролик #{project.week_number} успешно завершён.\n\n"
        + (f"📊 Осталось роликов: {videos_left}\n\n" if videos_left > 0 else "📊 Все ролики периода выполнены!\n\n")
        + "Следующая тема придёт в понедельник в 11:00.",
        parse_mode="HTML"
    )
    await callback.answer()
