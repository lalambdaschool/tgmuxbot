import asyncio
import logging
import json
from telegram import (
    Update,
    User,
    ForumTopic,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from telegram.error import BadRequest

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    CallbackContext,
    CallbackQueryHandler,
)

from chat_bot import database
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
    await update.message.reply_text(await database.get_text())


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
    await database.update_text(text)
    await update.message.reply_text(
        "Приветственный текст был обновлён. Теперь он такой"
    )
    await update.message.reply_text(await database.get_text())


async def get_forum_topic_id(user: User, context: ContextTypes.DEFAULT_TYPE) -> int:
    message_thread_id = await database.find_message_thread_id_by_user_id(user.id)
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
        await database.create_user(user_id=user.id, message_thread_id=message_thread_id)
    return message_thread_id


async def message_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    reply_message_id = None
    if reply_to_message := update.message.reply_to_message:
        reply_message_id = reply_to_message.message_id
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
        reply_to_message_id = None
        if reply_message_id:
            reply_to_message_id = (
                await database.find_chat_message_id_by_message_id_and_user_id(
                    message_id=reply_message_id, user_id=user.id
                )
            )
        new_message = await update.message.copy(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=message_thread_id,
            reply_to_message_id=reply_to_message_id,
        )
        await database.create_message(
            user_id=user.id,
            message_id=update.message.message_id,
            chat_message_id=new_message.message_id,
            sender_type="user",
        )
    except BadRequest as e:
        if e.message == "Message thread not found":
            await database.delete_user(user.id)
            await message_from_user(update, context)
        elif e.message == "The message can't be copied":
            return
        else:
            raise


async def message_from_admin(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message_thread_id = update.message.message_thread_id
    reply_message_id = None
    if reply_to_message := update.message.reply_to_message:
        reply_message_id = reply_to_message.message_id
    if message_thread_id is None:
        return
    user_id = await database.find_user_id_by_message_thread_id(
        message_thread_id=message_thread_id
    )
    if user_id is None:
        await update.message.reply_text("Не найден пользователь этого форума")
        return
    try:
        reply_to_message_id = None
        if reply_message_id:
            reply_to_message_id = (
                await database.find_message_id_by_chat_message_id_and_message_thread_id(
                    chat_message_id=reply_message_id,
                    message_thread_id=message_thread_id,
                )
            )
        new_message = await update.message.copy(
            chat_id=user_id, reply_to_message_id=reply_to_message_id
        )
        await database.create_message(
            user_id=user_id,
            message_id=new_message.message_id,
            chat_message_id=update.message.message_id,
            sender_type="staff",
        )
    except BadRequest as e:
        if e.message == "The message can't be copied":
            return


async def edited_message_from_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    user = update.effective_user
    original_message = update.edited_message
    original_message_id = original_message.message_id
    try:
        message_thread_id = await get_forum_topic_id(user, context)
    except NoAdminChat:
        await original_message.reply_text("Нет доступа к чату с админами")
        return
    except (NoTopicsAdminChat, NoTopicRightsAdminChat) as e:
        await original_message.forward(chat_id=ADMIN_CHAT_ID)
        await context.bot.send_message(ADMIN_CHAT_ID, e.message)
        return
    try:
        reply_to_message_id = (
            await database.find_chat_message_id_by_message_id_and_user_id(
                message_id=original_message_id, user_id=user.id
            )
        )
        new_message = await original_message.copy(
            chat_id=ADMIN_CHAT_ID,
            message_thread_id=message_thread_id,
            reply_to_message_id=reply_to_message_id,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            text="Обновлённое сообщение", callback_data="1"
                        )
                    ]
                ]
            ),
        )
        await database.create_message(
            user_id=user.id,
            message_id=original_message.message_id,
            chat_message_id=new_message.message_id,
            sender_type="user",
        )
    except BadRequest as e:
        if e.message in ["The message can't be copied", "Message thread not found"]:
            return
        else:
            raise


async def edited_message_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.edited_message.reply_text(
        "Редактировние текста не поддерживается, отправьте новое сообщение"
    )


async def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query

    # Answer the callback query with no text
    await query.answer(text="")


def main() -> None:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.create_tables())
    application = Application.builder().token(config["TELEGRAM_API_TOKEN"]).build()

    application.add_handler(CommandHandler("set_text", set_text))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & ~filters.COMMAND & filters.UpdateType.MESSAGE,
            message_from_user,
        )
    )

    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE
            & ~filters.COMMAND
            & filters.UpdateType.EDITED_MESSAGE,
            edited_message_from_user,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_CHAT_ID) & filters.UpdateType.MESSAGE,
            message_from_admin,
        )
    )
    application.add_handler(
        MessageHandler(
            filters.Chat(ADMIN_CHAT_ID) & filters.UpdateType.EDITED_MESSAGE,
            edited_message_from_admin,
        )
    )
    application.add_error_handler(error_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
