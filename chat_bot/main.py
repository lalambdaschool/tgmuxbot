import asyncio
import logging
import json
from telegram import Update, User, ForumTopic
from telegram.error import BadRequest

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
import os

from chat_bot.database import (
    init_db,
    add_user_message_thread_id,
    get_user_message_thread_id,
    get_user_by_message_thread_id,
    delete_user,
    get_text,
    store_text,
)
from chat_bot.error_handler import error_handler
from chat_bot.exceptions import NoAdminChat, NoTopicsAdminChat, NoTopicRightsAdminChat


def load_config():
    with open("../config.json", "r") as f:
        return json.load(f)


config = load_config()
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

logger = logging.getLogger(__name__)
ADMIN_CHAT_ID = int(config["ADMIN_CHAT_ID"])
DEVELOPER_CHAT_ID = int(config["DEVELOPER_CHAT_ID"])
ADMIN_LIST = config["ADMIN_LIST"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(await get_text())


async def set_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id not in ADMIN_LIST:
        return
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text
    else:
        await update.message.reply_text(
            "Чтобы обновить приветствтие, пожалуйста реплайните на новое приветствие командой /set_text."
        )
        return
    await store_text(text)
    await update.message.reply_text(
        "Приветственный текст был обновлён. Теперь он такой"
    )
    await update.message.reply_text(await get_text())


async def get_forum_topic_id(user: User, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_thread_id = await get_user_message_thread_id(user.id)
    if message_thread_id is None:
        try:
            chat = await context.bot.get_chat(ADMIN_CHAT_ID)
        except BadRequest as e:
            if e.message == "Chat not found":
                raise NoAdminChat()
            raise
        if chat.is_forum is not True:
            raise NoTopicsAdminChat()
        chat_member = await context.bot.get_chat_member(ADMIN_CHAT_ID, context.bot.id)
        if (
            not hasattr(chat_member, "can_manage_topics")
            or chat_member.can_manage_topics is not True
        ):
            raise NoTopicRightsAdminChat()
        forum: ForumTopic = await context.bot.create_forum_topic(
            ADMIN_CHAT_ID, user.name
        )
        message_thread_id = forum.message_thread_id
        await add_user_message_thread_id(user.id, message_thread_id)
    return message_thread_id


async def forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        message_thread_id = await get_forum_topic_id(user, context)
    except NoAdminChat:
        await update.message.reply_text("Нет доступа к чату с админами")
        return
    except (NoTopicsAdminChat, NoTopicRightsAdminChat) as e:
        await update.message.forward(chat_id=ADMIN_CHAT_ID)
        await context.bot.send_message(ADMIN_CHAT_ID, e.message)
        return
    try:
        await update.message.copy(
            chat_id=ADMIN_CHAT_ID, message_thread_id=message_thread_id
        )
    except BadRequest as e:
        if e.message == "Message thread not found":
            await delete_user(user.id)
            await forward(update, context)
        elif e.message == "The message can't be copied":
            return
        else:
            raise


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    message_thread_id = update.message.message_thread_id
    if message_thread_id is None:
        return
    user_id = await get_user_by_message_thread_id(message_thread_id)
    if user_id is None:
        await update.message.reply_text("Не найден пользователь этого форума")
        return
    try:
        await update.message.copy(chat_id=user_id)
    except BadRequest as e:
        if e.message == "The message can't be copied":
            return


def main() -> None:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    application = Application.builder().token(config["TELEGRAM_API_TOKEN"]).build()

    application.add_handler(CommandHandler("set_text", set_text))
    application.add_handler(CommandHandler("start", start))

    application.add_handler(
        MessageHandler(filters.ChatType.PRIVATE & ~filters.COMMAND, forward)
    )

    application.add_handler(MessageHandler(filters.Chat(ADMIN_CHAT_ID), reply))
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
