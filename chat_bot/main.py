import asyncio
import logging
import json
from typing import Optional

from telegram import (
    Update,
    User,
    ForumTopic,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
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
    """Посылает приветственный текст"""
    await update.message.reply_text(await database.get_text())


async def help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Посылает приветственный текст"""
    await update.message.reply_text(
        "\n\n".join(
            [
                await database.get_text(),
                "Также можно устнаовить режим работы бота с помощью команды /set_prompt",
            ]
        )
    )


async def set_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обновляет приветственный текст"""
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
    """Возвращает forum_topic_id. Если он не создан - создаёт"""
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


async def get_message_thread_id_or_handle_exceptions(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> Optional[int]:
    user = update.effective_user
    try:
        message_thread_id = await get_forum_topic_id(user, context)
    except NoAdminChat:
        await update.message.reply_text("Нет доступа к чату с админами")
        return None
    except (NoTopicsAdminChat, NoTopicRightsAdminChat) as e:
        await update.message.forward(chat_id=ADMIN_CHAT_ID)
        await context.bot.send_message(ADMIN_CHAT_ID, e.message)
        return None
    return message_thread_id


async def forward_message_to_admins(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    reply_message_id: int | None = None,
) -> None:
    user = update.effective_user
    message_thread_id = await get_message_thread_id_or_handle_exceptions(
        update, context
    )
    if message_thread_id is None:
        return

    reply_to_chat_message_id = None
    if reply_message_id:
        reply_to_chat_message_id = (
            await database.find_chat_message_id_by_message_id_and_user_id(
                message_id=reply_message_id, user_id=user.id
            )
        )

    new_message = await update.message.copy(
        chat_id=ADMIN_CHAT_ID,
        message_thread_id=message_thread_id,
        reply_to_message_id=reply_to_chat_message_id,
    )
    await database.create_message(
        user_id=user.id,
        message_id=update.message.message_id,
        chat_message_id=new_message.message_id,
        sender_type="user",
    )


async def forward_message_to_user(
    update: Update, message_thread_id: int, reply_message_id: int = None
) -> None:
    user_id = await database.find_user_id_by_message_thread_id(
        message_thread_id=message_thread_id
    )
    if user_id is None:
        await update.message.reply_text("Не найден пользователь этого форума")
        return

    reply_to_user_message_id = None
    if reply_message_id:
        reply_to_user_message_id = (
            await database.find_message_id_by_chat_message_id_and_message_thread_id(
                chat_message_id=reply_message_id, message_thread_id=message_thread_id
            )
        )

    new_message = await update.message.copy(
        chat_id=user_id, reply_to_message_id=reply_to_user_message_id
    )
    await database.create_message(
        user_id=user_id,
        message_id=new_message.message_id,
        chat_message_id=update.message.message_id,
        sender_type="staff",
    )


async def message_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    reply_message_id = (
        update.message.reply_to_message.message_id
        if update.message.reply_to_message
        else None
    )
    try:
        await forward_message_to_admins(update, context, reply_message_id)
    except BadRequest as e:
        if e.message == "Message thread not found":
            # Тред удалён из чата, но не удалён из базы данных
            await database.delete_user(update.effective_user.id)
            await message_from_user(update, context)
        elif e.message == "The message can't be copied":
            return
        else:
            raise


async def message_from_admin(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    message_thread_id = update.message.message_thread_id
    reply_message_id = (
        update.message.reply_to_message.message_id
        if update.message.reply_to_message
        else None
    )

    if message_thread_id is None:
        return

    try:
        await forward_message_to_user(update, message_thread_id, reply_message_id)
    except BadRequest as e:
        if e.message == "The message can't be copied":
            return


async def forward_edited_message_to_admins(
    update: Update, context: ContextTypes.DEFAULT_TYPE, original_message_id: int
) -> None:
    message_thread_id = await get_message_thread_id_or_handle_exceptions(
        update, context
    )
    if message_thread_id is None:
        return

    user = update.effective_user
    original_message = update.edited_message
    reply_to_chat_message_id = (
        await database.find_chat_message_id_by_message_id_and_user_id(
            message_id=original_message_id, user_id=user.id
        )
    )

    new_message = await original_message.copy(
        chat_id=ADMIN_CHAT_ID,
        message_thread_id=message_thread_id,
        reply_to_message_id=reply_to_chat_message_id,
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton(text="Обновлённое сообщение", callback_data="-1")]]
        ),
    )

    await database.create_message(
        user_id=user.id,
        message_id=original_message.message_id,
        chat_message_id=new_message.message_id,
        sender_type="user",
    )


async def edited_message_from_user(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    original_message_id = update.edited_message.message_id
    try:
        await forward_edited_message_to_admins(update, context, original_message_id)
    except BadRequest as e:
        if e.message in ["The message can't be copied", "Message thread not found"]:
            return
        else:
            raise


async def edited_message_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.edited_message.reply_text(
        "Редактировние текста не поддерживается, отправьте новое сообщение"
    )


async def set_variant(number: int, update: Update, context: CallbackContext):
    user = update.effective_user
    forum_id = await get_forum_topic_id(user, context)
    variant = config["PROMPT"][number]
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        message_thread_id=forum_id,
        text=f"Пользовтаель установил режим бота <b>{variant}</b>",
        parse_mode="html",
    )
    await context.bot.send_message(
        chat_id=user.id, text=f"Вы выбрали <b>{variant}</b>", parse_mode="html"
    )


async def handle_callback_query(update: Update, context: CallbackContext):
    query = update.callback_query
    if query is None:
        return
    number = int(query.data)
    if number > -1:
        await set_variant(number, update, context)
    # Answer the callback query with no text
    await query.answer(text="")


async def set_prompt(update: Update, context: CallbackContext):
    await update.message.reply_text(
        "Выберите режим работы бота",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text=f"{num+1}. {variant}", callback_data=str(num)
                    )
                ]
                for num, variant in enumerate(config["PROMPT"])
            ]
        ),
    )


def main() -> None:
    loop = asyncio.get_event_loop()
    loop.run_until_complete(database.create_tables())
    application = Application.builder().token(config["TELEGRAM_API_TOKEN"]).build()

    application.add_handler(CommandHandler("set_text", set_text))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help))
    application.add_handler(CommandHandler("set_prompt", set_prompt))
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
    loop.run_until_complete(
        application.bot.set_my_commands(
            [
                BotCommand("help", "Показать справку"),
                BotCommand("set_prompt", "Установить режим работы бота"),
            ]
        )
    )

    application.run_polling()


if __name__ == "__main__":
    main()
