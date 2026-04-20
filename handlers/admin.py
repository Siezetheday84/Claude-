from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery
from sqlalchemy import select

from config import ADMIN_IDS, PRODUCTION_HOURS
from database import (
    async_session, get_client, get_active_project,
    ClientStatus, ProjectStatus, Project, Client,
)
from states import AdminStates, WeeklyStates
from utils.ai import generate_topics
from utils.keyboards import topics_kb, video_review_kb, final_accept_kb

router = Router()


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(Client))
        clients = result.scalars().all()

    active = [c for c in clients if c.status == ClientStatus.ACTIVE]
    onboarding = [c for c in clients if c.status == ClientStatus.ONBOARDING]

    await message.answer(
        f"👨‍💼 <b>Панель администратора</b>\n\n"
        f"👥 Всего клиентов: {len(clients)}\n"
        f"✅ Активных: {len(active)}\n"
        f"⏳ В процессе регистрации: {len(onboarding)}\n\n"
        "<b>Команды:</b>\n"
        "/send_topics — Разослать темы активным клиентам\n"
        "/clients — Список клиентов\n"
        "/activate <id> — Активировать клиента\n"
        "/send_video <client_id> — Отправить ролик клиенту\n"
        "/broadcast — Рассылка всем клиентам\n"
        "/reply_<id> <текст> — Ответить клиенту\n",
        parse_mode="HTML"
    )


@router.message(Command("clients"))
async def cmd_clients(message: Message):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(select(Client))
        clients = result.scalars().all()

    if not clients:
        await message.answer("Клиентов нет.")
        return

    text = "👥 <b>Список клиентов:</b>\n\n"
    for c in clients:
        status_emoji = {"active": "✅", "onboarding": "⏳", "setup": "⚙️", "suspended": "❌"}.get(c.status.value, "❓")
        text += (
            f"{status_emoji} <b>{c.full_name or 'Без имени'}</b> "
            f"(@{c.username or 'нет'}) — <code>{c.id}</code>\n"
            f"   Тип: {c.contract_type.value if c.contract_type else '—'} | "
            f"Роликов: {c.videos_completed}/{c.videos_total}\n\n"
        )

    await message.answer(text[:4000], parse_mode="HTML")


