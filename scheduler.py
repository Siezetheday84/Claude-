from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
import pytz

from config import (
    TIMEZONE, TOPICS_SEND_DAY, TOPICS_SEND_HOUR, TOPICS_SEND_MINUTE,
    TOPIC_DEADLINE_DAY, TOPIC_DEADLINE_HOUR, TOPIC_DEADLINE_MINUTE,
)
from database import async_session, Client, Project, ClientStatus, ProjectStatus
from utils.ai import generate_topics


async def send_weekly_topics(bot):
    from utils.keyboards import topics_kb
    tz = pytz.timezone(TIMEZONE)

    async with async_session() as session:
        result = await session.execute(
            select(Client).where(Client.status == ClientStatus.ACTIVE)
        )
        clients = result.scalars().all()

    for client in clients:
        try:
            async with async_session() as session:
                result = await session.execute(
                    select(Project)
                    .where(Project.client_id == client.id)
                    .where(Project.status != ProjectStatus.COMPLETED)
                )
                existing = result.scalar_one_or_none()

            if existing:
                continue

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
                    "Антитренд: что уже не работает",
                    "Кейс недели: история успеха",
                    "Вопрос-ответ: популярный запрос клиентов",
                    "Новость недели и ваша реакция",
                    "Провокационный заголовок недели",
                ]

            now_local = datetime.now(tz)
            days_until_tuesday = (1 - now_local.weekday()) % 7 or 7
            deadline_local = now_local.replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=days_until_tuesday)
            deadline_utc = deadline_local.astimezone(pytz.utc).replace(tzinfo=None)

            week_num = client.videos_completed + 1

            async with async_session() as session:
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
                "👆 Выберите одну тему для ролика недели.\n\n"
                "⏰ <b>Дедлайн: вторник 10:00</b>\n"
                "Если тема не выбрана — ролик считается пропущенным.\n\n"
                "💡 Напишите <b>«подключить аккаунта»</b> — и менеджер поможет с выбором.",
                reply_markup=topics_kb(topics),
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Error sending topics to {client.id}: {e}")


async def check_topic_deadlines(bot):
    async with async_session() as session:
        result = await session.execute(
            select(Project).where(Project.status == ProjectStatus.TOPIC_SELECTION)
        )
        projects = result.scalars().all()

    now = datetime.utcnow()
    for project in projects:
        if project.topic_deadline and now >= project.topic_deadline:
            try:
                async with async_session() as session:
                    result = await session.execute(
                        select(Project).where(Project.id == project.id)
                    )
                    p = result.scalar_one_or_none()
                    if p and p.status == ProjectStatus.TOPIC_SELECTION:
                        p.status = ProjectStatus.TOPIC_MISSED
                        await session.commit()

                await bot.send_message(
                    project.client_id,
                    "⏰ <b>Время выбора темы истекло</b>\n\n"
                    "К сожалению, тема не была выбрана до вторника 10:00.\n"
                    "Ролик этой недели считается пропущенным.\n\n"
                    "Стоимость подписки при этом не уменьшается.\n\n"
                    "Следующая тема придёт в следующий понедельник в 11:00.",
                    parse_mode="HTML"
                )
            except Exception as e:
                print(f"Error marking missed topic for project {project.id}: {e}")


async def check_period_completions(bot):
    from config import ADMIN_IDS

    async with async_session() as session:
        result = await session.execute(
            select(Client).where(Client.status == ClientStatus.ACTIVE)
        )
        clients = result.scalars().all()

    now = datetime.utcnow()
    for client in clients:
        if client.period_end and now >= client.period_end:
            if client.videos_completed >= client.videos_total:
                try:
                    await bot.send_message(
                        client.id,
                        "🎉 <b>Период завершён!</b>\n\n"
                        f"Выполнено роликов: {client.videos_completed} из {client.videos_total}\n\n"
                        "Акт выполненных работ будет направлен вам в ближайшее время.\n\n"
                        "Если вы не сообщили об отказе — работа продолжится автоматически на следующие 4 недели.",
                        parse_mode="HTML"
                    )

                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"📋 <b>Период завершён у клиента</b>\n\n"
                                f"👤 {client.full_name} (ID: {client.id})\n"
                                f"✅ Роликов: {client.videos_completed}/{client.videos_total}\n\n"
                                f"Нужно выслать акт: /send_act {client.id}",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass
                except Exception as e:
                    print(f"Error notifying period completion for {client.id}: {e}")


def setup_scheduler(bot) -> AsyncIOScheduler:
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    scheduler.add_job(
        send_weekly_topics,
        CronTrigger(
            day_of_week=TOPICS_SEND_DAY,
            hour=TOPICS_SEND_HOUR,
            minute=TOPICS_SEND_MINUTE,
            timezone=tz
        ),
        args=[bot],
        id="send_weekly_topics",
        replace_existing=True,
    )

    scheduler.add_job(
        check_topic_deadlines,
        CronTrigger(hour="*", minute=0, timezone=tz),
        args=[bot],
        id="check_deadlines",
        replace_existing=True,
    )

    scheduler.add_job(
        check_period_completions,
        CronTrigger(hour=9, minute=0, timezone=tz),
        args=[bot],
        id="check_periods",
        replace_existing=True,
    )

    return scheduler
