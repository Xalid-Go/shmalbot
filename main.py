# -*- coding: utf-8 -*-
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import config
from database import init_db
from handlers import (
    admin_router,
    business_router,
    vision_router,
    inline_router,
    chat_router,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger("ai_assistant_bot")


import socket
from aiogram.client.session.aiohttp import AiohttpSession

async def main():
    logger.info("Initializing Bot and Database...")
    init_db()

    # Configure session: force IPv4 to avoid container IPv6 timeout hangs on cloud hosts
    session = AiohttpSession(timeout=30.0)
    session._connector_init["family"] = socket.AF_INET

    bot = Bot(
        token=config.bot_token,
        session=session,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = Dispatcher()

    # Register routers in priority order
    dp.include_router(admin_router)
    dp.include_router(business_router)
    dp.include_router(vision_router)
    dp.include_router(inline_router)
    dp.include_router(chat_router)

    # Verify bot credentials with automatic retries
    bot_info = None
    for attempt in range(1, 6):
        try:
            logger.info("Connecting to Telegram API (attempt %d/5)...", attempt)
            bot_info = await bot.get_me()
            break
        except Exception as e:
            logger.warning("Telegram API connection attempt %d/5 failed: %s. Retrying in 3s...", attempt, e)
            await asyncio.sleep(3)

    if not bot_info:
        logger.error("Failed to connect to Telegram API after 5 attempts. Exiting.")
        await bot.session.close()
        return

    logger.info("Bot started successfully!")
    logger.info("Name: %s", bot_info.first_name)
    logger.info("Username: @%s", bot_info.username)
    logger.info("Inline mode ready. Invoke via: @%s <запрос>", bot_info.username)

    # Drop old updates so bot starts fresh
    try:
        await bot.delete_webhook(drop_pending_updates=True)
    except Exception as e:
        logger.warning("Could not delete webhook: %s", e)

    # Sync bot profile description with current AI state
    try:
        from database import is_ai_enabled
        from handlers.admin import update_bot_profile_description
        await update_bot_profile_description(bot, is_ai_enabled())
    except Exception as e:
        logger.warning("Could not sync profile description on startup: %s", e)

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Pach Bot stopped.")
