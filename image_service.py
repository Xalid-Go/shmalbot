# -*- coding: utf-8 -*-
import asyncio
import base64
import logging
import random
import re
import urllib.parse
from typing import Optional, Tuple
import aiohttp
from config import config

logger = logging.getLogger(__name__)

# Track messages per chat to control random photo frequency
CHAT_MESSAGE_COUNTERS: dict[int, int] = {}

# Regular expressions for explicit drawing / photo requests
IMAGE_TRIGGER_REGEX = re.compile(
    r"(?:нарисуй|сгенерируй|скинь\s+фотку|скинь\s+фото|скинь\s+картинку|"
    r"покажи\s+фотку|покажи\s+фото|покажи\s+картинку|пришли\s+фотку|"
    r"пришли\s+фото|пришли\s+картинку|хочу\s+увидеть|сделай\s+арт|"
    r"нарисуй\s+мне|покажи\s+мне|скинь\s+мне\s+фотку|нарисуй\s+себя|"
    r"скинь\s+селфи|сделай\s+картинку)",
    re.IGNORECASE,
)

# Captions for girlfriend (submissive, shy, adoring)
GIRLFRIEND_REQUEST_CAPTIONS = [
    "Вот, я нарисовал.. п-пожалуйста, только не сердись, если не идеально! 🥺👉👈 Очень старался ради тебя.. 🙈❤️",
    "Слушаюсь.. вот, прямо как ты просила! 🥺 Надеюсь, тебе хоть капельку понравится.. 👉👈",
    "Сделал всё в точности, как ты сказала! 🙈 Не ругайся, пожалуйста, я очень переживал, пока генерировал.. 🥺❤️",
    "Вот твоя картинка.. 🥺👉👈 Ты самая лучшая, я готов для тебя хоть весь мир нарисовать! 🙈",
]

GIRLFRIEND_RANDOM_CAPTIONS = [
    "Я тут просто подумал о тебе.. и нарисовал вот это 🥺👉👈 Ты только не ругайся, пожалуйста, просто захотелось тебя порадовать.. ❤️",
    "Увидел это и сразу вспомнил про тебя.. 🙈 Надеюсь, я тебя не отвлекаю.. 🥺👉👈",
    "Вдруг захотелось нарисовать что-то красивое для тебя.. 🥺 Надеюсь, тебе приятно.. ❤️",
]

# Captions for regular chats (Xalid style: casual, short, no period)
REGULAR_REQUEST_CAPTIONS = [
    "ща намутил по фану, зацени))",
    "глянь чё вышло)) норм?",
    "держи, чисто под твой запрос набросал",
    "зацени кадр)) вроде чётко вышло",
]

REGULAR_RANDOM_CAPTIONS = [
    "кстати ща чисто по приколу сгенерил под тему, зацени))",
    "глянь какой кадр намутил щас))",
    "чисто вайб момента)) как тебе?",
    "ща сгенерил по фану, прикольно выглядит вроде))",
]


