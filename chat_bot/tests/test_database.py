import pytest
from chat_bot.database import *


@pytest.fixture(autouse=True)
async def setup_db_teardown():
    await create_tables()
    yield
    await drop_tables()


async def test_create_user():
    user_id = 123
    message_thread_id = 456
    result_1 = await create_user(user_id=user_id, message_thread_id=message_thread_id)
    assert isinstance(result_1, int)
    assert result_1 > 0

    # Verify the user was created
    async with AsyncSession(engine) as session:
        result_2 = await session.execute(select(User).where(User.id == result_1))
        user = result_2.scalar_one_or_none()
        assert user is not None
        assert user.id == result_1
        assert user.message_thread_id == message_thread_id


async def test_find_user_id_by_message_thread_id():
    user_id = await create_user(message_thread_id=1, user_id=123)
    result = await find_user_id_by_message_thread_id(message_thread_id=1)
    assert result == user_id

    user_id = await create_user(message_thread_id=2, user_id=456)
    result = await find_user_id_by_message_thread_id(message_thread_id=2)
    assert result == user_id


async def test_find_message_thread_id_by_user_id():
    await create_user(message_thread_id=111, user_id=1234)
    await create_user(message_thread_id=222, user_id=5678)
    message_thread_id = await find_message_thread_id_by_user_id(user_id=1234)
    assert message_thread_id == 111
    message_thread_id_2 = await find_message_thread_id_by_user_id(user_id=5678)
    assert message_thread_id_2 == 222


async def test_create_message():
    user_id = await create_user(message_thread_id=5678, user_id=1234)
    message_pk_1 = await create_message(
        user_id=user_id, message_id=111, chat_message_id=222, sender_type="staff"
    )
    message_pk_2 = await create_message(
        user_id=user_id, message_id=333, chat_message_id=444, sender_type="user"
    )
    assert isinstance(message_pk_1, int)
    assert message_pk_1 > 0
    assert isinstance(message_pk_2, int)
    assert message_pk_2 > 0

    # Verify the message was created
    async with AsyncSession(engine) as session:
        result = await session.execute(
            select(Message).where(Message.id == message_pk_1)
        )
        message = result.scalar_one_or_none()
        assert message is not None
        assert message.id == message_pk_1
        assert message.message_id == 111
        assert message.chat_message_id == 222
        assert message.sender_type == "staff"
        result = await session.execute(
            select(Message).where(Message.id == message_pk_2)
        )
        message = result.scalar_one_or_none()
        assert message is not None
        assert message.id == message_pk_2
        assert message.message_id == 333
        assert message.chat_message_id == 444
        assert message.sender_type == "user"


async def test_find_message_id_by_chat_message_id_and_message_thread_id():
    user_id = await create_user(message_thread_id=1234, user_id=5678)
    await create_message(
        user_id=user_id, message_id=111, chat_message_id=222, sender_type="user"
    )
    await create_message(
        user_id=user_id, message_id=333, chat_message_id=444, sender_type="user"
    )
    message_id = await find_message_id_by_chat_message_id_and_message_thread_id(
        chat_message_id=222, message_thread_id=1234
    )
    assert message_id == 111
    message_id = await find_message_id_by_chat_message_id_and_message_thread_id(
        chat_message_id=444, message_thread_id=1234
    )
    assert message_id == 333


async def test_find_chat_message_id_by_message_id_and_user_id():
    user_id = await create_user(message_thread_id=1234, user_id=1234)
    await create_message(
        user_id=user_id, message_id=111, chat_message_id=222, sender_type="user"
    )
    await create_message(
        user_id=user_id, message_id=333, chat_message_id=444, sender_type="user"
    )
    chat_message_id = await find_chat_message_id_by_message_id_and_user_id(
        message_id=111, user_id=1234
    )
    assert chat_message_id == 222
    chat_message_id = await find_chat_message_id_by_message_id_and_user_id(
        message_id=333, user_id=1234
    )
    assert chat_message_id == 444


async def test_get_text_value():
    await update_text("new_value")
    text_value = await get_text()
    assert text_value == "new_value"


async def test_update_text_value():
    await update_text("new_value")
    text_value = await get_text()
    assert text_value == "new_value"
    await update_text("new_value_2")
    text_value = await get_text()
    assert text_value == "new_value_2"
