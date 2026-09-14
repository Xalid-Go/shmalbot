# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from ai_service import ai_service
from config import config

logger = logging.getLogger(__name__)
router = Router(name="chat_router")

# Keep last 8 messages per chat (in-memory history)
CHAT_HISTORIES = defaultdict(list)
MAX_HISTORY_MESSAGES = 8


@router.message(CommandStart())
async def handle_start(message: Message):
    CHAT_HISTORIES[message.chat.id].clear()
    is_admin_str = " (Вы администратор бота ⭐)" if config.is_admin(message.from_user.id) else ""
    bot_user = (await message.bot.get_me()).username
    greeting = (
        f"👋 Здравствуйте! Я ваш AI-ассистент в Telegram{is_admin_str}.\n\n"
        "💡 **Как меня использовать:**\n"
        "1. **В этом чате:** задавайте любые вопросы текстом или отправляйте фотографии для распознавания.\n"
        f"2. **В любых чатах и беседах:** введите в строке сообщения `@{bot_user} ваш вопрос`, и выберите готовый ответ для быстрой отправки собеседнику.\n\n"
        "Команды:\n"
        "• `/reset` — очистить историю диалога\n"
        + ("• `/admin` — открыть панель управления ботом\n" if config.is_admin(message.from_user.id) else "")
    )
    await message.answer(greeting, parse_mode="Markdown")


@router.message(Command("reset", "clear"))
async def handle_reset(message: Message):
    CHAT_HISTORIES[message.chat.id].clear()
    await message.answer("🔄 История текущего диалога очищена. Чем могу помочь?")


@router.message(F.text)
async def handle_text_message(message: Message):
    user_text = message.text.strip()
    chat_id = message.chat.id

    # Add user message to history
    history = CHAT_HISTORIES[chat_id]
    history.append({"role": "user", "content": user_text})

    # Keep only last MAX_HISTORY_MESSAGES
    if len(history) > MAX_HISTORY_MESSAGES:
        history[:] = history[-MAX_HISTORY_MESSAGES:]

    # Show "typing" action while waiting for response
    async with ChatActionSender.typing(bot=message.bot, chat_id=chat_id):
        try:
            bot_reply = await ai_service.generate_chat_response(history)
        except Exception as e:
            logger.error("Chat response error: %s", e, exc_info=True)
            bot_reply = "Извините, не удалось сформировать ответ. Попробуйте повторить ваш вопрос."

    # Save bot reply to history
    history.append({"role": "assistant", "content": bot_reply})
    if len(history) > MAX_HISTORY_MESSAGES:
        history[:] = history[-MAX_HISTORY_MESSAGES:]

    # Send plain text reply without entity parsing issues
    await message.answer(bot_reply, parse_mode=None)
