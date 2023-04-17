import aiosqlite

DB_NAME = "users.db"


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, message_thread_id INTEGER NOT NULL)"
        )
        await db.execute(
            "CREATE TABLE IF NOT EXISTS text (id INTEGER PRIMARY KEY, content TEXT)"
        )
        await db.commit()


async def add_user_message_thread_id(user_id: int, message_thread_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO users (id, message_thread_id) VALUES (?, ?)",
            (user_id, message_thread_id),
        )
        await db.commit()


async def get_user_message_thread_id(user_id: int) -> int | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT message_thread_id FROM users WHERE id=?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def get_user_by_message_thread_id(message_thread_id: int) -> int | None:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT id FROM users WHERE message_thread_id=?", (message_thread_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else None


async def delete_user(user_id: int) -> None:
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM users WHERE id=?", (user_id,))
        await db.commit()


async def store_text(content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO text (id, content) VALUES (?, ?)", (1, content)
        )
        await db.commit()


async def get_text() -> str:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute("SELECT content FROM text WHERE id=?", (1,))
        row = await cursor.fetchone()
        return row[0] if row else "Напишите нам, мы вам ответим"
