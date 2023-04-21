from typing import Optional, Literal

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy import Column, Integer, ForeignKey, select, Index, String, update
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    message_thread_id = Column(Integer, index=True)

    messages = relationship("Message", back_populates="user")


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    message_id = Column(Integer)
    chat_message_id = Column(Integer)
    sender_type = Column(String)

    user = relationship("User", back_populates="messages")

    __table_args__ = (
        Index("idx_message_user_id", user_id),
        Index("idx_message_message_id", message_id),
        Index("idx_message_chat_message_id", chat_message_id),
    )


class Config(Base):
    __tablename__ = "config"
    id = Column(Integer, primary_key=True)
    text_value = Column(String)


DATABASE_URL = "sqlite+aiosqlite:///my_database.sqlite"
engine = create_async_engine(DATABASE_URL, echo=True)


async def create_tables(initial_config_value: str = "Пишите, мы вам ответим!"):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Check if the config table is empty
        async with AsyncSession(engine) as session:
            result = await session.execute(select(Config).where(Config.id == 1))
            config_exists = result.scalar_one_or_none()

            # If the config table is empty, insert the initial value
            if not config_exists:
                config = Config(id=1, text_value=initial_config_value)
                session.add(config)
                await session.commit()


async def create_user(user_id: int, message_thread_id: int) -> int:
    async with AsyncSession(engine) as session:
        user = User(id=user_id, message_thread_id=message_thread_id)
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user.id


async def delete_user(user_id: int) -> None:
    async with AsyncSession(engine) as session:
        user = await session.get(User, user_id)
        await session.delete(user)
        await session.commit()


async def create_message(
    user_id: int,
    message_id: int,
    chat_message_id: int,
    sender_type: Literal["user", "staff"],
) -> int:
    async with AsyncSession(engine) as session:
        message = Message(
            user_id=user_id,
            message_id=message_id,
            chat_message_id=chat_message_id,
            sender_type=sender_type,
        )
        session.add(message)
        await session.commit()
        await session.refresh(message)
        return message.id


async def find_message_thread_id_by_user_id(user_id: int) -> Optional[int]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User.message_thread_id).where(User.id == user_id)
        )
        return result.scalar_one_or_none()


async def find_user_id_by_message_thread_id(message_thread_id: int) -> Optional[int]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(User.id).where(User.message_thread_id == message_thread_id)
        )
        return result.scalar_one_or_none()


async def find_message_id_by_chat_message_id_and_message_thread_id(
    chat_message_id: int, message_thread_id: int
) -> Optional[int]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Message.message_id).where(
                (Message.chat_message_id == chat_message_id)
                & (Message.user.has(User.message_thread_id == message_thread_id))
            )
        )
        return result.scalar_one_or_none()


async def find_chat_message_id_by_message_id_and_user_id(
    message_id: int, user_id: int
) -> Optional[int]:
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Message.chat_message_id).where(
                (Message.message_id == message_id) & (Message.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()


async def get_text() -> Optional[str]:
    async with AsyncSession(engine) as session:
        result = await session.execute(select(Config.text_value).where(Config.id == 1))
        return result.scalar_one_or_none()


async def update_text(new_value: str):
    async with AsyncSession(engine) as session:
        async with session.begin():
            await session.execute(
                update(Config).where(Config.id == 1).values(text_value=new_value)
            )
            await session.commit()


async def drop_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
