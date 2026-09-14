# -*- coding: utf-8 -*-
import base64
import io
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from config import config
from ai_service import ai_service

logger = logging.getLogger(__name__)
router = Router(name="vision_router")


@router.message(F.photo)
async def handle_photo_message(message: Message, bot: Bot):
    user_id = message.from_user.id
    logger.info("Photo received from user %s", user_id)

    # Permission check for image recognition
    if config.vision_mode == "disabled":
        await message.answer("Распознавание изображений в данный момент отключено администратором.")
        return

    if config.vision_mode == "admin_only" and not config.is_admin(user_id):
        await message.answer("Функция распознавания изображений сейчас доступна только администратору бота.")
        return

    photo = message.photo[-1]
    file_bytes = io.BytesIO()

    try:
        await bot.download(photo, destination=file_bytes)
        file_bytes.seek(0)
        image_base64 = base64.b64encode(file_bytes.read()).decode("utf-8")
    except Exception as e:
        logger.error("Failed to download user photo: %s", e, exc_info=True)
        await message.answer("Не удалось загрузить изображение. Пожалуйста, попробуйте отправить ещё раз.")
        return

    caption = message.caption or ""

    async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
        reply = await ai_service.generate_vision_response(image_base64, caption=caption)

    await message.answer(reply, parse_mode=None)