@router.message(Command("activate"))
async def cmd_activate(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /activate <client_id>")
        return

    try:
        client_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    async with async_session() as session:
        client = await get_client(session, client_id)
        if not client:
            await message.answer("❌ Клиент не найден")
            return
        client.status = ClientStatus.SETUP
        client.period_start = datetime.utcnow()
        client.period_end = datetime.utcnow() + timedelta(weeks=4)
        await session.commit()

    await message.answer(f"✅ Клиент {client_id} активирован. Статус: SETUP (нужна настройка профиля).")

    try:
        from handlers.account import start_setup
        from aiogram.fsm.storage.base import StorageKey
        await message.bot.send_message(
            client_id,
            "✅ <b>Ваш аккаунт активирован!</b>\n\n"
            "Теперь давайте настроим ваш профиль — это займёт минуту.",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"⚠️ Не смог уведомить клиента: {e}")


@router.message(Command("send_topics"))
async def cmd_send_topics(message: Message):
    if not is_admin(message.from_user.id):
        return

    await message.answer("🔄 Генерирую темы и рассылаю клиентам...")

    async with async_session() as session:
        result = await session.execute(
            select(Client).where(Client.status == ClientStatus.ACTIVE)
        )
        clients = result.scalars().all()

    sent = 0
    for client in clients:
        try:
            active_project = await _create_weekly_project_and_send(message.bot, client)
            sent += 1
        except Exception as e:
            await message.answer(f"⚠️ Ошибка для клиента {client.id}: {e}")

    await message.answer(f"✅ Темы разосланы {sent} клиентам.")


@router.message(Command("send_video"))
async def cmd_send_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /send_video <client_id>\nЗатем прикрепите видео следующим сообщением.")
        return

    try:
        client_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    await state.update_data(target_client_id=client_id)
    await state.set_state(AdminStates.uploading_video)
    await message.answer(f"📤 Прикрепите видео для клиента {client_id}.")


@router.message(AdminStates.uploading_video, F.video)
async def admin_upload_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    data = await state.get_data()
    client_id = data.get("target_client_id")

    async with async_session() as session:
        project = await get_active_project(session, client_id)
        if not project:
            await message.answer("❌ У клиента нет активного проекта.")
            await state.clear()
            return

        is_revision = project.status == ProjectStatus.REVISION
        if is_revision:
            project.final_video_file_id = message.video.file_id
            project.status = ProjectStatus.REVIEW
        else:
            project.video_file_id = message.video.file_id
            project.status = ProjectStatus.REVIEW
        await session.commit()
        project_id = project.id
        topic = project.selected_topic

    kb = final_accept_kb() if is_revision else video_review_kb()
    prefix = "🎬 <b>Финальная версия вашего ролика готова!</b>" if is_revision else "🎬 <b>Ваш ролик готов!</b>"

    try:
        await message.bot.send_video(
            client_id,
            message.video.file_id,
            caption=(
                f"{prefix}\n\n"
                f"📌 Тема: {topic}\n\n"
                "Проверьте ролик и примите решение:"
            ),
            reply_markup=kb,
            parse_mode="HTML"
        )
        await message.answer(f"✅ Ролик отправлен клиенту {client_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка отправки: {e}")

    await state.clear()


@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.set_state(AdminStates.broadcasting)
    await message.answer("📢 Напишите сообщение для рассылки всем активным клиентам:")


@router.message(AdminStates.broadcasting)
async def do_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    async with async_session() as session:
        result = await session.execute(
            select(Client).where(Client.status == ClientStatus.ACTIVE)
        )
        clients = result.scalars().all()

    sent = 0
    for client in clients:
        try:
            await message.bot.send_message(client.id, message.text)
            sent += 1
        except Exception:
            pass

    await message.answer(f"✅ Рассылка завершена. Отправлено: {sent} клиентам.")
    await state.clear()


@router.message(F.text.regexp(r'^/reply_(\d+)\s(.+)$'))
async def admin_reply(message: Message):
    if not is_admin(message.from_user.id):
        return

    import re
    match = re.match(r'^/reply_(\d+)\s(.+)$', message.text, re.DOTALL)
    if not match:
        return

    client_id = int(match.group(1))
    reply_text = match.group(2)

    try:
        await message.bot.send_message(
            client_id,
            f"💬 <b>Менеджер:</b>\n\n{reply_text}",
            parse_mode="HTML"
        )
        await message.answer(f"✅ Сообщение отправлено клиенту {client_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("send_act"))
async def cmd_send_act(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Использование: /send_act <client_id>")
        return

    try:
        client_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Неверный ID")
        return

    async with async_session() as session:
        client = await get_client(session, client_id)

    if not client:
        await message.answer("❌ Клиент не найден")
        return

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить акт", callback_data=f"act:confirm:{client_id}")],
    ])

    try:
        await message.bot.send_message(
            client_id,
            f"📋 <b>Акт выполненных работ</b>\n\n"
            f"Период: {client.period_start.strftime('%d.%m.%Y') if client.period_start else '—'} — "
            f"{client.period_end.strftime('%d.%m.%Y') if client.period_end else '—'}\n"
            f"Выполнено роликов: {client.videos_completed} из {client.videos_total}\n\n"
            f"Тип договора: {client.contract_type.value if client.contract_type else '—'}\n\n"
            "Пожалуйста, подтвердите получение акта:",
            reply_markup=kb,
            parse_mode="HTML"
        )
        await message.answer(f"✅ Акт отправлен клиенту {client_id}.")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.callback_query(F.data.startswith("act:confirm:"))
async def confirm_act(callback: CallbackQuery):
    client_id = int(callback.data.split(":")[2])

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer(
        "✅ <b>Акт подтверждён!</b>\n\n"
        "Спасибо за сотрудничество! "
        "Если вы не отказались от продолжения — работа автоматически продолжится на следующий период.",
        parse_mode="HTML"
    )

    for admin_id in ADMIN_IDS:
        try:
            await callback.bot.send_message(
                admin_id,
                f"✅ Клиент {client_id} подтвердил акт.",
                parse_mode="HTML"
            )
        except Exception:
            pass

    await callback.answer()


async def _create_weekly_project_and_send(bot: Bot, client: Client) -> None:
    async with async_session() as session:
        existing = await get_active_project(session, client.id)
        if existing and existing.status != ProjectStatus.COMPLETED:
            return

        week_num = client.videos_completed + 1
        industries = client.industries or ["общая тематика"]
        region = client.region or ""

        topics = await generate_topics(industries, region)
        if not topics:
            topics = [
                "Топ-5 трендов недели в вашей отрасли",
                "Что изменилось на рынке за последние 7 дней",
                "Вирусный формат: до/после в вашей нише",
                "Разбор актуального инфоповода",
                "Лайфхак для клиентов вашей отрасли",
            ]

        from datetime import date
        import pytz
        tz = pytz.timezone("Europe/Moscow")
        now_local = datetime.now(tz)
        days_until_tuesday = (1 - now_local.weekday()) % 7
        if days_until_tuesday == 0:
            days_until_tuesday = 7
        deadline_local = now_local.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=days_until_tuesday)
        deadline_utc = deadline_local.astimezone(pytz.utc).replace(tzinfo=None)

        project = Project(
            client_id=client.id,
            week_number=week_num,
            status=ProjectStatus.TOPIC_SELECTION,
            topics_offered=topics,
            topic_deadline=deadline_utc,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)

    topics_text = "\n".join(f"{i}. {t}" for i, t in enumerate(topics, 1))
    await bot.send_message(
        client.id,
        f"📅 <b>Темы для ролика недели #{week_num}</b>\n\n"
        f"{topics_text}\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "👆 Выберите одну тему — это основа вашего ролика.\n\n"
        f"⏰ <b>Дедлайн выбора: вторник 10:00</b>\n"
        "Если тема не выбрана — ролик считается пропущенным.",
        reply_markup=topics_kb(topics),
        parse_mode="HTML"
    )

    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.memory import MemoryStorage
