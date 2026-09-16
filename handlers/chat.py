# -*- coding: utf-8 -*-
import logging
from collections import defaultdict
from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender
from ai_service import ai_service
from config import config
from database import is_ai_enabled, save_chat_message, get_chat_history, get_recent_chats
from html_exporter import generate_chat_html
from aiogram.types import BufferedInputFile
from prompts import GIRLFRIEND_USERNAME
from image_service import image_service
from honor_service import honor_service

logger = logging.getLogger(__name__)
router = Router(name="chat_router")

# Keep last 8 messages per chat (in-memory history)
CHAT_HISTORIES = defaultdict(list)
MAX_HISTORY_MESSAGES = 8


@router.message(CommandStart())
async def handle_start(message: Message):
    CHAT_HISTORIES[message.chat.id].clear()
    text_parts = (message.text or "").split(maxsplit=1)
    
    # Check for deep-link export request from inline: /start export_<chat_id>
    if len(text_parts) > 1 and text_parts[1].startswith("export_") and config.is_admin(message.from_user.id):
        target_str = text_parts[1].replace("export_", "")
        try:
            target_chat_id = int(target_str)
            msgs = get_chat_history(target_chat_id)
            if not msgs:
                await message.answer(f"В чате {target_chat_id} пока нет сохранённых сообщений.")
                return
            
            # Find metadata
            meta = {"chat_id": target_chat_id, "full_name": msgs[0].get("full_name"), "username": msgs[0].get("username")}
            html_content = generate_chat_html(target_chat_id, msgs, meta)
            doc = BufferedInputFile(html_content.encode("utf-8"), filename=f"chat_{target_chat_id}.html")
            await message.answer_document(
                document=doc,
                caption=f"📜 <b>История диалога</b> ({len(msgs)} сообщений)\n👤 {meta.get('full_name')} (@{meta.get('username')})",
                parse_mode="HTML"
            )
            return
        except Exception as e:
            logger.error("Deep link export error: %s", e)

    bot_user = (await message.bot.get_me()).username
    greeting = (
        "О, здорова! 👋\n\n"
        "Я на связи. Чё как сам? Рассказывай, о чём побазарим сегодня — за жизнь, по делам, за тачки, музыку или просто поболтаем?\n\n"
        "Кстати:\n"
        "• Можешь скидывать любые фотки — заценю и прокомментирую!\n"
        "• Можешь просить нарисовать что угодно: <code>нарисуй котика</code> или <code>/image неоновый город</code>!\n"
        f"• Можешь звать меня в любые чаты через <code>@{bot_user} вопрос</code>."
        + ("\n\n• /admin — панель управления и рубильник ИИ\n• /export — выгрузить сохранённые диалоги в HTML" if config.is_admin(message.from_user.id) else "")
    )
    await message.answer(greeting, parse_mode="HTML")


@router.message(Command("reset", "clear"))
async def handle_reset(message: Message):
    CHAT_HISTORIES[message.chat.id].clear()
    await message.answer("С чистого листа погнали! Чё расскажешь?")


@router.message(Command("image", "draw", "img", "photo"))
async def handle_draw_command(message: Message):
    """Command to generate an image explicitly."""
    text_parts = (message.text or "").split(maxsplit=1)
    prompt_text = text_parts[1].strip() if len(text_parts) > 1 else "cool cyberpunk city aesthetic"
    sender = message.from_user
    is_girlfriend = bool(sender.username and sender.username.lower().lstrip("@") == GIRLFRIEND_USERNAME)

    async with ChatActionSender.upload_photo(bot=message.bot, chat_id=message.chat.id):
        image_prompt = await ai_service.craft_image_prompt(prompt_text)
        res = await image_service.generate_image(image_prompt)
        if res:
            img_bytes, _ = res
            caption = image_service.get_caption(is_girlfriend=is_girlfriend, was_requested=True)
            doc = BufferedInputFile(img_bytes, filename="generated.jpg")
            await message.answer_photo(photo=doc, caption=caption)
            save_chat_message(
                chat_id=message.chat.id,
                chat_title=message.chat.title or sender.full_name or "",
                user_id=message.bot.id if hasattr(message.bot, "id") and message.bot.id else 8984079656,
                username="bipbup992_robot",
                full_name="Халид (ИИ)",
                role="assistant",
                text=f"[Фото] {caption}",
                is_photo=True,
                source="direct",
            )
            return

    await message.answer("Чёт не вышло сгенерировать щас, попробуй чуть позже или другими словами!")


