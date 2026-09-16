# -*- coding: utf-8 -*-
import html
import logging
from collections import defaultdict
from aiogram import Router, F, Bot
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BusinessConnection,
    BufferedInputFile,
)
from aiogram.utils.chat_action import ChatActionSender
import base64
import io
from config import config
from ai_service import ai_service
from database import is_ai_enabled, save_chat_message, set_setting
from prompts import GIRLFRIEND_USERNAME
from image_service import image_service
from honor_service import honor_service

logger = logging.getLogger(__name__)
router = Router(name="business_router")

# Chats where the owner took over or paused the AI
PAUSED_BUSINESS_CHATS = set()

# Context histories for business chats: chat_id -> list of {"role": "user"|"assistant", "content": str}
BUSINESS_HISTORIES = defaultdict(list)
MAX_BIZ_HISTORY = 6


@router.business_connection()
async def handle_business_connection(business_connection: BusinessConnection, bot: Bot):
    """Triggered when the owner connects or disconnects the bot in Telegram Business."""
    logger.info(
        "Business connection status: id=%s, user=%s, is_enabled=%s",
        business_connection.id,
        business_connection.user.id,
        business_connection.is_enabled,
    )
    if business_connection.id:
        set_setting("business_conn_id", business_connection.id)
        from handlers.admin import update_bot_profile_description
        await update_bot_profile_description(bot, is_ai_enabled(), sync_avatar=False)

    if business_connection.is_enabled:
        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=(
                        "🚀 <b>Бот успешно подключён к вашей «Автоматизации чатов»!</b>\n\n"
                        "Включён <b>полный автопилот через ИИ</b>:\n"
                        "• Когда вам пишут в личку, нейросеть умно и вежливо отвечает от вашего лица\n"
                        "• Если вы сами напишете сообщение в диалог — бот поймёт, что вы вмешались, и уступит вам переписку!"
                    ),
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.error("Failed to notify admin of business connection: %s", e)


