"""
Middleware-style handler that sets FSM state for active projects
and routes topic/script callbacks to the correct state.
"""
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery

from database import async_session, get_client, get_active_project, ClientStatus, ProjectStatus
from states import WeeklyStates, SetupStates

router = Router()


async def restore_project_state(user_id: int, state: FSMContext):
    """Restores the FSM state for an active project if state is empty."""
    current = await state.get_state()
    if current:
        return

    async with async_session() as session:
        client = await get_client(session, user_id)
        if not client or client.status != ClientStatus.ACTIVE:
            if client and client.status == ClientStatus.SETUP:
                await state.set_state(SetupStates.choosing_industries)
            return

        project = await get_active_project(session, user_id)
        if not project:
            return

        state_map = {
            ProjectStatus.TOPIC_SELECTION: WeeklyStates.waiting_topic_choice,
            ProjectStatus.SCRIPT_REVIEW: WeeklyStates.waiting_script_feedback,
            ProjectStatus.ASSETS_UPLOAD: WeeklyStates.uploading_assets,
            ProjectStatus.REVISION: WeeklyStates.waiting_revision,
        }

        target_state = state_map.get(project.status)
        if target_state:
            await state.set_state(target_state)
            await state.update_data(project_id=project.id, topics=project.topics_offered or [])


@router.message(F.text, flags={"restore_state": True})
async def message_state_restorer(message: Message, state: FSMContext):
    await restore_project_state(message.from_user.id, state)


@router.callback_query(F.data.startswith("topic:"))
async def route_topic_callback(callback: CallbackQuery, state: FSMContext):
    await restore_project_state(callback.from_user.id, state)

    current = await state.get_state()
    if current != WeeklyStates.waiting_topic_choice:
        data = await state.get_data()
        if not data.get("project_id"):
            async with async_session() as session:
                project = await get_active_project(session, callback.from_user.id)
                if project:
                    await state.update_data(project_id=project.id, topics=project.topics_offered or [])
                    await state.set_state(WeeklyStates.waiting_topic_choice)

    from handlers.weekly import select_topic
    await select_topic(callback, state)
