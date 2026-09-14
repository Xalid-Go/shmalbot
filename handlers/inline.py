# -*- coding: utf-8 -*-
import hashlib
import logging
from aiogram import Router
from aiogram.types import (
    InlineQuery,
    InlineQueryResultArticle,
    InputTextMessageContent,
)
from ai_service import ai_service

logger = logging.getLogger(__name__)
router = Router(name="inline_router")


@router.inline_query()
async def handle_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()

    # If query is empty or too short, show placeholder hint without querying LLM
    if len(query) < 2:
        hint_id = "hint_help"
        results = [
            InlineQueryResultArticle(
                id=hint_id,
                title="💡 Задайте вопрос ассистенту...",
                description="Напишите любой вопрос после @имени_бота, например: @drugsAi_bot что такое квантовый компьютер?",
                input_message_content=InputTextMessageContent(
                    message_text="Напишите вопрос после имени бота, чтобы получить быстрый ответ в чат.",
                    parse_mode=None,
                ),
            )
        ]
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
                title=f"💬 Ответ на: {query[:35]}",
                description=snippet,
                input_message_content=InputTextMessageContent(
                    message_text=answer,
                    parse_mode=None,  # Immune to HTML/Markdown parse errors
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
                title="⚠️ Ошибка генерации",
                description="Не удалось сгенерировать ответ, нажмите чтобы отправить уведомление",
                input_message_content=InputTextMessageContent(
                    message_text="Извините, произошла ошибка при генерации ответа. Попробуйте ещё раз через несколько секунд.",
                    parse_mode=None,
                ),
            )
        ]
        await inline_query.answer(results=fallback_results, cache_time=1, is_personal=True)