@router.business_message(F.text)
async def handle_business_message(message: Message, bot: Bot):
    """Triggered on messages in personal business-connected chats."""
    chat_id = message.chat.id
    sender = message.from_user
    user_text = message.text.strip()
    chat_title = message.chat.title or message.chat.full_name or ""

    if message.business_connection_id:
        set_setting("business_conn_id", message.business_connection_id)

    # 1. OWNER INTERVENTION CHECK:
    # If the message is sent by YOU (the admin/owner):
    if config.is_admin(sender.id):
        if chat_id not in PAUSED_BUSINESS_CHATS:
            PAUSED_BUSINESS_CHATS.add(chat_id)
            logger.info("Owner intervened in chat %s. AI autopilot silently paused for this chat.", chat_id)
        
        # Save owner message to DB history
        save_chat_message(
            chat_id=chat_id,
            chat_title=chat_title,
            user_id=sender.id,
            username=sender.username or "",
            full_name=sender.full_name or "Халид",
            role="assistant",
            text=user_text,
            is_photo=False,
            source="business",
        )
        return

    # 2. IF CHAT IS PAUSED BY OWNER:
    if chat_id in PAUSED_BUSINESS_CHATS:
        logger.info("Chat %s is paused by owner. Bot will not auto-respond.", chat_id)
        return

    # 3. IF AI IS MANUALLY DISABLED IN /admin:
    if not is_ai_enabled():
        return

    # 4. FULL AI AUTOPILOT GENERATION:
    is_girlfriend = bool(sender.username and sender.username.lower().lstrip("@") == GIRLFRIEND_USERNAME)
    logger.info("Autopilot responding to chat_id=%s (is_special=%s)", chat_id, is_girlfriend)

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
        source="business",
    )

    # Save to context history
    history = BUSINESS_HISTORIES[chat_id]
    history.append({"role": "user", "content": user_text})
    if len(history) > MAX_BIZ_HISTORY:
        history[:] = history[-MAX_BIZ_HISTORY:]

    # 0. HONOR DEFENSE: Check if anyone other than girlfriend wrote something disrespectful/unworthy
    if not honor_service.is_exempt(sender.id, sender.username):
        is_dishonor, dishonor_reason = await honor_service.check_dishonor(user_text, ai_service)
        if is_dishonor:
            dignity_reply = honor_service.get_response()
            logger.warning("Honor violation in chat %s by user %s: %s", chat_id, sender.id, dishonor_reason)

            # Answer firmly in the chat
            await message.answer(dignity_reply, parse_mode=None)

            # Save to context history and DB
            history.append({"role": "assistant", "content": dignity_reply})
            save_chat_message(
                chat_id=chat_id,
                chat_title=chat_title,
                user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
                username="bipbup992_robot",
                full_name="Халид (ИИ)",
                role="assistant",
                text=dignity_reply,
                is_photo=False,
                source="business",
            )

            # Alert Xalid immediately in his main bot DM!
            await honor_service.alert_owner(
                bot=bot,
                chat_id=chat_id,
                chat_title=chat_title,
                user=sender,
                user_text=user_text,
                bot_reply=dignity_reply,
                reason=dishonor_reason,
            )
            return

    # 1. Check if user/girlfriend explicitly asked for an image
    is_img_req, raw_prompt = image_service.is_image_request(user_text)
    if is_img_req:
        try:
            await bot.send_chat_action(
                chat_id=chat_id,
                action="upload_photo",
                business_connection_id=message.business_connection_id,
            )
        except Exception as e:
            logger.debug("Chat action error: %s", e)

        logger.info("Business image requested in chat %s", chat_id)
        image_prompt = await ai_service.craft_image_prompt(raw_prompt)
        res = await image_service.generate_image(image_prompt)
        if res:
            img_bytes, _ = res
            caption = image_service.get_caption(is_girlfriend=is_girlfriend, was_requested=True)
            doc = BufferedInputFile(img_bytes, filename="photo.jpg")
            if message.business_connection_id:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=doc,
                    caption=caption,
                    business_connection_id=message.business_connection_id,
                )
            else:
                await message.answer_photo(photo=doc, caption=caption)

            history.append({"role": "assistant", "content": f"[Прислал фото]: {caption}"})
            save_chat_message(
                chat_id=chat_id,
                chat_title=chat_title,
                user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
                username="bipbup992_robot",
                full_name="Халид (ИИ)",
                role="assistant",
                text=f"[Фото] {caption}",
                is_photo=True,
                source="business",
            )
            return
        else:
            fail_msg = "Ой, прости пожалуйста... 🥺 У меня не получилось нарисовать щас! 👉👈 Попроси ещё разок, пожалуйста!" if is_girlfriend else "Чёт генератор щас подвис, черкани ещё раз или чуть другими словами попробуй)"
            await message.answer(fail_msg, parse_mode=None)
            return

    # 2. Check if spontaneous/random image should be sent
    if image_service.should_send_random_image(chat_id):
        try:
            await bot.send_chat_action(
                chat_id=chat_id,
                action="upload_photo",
                business_connection_id=message.business_connection_id,
            )
        except Exception as e:
            logger.debug("Chat action error: %s", e)

        logger.info("Business spontaneous random image triggered for chat %s", chat_id)
        spontaneous_prompt, caption = await ai_service.craft_spontaneous_image(history, is_girlfriend=is_girlfriend)
        res = await image_service.generate_image(spontaneous_prompt)
        if res:
            img_bytes, _ = res
            doc = BufferedInputFile(img_bytes, filename="spontaneous.jpg")
            if message.business_connection_id:
                await bot.send_photo(
                    chat_id=chat_id,
                    photo=doc,
                    caption=caption,
                    business_connection_id=message.business_connection_id,
                )
            else:
                await message.answer_photo(photo=doc, caption=caption)

            history.append({"role": "assistant", "content": f"[Прислал фото]: {caption}"})
            save_chat_message(
                chat_id=chat_id,
                chat_title=chat_title,
                user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
                username="bipbup992_robot",
                full_name="Халид (ИИ)",
                role="assistant",
                text=f"[Фото] {caption}",
                is_photo=True,
                source="business",
            )
            return

    # Send typing indicator in the business chat
    try:
        await bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logger.debug("Chat action error: %s", e)

    # Generate response through LLM
    try:
        ai_reply = await ai_service.generate_business_response(history, is_girlfriend=is_girlfriend)
    except Exception as e:
        logger.error("AI autopilot generation error: %s", e, exc_info=True)
        if is_girlfriend:
            ai_reply = "Ой, прости пожалуйста... 🥺 У меня связь забарахлила на секунду, напиши ещё разок, я очень жду! 👉👈"
        else:
            ai_reply = "Слушай, я щас занят немного, чуть позже напишу тебе нормально!"

    # Save bot reply to memory history
    history.append({"role": "assistant", "content": ai_reply})
    if len(history) > MAX_BIZ_HISTORY:
        history[:] = history[-MAX_BIZ_HISTORY:]

    # Save assistant reply to DB
    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
        username="bipbup992_robot",
        full_name="Халид (ИИ)",
        role="assistant",
        text=ai_reply,
        is_photo=False,
        source="business",
    )

    # Send message in the business chat (without spamming owner's bot DM)
    await message.answer(ai_reply, parse_mode=None)


