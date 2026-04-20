from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, ForeignKey,
    Integer, String, Text, Enum, JSON, select, update,
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, relationship

from config import DATABASE_URL


engine = create_async_engine(DATABASE_URL, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class ContractType(str, PyEnum):
    CONTRACT = "contract"
    SUBSCRIPTION = "subscription"


class ProjectStatus(str, PyEnum):
    TOPIC_SELECTION = "topic_selection"
    TOPIC_MISSED = "topic_missed"
    SCRIPT_REVIEW = "script_review"
    ASSETS_UPLOAD = "assets_upload"
    IN_PRODUCTION = "in_production"
    REVIEW = "review"
    REVISION = "revision"
    COMPLETED = "completed"


class ClientStatus(str, PyEnum):
    ONBOARDING = "onboarding"
    SETUP = "setup"
    ACTIVE = "active"
    SUSPENDED = "suspended"


class Client(Base):
    __tablename__ = "clients"

    id = Column(BigInteger, primary_key=True)  # Telegram user ID
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    status = Column(Enum(ClientStatus), default=ClientStatus.ONBOARDING)
    contract_type = Column(Enum(ContractType), nullable=True)
    industries = Column(JSON, default=list)
    region = Column(String(255), nullable=True)
    contract_signed = Column(Boolean, default=False)
    payment_50_received = Column(Boolean, default=False)
    payment_100_received = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    period_start = Column(DateTime, nullable=True)
    period_end = Column(DateTime, nullable=True)
    videos_total = Column(Integer, default=4)
    videos_completed = Column(Integer, default=0)
    assigned_manager_id = Column(BigInteger, nullable=True)

    projects = relationship("Project", back_populates="client", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(BigInteger, ForeignKey("clients.id"), nullable=False)
    week_number = Column(Integer, nullable=False)
    status = Column(Enum(ProjectStatus), default=ProjectStatus.TOPIC_SELECTION)
    topics_offered = Column(JSON, default=list)
    selected_topic = Column(Text, nullable=True)
    topic_deadline = Column(DateTime, nullable=True)
    script = Column(Text, nullable=True)
    script_feedback = Column(Text, nullable=True)
    disclaimers = Column(Text, nullable=True)
    asset_file_ids = Column(JSON, default=list)
    production_started_at = Column(DateTime, nullable=True)
    production_deadline = Column(DateTime, nullable=True)
    video_file_id = Column(String(255), nullable=True)
    revision_feedback = Column(Text, nullable=True)
    final_video_file_id = Column(String(255), nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="projects")


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_client(session: AsyncSession, client_id: int) -> Optional[Client]:
    result = await session.execute(select(Client).where(Client.id == client_id))
    return result.scalar_one_or_none()


async def get_or_create_client(session: AsyncSession, user) -> Client:
    client = await get_client(session, user.id)
    if not client:
        client = Client(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
        )
        session.add(client)
        await session.commit()
        await session.refresh(client)
    return client


async def get_active_project(session: AsyncSession, client_id: int) -> Optional[Project]:
    result = await session.execute(
        select(Project)
        .where(Project.client_id == client_id)
        .where(Project.status != ProjectStatus.COMPLETED)
        .order_by(Project.created_at.desc())
    )
    return result.scalar_one_or_none()


async def get_all_active_clients(session: AsyncSession) -> list[Client]:
    result = await session.execute(
        select(Client).where(Client.status == ClientStatus.ACTIVE)
    )
    return list(result.scalars().all())
