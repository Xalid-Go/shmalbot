# -*- coding: utf-8 -*-
import hashlib
import logging
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from ai_service import ai_service
from config import config
from database import is_ai_enabled, get_recent_chats

logger = logging.getLogger(__name__)
router = Router(name="inline_router")


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    if not is_ai_enabled() and not config.is_admin(inline_query.from_user.id):
        lock_results = [
            InlineQueryResultArticle(
                id="ai_disabled",
                title="💤 ИИ-собеседник отключен",
                description="Владелец бота временно отключил генерацию ответов в /admin",
                input_message_content=InputTextMessageContent(
                    message_text="ИИ-собеседник в данный момент отключен.",
                    parse_mode=None,
                ),
            )
        ]
        await inline_query.answer(results=lock_results, cache_time=2, is_personal=True)
        return

    query = inline_query.query.strip()
    is_admin = config.is_admin(inline_query.from_user.id)

    # 1. Admin inline dialog exporter
    if is_admin and query.lower() in ("export", "logs", "диалоги", "chats", "чат"):
        chats = get_recent_chats(limit=10)
        bot_user = (await inline_query.bot.get_me()).username
        export_results = []
        for c in chats:
            c_id = c["chat_id"]
            c_name = c["full_name"] or c["chat_title"] or f"Чат {c_id}"
            u_info = f"@{c['username']} • " if c["username"] else ""
            cnt = c["message_count"]
            deep_link = f"https://t.me/{bot_user}?start=export_{c_id}"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[
                    InlineKeyboardButton(text="📥 Открыть и скачать HTML", url=deep_link)
                ]]
            )
            export_results.append(
                InlineQueryResultArticle(
                    id=f"exp_{c_id}",
                    title=f"📜 {c_name} [{cnt} сообщ.]",
                    description=f"{u_info}Нажмите для выгрузки HTML",
                    input_message_content=InputTextMessageContent(
                        message_text=f"📜 <b>История диалога:</b> {c_name}\nВсего сообщений: {cnt}\n\nНажмите кнопку ниже, чтобы получить готовый HTML-файл:",
                        parse_mode="HTML",
                    ),
                    reply_markup=kb,
                )
            )
        if export_results:
            await inline_query.answer(results=export_results, cache_time=1, is_personal=True)
            return

    # If query is empty or too short, show placeholder hint without querying LLM
    if len(query) < 2:
        hint_id = "hint_help"
        bot_user = (await inline_query.bot.get_me()).username
        results = [
            InlineQueryResultArticle(
                id=hint_id,
                title="💬 Напиши вопрос или фразу...",
                description=f"Например: @{bot_user} чё делаешь вечером?",
                input_message_content=InputTextMessageContent(
                    message_text="Напиши вопрос после имени бота, чтобы отправить быстрый ответ в чат.",
                    parse_mode=None,
                ),
            )
        ]
        if is_admin:
            results.append(
                InlineQueryResultArticle(
                    id="hint_exp",
                    title="📜 Экспорт диалогов (HTML)",
                    description=f"Напишите: @{bot_user} export",
                    input_message_content=InputTextMessageContent(
                        message_text="Напишите @bipbup992_robot export для выбора диалогов.",
                        parse_mode=None,
                    ),
                )
            )
        await inline_query.answer(results=results, cache_time=1, is_personal=True)
        return

    try:
        # Generate quick inline answer
        answer = await ai_service.generate_inline_response(query)

        # Unique ID based on query and answer
        result_id = hashlib.md5(f"{query}_{answer}".encode("utf-8")).hexdigest()

        # Snippet for preview
        snippet = (answer[:90] + "...") if len(answer) > 90 else answer

        results = [
            InlineQueryResultArticle(
                id=result_id,
                title=f"🗣️ Ответ: {query[:35]}",
                description=snippet,
                input_message_content=InputTextMessageContent(
                    message_text=answer,
                    parse_mode=None,
                ),
            )
        ]

        await inline_query.answer(results=results, cache_time=5, is_personal=True)

    except Exception as e:
        logger.error("Error in inline query: %s", e, exc_info=True)
        err_id = hashlib.md5(query.encode("utf-8")).hexdigest()
        fallback_results = [
            InlineQueryResultArticle(
                id=err_id,
                title="⚠️ Сбой связи",
                description="Связь подглючивает, нажми чтобы повторить",
                input_message_content=InputTextMessageContent(
                    message_text="Слушай, связь что-то подглючивает щас с телефона, повтори чуть позже!",
                    parse_mode=None,
                ),
            )
        ]
        await inline_query.answer(results=fallback_results, cache_time=1, is_personal=True)