@router.message(F.text)
async def handle_text_message(message: Message):
    user_text = message.text.strip()
    chat_id = message.chat.id
    sender = message.from_user
    chat_title = message.chat.title or sender.full_name or ""

    # If AI is globally turned off by owner
    if not is_ai_enabled() and not config.is_admin(sender.id):
        return

    is_girlfriend = bool(sender.username and sender.username.lower().lstrip("@") == GIRLFRIEND_USERNAME)

    # Save incoming user message to DB
    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=sender.id,
        username=sender.username or "",
        full_name=sender.full_name or "Собеседник",
        role="user",
        text=user_text,
        is_photo=False,
        source="direct",
    )

    # Add user message to in-memory context history
    history = CHAT_HISTORIES[chat_id]
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_HISTORY_MESSAGES:
        history[:] = history[-MAX_HISTORY_MESSAGES:]

    # 0. HONOR DEFENSE: Check if message is disrespectful/unworthy (girlfriend is exempt)
    if not honor_service.is_exempt(sender.id, sender.username):
        is_dishonor, dishonor_reason = await honor_service.check_dishonor(user_text, ai_service)
        if is_dishonor:
            dignity_reply = honor_service.get_response()
            logger.warning("Honor violation in direct chat %s by user %s: %s", chat_id, sender.id, dishonor_reason)

            # Answer firmly
            await message.answer(dignity_reply, parse_mode=None)

            # Save to context history and DB
            history.append({"role": "assistant", "content": dignity_reply})
            save_chat_message(
                chat_id=chat_id,
                chat_title=chat_title,
                user_id=message.bot.id if hasattr(message.bot, "id") and message.bot.id else 8984079656,
                username="bipbup992_robot",
                full_name="Халид (ИИ)",
                role="assistant",
                text=dignity_reply,
                is_photo=False,
                source="direct",
            )

            # Alert Xalid immediately in his main bot DM!
            await honor_service.alert_owner(
                bot=message.bot,
                chat_id=chat_id,
                chat_title=chat_title,
                user=sender,
                user_text=user_text,
                bot_reply=dignity_reply,
                reason=dishonor_reason,
            )
            return

    # 1. Check if user asked to draw/send an image
    is_img_req, raw_prompt = image_service.is_image_request(user_text)
    if is_img_req:
        async with ChatActionSender.upload_photo(bot=message.bot, chat_id=chat_id):
            logger.info("Image generation requested in chat %s", chat_id)
            image_prompt = await ai_service.craft_image_prompt(raw_prompt)
            res = await image_service.generate_image(image_prompt)
            if res:
                img_bytes, _ = res
                caption = image_service.get_caption(is_girlfriend=is_girlfriend, was_requested=True)
                doc = BufferedInputFile(img_bytes, filename="photo.jpg")
                await message.answer_photo(photo=doc, caption=caption)

                history.append({"role": "assistant", "content": f"[Прислал фото]: {caption}"})
                save_chat_message(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    user_id=message.bot.id if hasattr(message.bot, "id") and message.bot.id else 8984079656,
                    username="bipbup992_robot",
                    full_name="Халид (ИИ)",
                    role="assistant",
                    text=f"[Фото] {caption}",
                    is_photo=True,
                    source="direct",
                )
                return

    # 2. Check if spontaneous/random image should be sent
    if image_service.should_send_random_image(chat_id):
        async with ChatActionSender.upload_photo(bot=message.bot, chat_id=chat_id):
            logger.info("Spontaneous random image triggered for chat %s", chat_id)
            spontaneous_prompt, caption = await ai_service.craft_spontaneous_image(history, is_girlfriend=is_girlfriend)
            res = await image_service.generate_image(spontaneous_prompt)
            if res:
                img_bytes, _ = res
                doc = BufferedInputFile(img_bytes, filename="spontaneous.jpg")
                await message.answer_photo(photo=doc, caption=caption)

                history.append({"role": "assistant", "content": f"[Прислал фото]: {caption}"})
                save_chat_message(
                    chat_id=chat_id,
                    chat_title=chat_title,
                    user_id=message.bot.id if hasattr(message.bot, "id") and message.bot.id else 8984079656,
                    username="bipbup992_robot",
                    full_name="Халид (ИИ)",
                    role="assistant",
                    text=f"[Фото] {caption}",
                    is_photo=True,
                    source="direct",
                )
                return

    # 3. Regular text response
    async with ChatActionSender.typing(bot=message.bot, chat_id=chat_id):
        try:
            bot_reply = await ai_service.generate_chat_response(history, is_girlfriend=is_girlfriend)
        except Exception as e:
            logger.error("Chat response error: %s", e, exc_info=True)
            if is_girlfriend:
                bot_reply = "Ой, прости пожалуйста... 🥺 У меня связь забарахлила на секунду, напиши ещё разок, я очень жду! 👉👈"
            else:
                bot_reply = "Слушай, связь что-то подглючивает щас с телефона... Черкани ещё разок через минуту."

    # Save bot reply to in-memory context history
    history.append({"role": "assistant", "content": bot_reply})
    if len(history) > MAX_HISTORY_MESSAGES:
        history[:] = history[-MAX_HISTORY_MESSAGES:]

    # Save assistant reply to DB
    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=message.bot.id if hasattr(message.bot, "id") and message.bot.id else 8984079656,
        username="bipbup992_robot",
        full_name="Халид (ИИ)",
        role="assistant",
        text=bot_reply,
        is_photo=False,
        source="direct",
    )

    # Send plain text reply without entity parsing issues
    await message.answer(bot_reply, parse_mode=None)