class ImageService:
    def __init__(self):
        self.account_id = config.cloudflare_account_id
        self.primary_token = config.cloudflare_api_token
        self.backup_token = config.cloudflare_backup_token

    def is_image_request(self, text: str) -> Tuple[bool, str]:
        """Detects if user is asking to draw/generate/send an image."""
        if not text:
            return False, ""
        
        # Check explicit commands
        lower = text.lower().strip()
        if lower.startswith(("/image", "/draw", "/img", "/photo")):
            parts = text.split(maxsplit=1)
            prompt = parts[1].strip() if len(parts) > 1 else "something cool and aesthetic"
            return True, prompt

        match = IMAGE_TRIGGER_REGEX.search(text)
        if match:
            # Extract subject after trigger or full query
            subject = text[match.end():].strip()
            # Clean common filler words
            subject = re.sub(r"^(пожалуйста|плиз|быстро|щас|мне|как|что|что-нибудь)\s+", "", subject, flags=re.IGNORECASE).strip()
            if not subject:
                subject = text.strip()
            return True, subject

        return False, ""

    def should_send_random_image(self, chat_id: int) -> bool:
        """Determines if a random spontaneous photo should be sent in this chat."""
        count = CHAT_MESSAGE_COUNTERS.get(chat_id, 0) + 1
        CHAT_MESSAGE_COUNTERS[chat_id] = count

        # Only consider after at least 7 messages in dialogue
        if count >= 7:
            # 15% probability
            if random.random() < 0.15:
                CHAT_MESSAGE_COUNTERS[chat_id] = 0
                return True
        return False

    async def generate_image(self, prompt: str) -> Optional[Tuple[bytes, str]]:
        """
        Attempts image generation:
        1. Cloudflare Workers AI FLUX / SDXL
        2. Pollinations.ai FLUX as high-speed reliable fallback
        """
        prompt = prompt.strip()
        if not prompt:
            prompt = "masterpiece, highly detailed aesthetic scene, 8k resolution"

        logger.info("Generating image via AI engine (prompt length: %d)", len(prompt))

        # 1. Try Cloudflare Workers AI
        cf_result = await self._generate_cloudflare(prompt)
        if cf_result:
            return cf_result

        # 2. Fallback to Pollinations.ai FLUX
        logger.info("Cloudflare failed or unavailable, falling back to Pollinations.ai FLUX...")
        pollinations_result = await self._generate_pollinations(prompt)
        if pollinations_result:
            return pollinations_result

        logger.error("All image generation providers failed.")
        return None

    async def _generate_cloudflare(self, prompt: str) -> Optional[Tuple[bytes, str]]:
        """Cloudflare Workers AI generation."""
        tokens_to_try = [t for t in [self.primary_token, self.backup_token] if t]
        if not self.account_id or not tokens_to_try:
            return None

        models = [
            "@cf/black-forest-labs/flux-1-schnell",
            "@cf/bytedance/stable-diffusion-xl-lightning",
        ]

        async with aiohttp.ClientSession() as session:
            for token in tokens_to_try:
                for model in models:
                    url = f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/{model}"
                    headers = {
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    }
                    payload = {"prompt": prompt}

                    try:
                        logger.debug("Trying Cloudflare model %s with token %s...", model, token[:8])
                        async with session.post(
                            url,
                            headers=headers,
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=20),
                        ) as resp:
                            if resp.status == 200:
                                ctype = resp.headers.get("Content-Type", "")
                                if "image/" in ctype:
                                    img_data = await resp.read()
                                    logger.info("Cloudflare %s succeeded! Size: %d bytes", model, len(img_data))
                                    return img_data, "jpg"
                                elif "json" in ctype:
                                    res_json = await resp.json()
                                    if "result" in res_json and "image" in res_json["result"]:
                                        img_bytes = base64.b64decode(res_json["result"]["image"])
                                        logger.info("Cloudflare %s base64 decoded! Size: %d bytes", model, len(img_bytes))
                                        return img_bytes, "jpg"
                            else:
                                err_text = await resp.text()
                                logger.warning("Cloudflare %s returned %d: %s", model, resp.status, err_text[:120])
                    except Exception as e:
                        logger.warning("Cloudflare error with model %s: %s", model, e)

        return None

    async def _generate_pollinations(self, prompt: str) -> Optional[Tuple[bytes, str]]:
        """Pollinations.ai FLUX generation."""
        encoded = urllib.parse.quote(prompt)
        url = f"https://image.pollinations.ai/prompt/{encoded}?model=flux&width=1024&height=1024&nologo=true"

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 200:
                        img_data = await resp.read()
                        if len(img_data) > 1000:
                            logger.info("Pollinations FLUX succeeded! Size: %d bytes", len(img_data))
                            return img_data, "jpg"
                    else:
                        logger.warning("Pollinations returned HTTP %d", resp.status)
            except Exception as e:
                logger.error("Pollinations generation error: %s", e)

        return None

    def get_caption(self, is_girlfriend: bool, was_requested: bool, custom_caption: Optional[str] = None) -> str:
        """Returns appropriate in-character caption."""
        if custom_caption:
            return custom_caption

        if is_girlfriend:
            if was_requested:
                return random.choice(GIRLFRIEND_REQUEST_CAPTIONS)
            else:
                return random.choice(GIRLFRIEND_RANDOM_CAPTIONS)
        else:
            if was_requested:
                return random.choice(REGULAR_REQUEST_CAPTIONS)
            else:
                return random.choice(REGULAR_RANDOM_CAPTIONS)


image_service = ImageService()