@router.business_message(F.photo)
async def handle_business_photo(message: Message, bot: Bot):
    """Triggered on photo messages in personal business-connected chats."""
    chat_id = message.chat.id
    sender = message.from_user
    chat_title = message.chat.title or message.chat.full_name or ""
    caption = (message.caption or "").strip()

    if message.business_connection_id:
        set_setting("business_conn_id", message.business_connection_id)

    # If sent by owner:
    if config.is_admin(sender.id):
        if chat_id not in PAUSED_BUSINESS_CHATS:
            PAUSED_BUSINESS_CHATS.add(chat_id)
            logger.info("Owner sent photo in chat %s. AI autopilot paused for this chat.", chat_id)
        
        save_chat_message(
            chat_id=chat_id,
            chat_title=chat_title,
            user_id=sender.id,
            username=sender.username or "",
            full_name=sender.full_name or "Халид",
            role="assistant",
            text=f"[Фото] {caption}".strip(),
            is_photo=True,
            source="business",
        )
        return

    if chat_id in PAUSED_BUSINESS_CHATS or not is_ai_enabled():
        return

    # Check vision permissions
    if config.vision_mode == "disabled":
        logger.info("Vision is disabled, skipping photo in chat %s", chat_id)
        return

    is_girlfriend = bool(sender.username and sender.username.lower().lstrip("@") == GIRLFRIEND_USERNAME)
    logger.info("Autopilot processing photo in chat %s", chat_id)

    photo = message.photo[-1]
    file_bytes = io.BytesIO()
    try:
        await bot.download(photo, destination=file_bytes)
        file_bytes.seek(0)
        image_base64 = base64.b64encode(file_bytes.read()).decode("utf-8")
    except Exception as e:
        logger.error("Failed to download photo in business chat: %s", e)
        return

    # Save user photo message to DB
    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=sender.id,
        username=sender.username or "",
        full_name=sender.full_name or "Собеседник",
        role="user",
        text=caption or "[Фотография]",
        is_photo=True,
        source="business",
    )

    try:
        await bot.send_chat_action(
            chat_id=chat_id,
            action="typing",
            business_connection_id=message.business_connection_id,
        )
    except Exception as e:
        logger.debug("Chat action error: %s", e)

    try:
        ai_reply = await ai_service.generate_vision_response(image_base64, caption=caption, is_girlfriend=is_girlfriend)
    except Exception as e:
        logger.error("Vision response error: %s", e, exc_info=True)
        if is_girlfriend:
            ai_reply = "Ой, прости пожалуйста... 🥺 У меня фотка почему-то не открылась... Скинешь ещё раз, если не трудно? 👉👈"
        else:
            ai_reply = "Слушай, фотка чёт не прогрузилась, скинь ещё разок или черкани текстом."

    # Save bot reply to DB
    save_chat_message(
        chat_id=chat_id,
        chat_title=chat_title,
        user_id=bot.id if hasattr(bot, "id") and bot.id else 8984079656,
        username="bipbup992_robot",
        full_name="Халид (ИИ)",
        role="assistant",
        text=ai_reply,
        is_photo=False,
        source="business",
    )

    await message.answer(ai_reply, parse_mode=None)


@router.callback_query(F.data.startswith("biz_pause:"))
async def cb_business_pause(call: CallbackQuery):
    admin_id = call.from_user.id
    if not config.is_admin(admin_id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    chat_id = int(call.data.split(":")[1])
    PAUSED_BUSINESS_CHATS.add(chat_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="▶️ Возобновить автопилот ИИ",
                    callback_data=f"biz_resume:{chat_id}",
                )
            ]
        ]
    )
    new_text = f"{call.message.html_text}\n\n⏸️ <b>AI-автопилот ПРИОСТАНОВЛЕН. Вы ведёте диалог лично.</b>"
    await call.message.edit_text(new_text, reply_markup=kb, parse_mode="HTML")
    await call.answer("ИИ в этом чате приостановлен!", show_alert=True)


@router.callback_query(F.data.startswith("biz_resume:"))
async def cb_business_resume(call: CallbackQuery):
    admin_id = call.from_user.id
    if not config.is_admin(admin_id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    chat_id = int(call.data.split(":")[1])
    if chat_id in PAUSED_BUSINESS_CHATS:
        PAUSED_BUSINESS_CHATS.remove(chat_id)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏸️ Приостановить ИИ",
                    callback_data=f"biz_pause:{chat_id}",
                )
            ]
        ]
    )
    new_text = f"{call.message.html_text}\n\n▶️ <b>AI-автопилот СНОВА АКТИВЕН для этого чата.</b>"
    await call.message.edit_text(new_text, reply_markup=kb, parse_mode="HTML")
    await call.answer("Автопилот снова включён!", show_alert=True)
