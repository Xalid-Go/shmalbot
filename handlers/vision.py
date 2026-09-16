# -*- coding: utf-8 -*-
import base64
import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from config import config
from ai_service import ai_service
from database import is_ai_enabled, save_chat_message
from prompts import GIRLFRIEND_USERNAME

logger = logging.getLogger(__name__)
router = Router(name="vision_router")


@router.message(F.photo)
async def handle_photo_message(message: Message, bot: Bot):
    if not is_ai_enabled() and not config.is_admin(message.from_user.id):
        return

    user_id = message.from_user.id
    sender = message.from_user
    chat_id = message.chat.id
    chat_title = message.chat.title or sender.full_name or ""
    logger.info("Photo received from user %s", user_id)

    # Permission check for image recognition
    if config.vision_mode == "disabled":
        await message.answer("Я пока фотки отключил, пиши текстом лучше!")
        return

    if config.vision_mode == "admin_only" and not config.is_admin(user_id):
        await message.answer("Фотки мне пока только шеф может слать, пиши словами)")
        return

    photo = message.photo[-1]
    file_bytes = io.BytesIO()

    try:
        await bot.download(photo, destination=file_bytes)
        file_bytes.seek(0)
        image_base64 = base64.b64encode(file_bytes.read()).decode("utf-8")
    except Exception as e:
        logger.error("Failed to download user photo: %s", e, exc_info=True)
        await message.answer("Что-то фотка не прогрузилась, скинь ещё раз!")
        return

    caption = message.caption or ""

    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=sender.id,
        username=sender.username or "",
        full_name=sender.full_name or "Собеседник",
        role="user",
        text=caption or "[Фотография]",
        is_photo=True,
        source="direct",
    )

    is_girlfriend = bool(sender.username and sender.username.lower().lstrip("@") == GIRLFRIEND_USERNAME)
    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        reply = await ai_service.generate_vision_response(image_base64, caption=caption, is_girlfriend=is_girlfriend)

    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
        username="bipbup992_robot",
        full_name="Халид (ИИ)",
        role="assistant",
        text=reply,
        is_photo=False,
        source="direct",
    )

    await message.answer(reply, parse_mode=None)
