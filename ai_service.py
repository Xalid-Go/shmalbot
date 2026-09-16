# -*- coding: utf-8 -*-
import asyncio
import logging
import re
import time
from openai import AsyncOpenAI
from config import config
from prompts import DIGITAL_TWIN_PROMPT, INLINE_PROMPT_EXTRA, GIRLFRIEND_PROMPT

logger = logging.getLogger(__name__)

EMERGENCY_FALLBACK = "Слушай, связь что-то подглючивает щас с телефона... Черкани ещё разок через минуту."


def clean_model_output(text: str) -> str:
    """Removes reasoning tags (<think>...</think>), raw stop artifacts, and trailing dots."""
    if not text:
        return ""
    # Strip <think>...</think> tags and internal reasoning blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip trailing raw model stop tokens
    text = re.sub(r"(stop|<\|im_end\|>|</s>|<\|endoftext\|>)\s*$", "", text, flags=re.IGNORECASE)
    text = text.strip()
    # Strip a single trailing dot at the very end of message (leaves ... or ? or ! or ) intact)
    if text.endswith(".") and not text.endswith(".."):
        text = text[:-1].rstrip()
    return text


class AIService:
    def __init__(self):
        self.client = AsyncOpenAI(
            api_key=config.api_key,
            base_url=config.base_url,
            timeout=10.0,
            max_retries=0,  # Do not pause/retry on broken models; fail fast to fallback!
        )

    async def _call_llm(
        self,
        model: str,
        messages: list[dict],
        max_tokens: int = 350,
        timeout: float = 6.0,
    ) -> str:
        response = await self.client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=0.85,
            timeout=timeout,
        )
        content = response.choices[0].message.content or ""
        cleaned = clean_model_output(content)
        if not cleaned:
            raise ValueError("Empty response from model")
        return cleaned

    async def generate_response(
        self,
        messages: list[dict],
        is_inline: bool = False,
        max_tokens: int = 350,
    ) -> str:
        """Attempts generation with current model, then falls back to other models."""
        models_to_try = [config.model] + [m for m in config.fallback_models if m != config.model]

        last_error = None
        # Allow sufficient time for LLM generation
        call_timeout = 8.0 if is_inline else 18.0

        for model in models_to_try:
            try:
                logger.info("Requesting model '%s' (inline=%s, timeout=%.1fs)...", model, is_inline, call_timeout)
                answer = await self._call_llm(model, messages, max_tokens=max_tokens, timeout=call_timeout)
                return answer
            except Exception as e:
                logger.warning("Model '%s' failed: %s. Trying next...", model, e)
                last_error = e

        logger.error("All models failed. Last error: %s", last_error)
        return EMERGENCY_FALLBACK

    async def generate_inline_response(self, query: str) -> str:
        """Quick concise response for Telegram inline mode."""
        system_prompt = f"{DIGITAL_TWIN_PROMPT}\n\n{INLINE_PROMPT_EXTRA}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        return await self.generate_response(messages, is_inline=True, max_tokens=200)

    async def generate_chat_response(self, history: list[dict], is_girlfriend: bool = False) -> str:
        """Response for normal chat messages with conversation context."""
        system_prompt = GIRLFRIEND_PROMPT if is_girlfriend else DIGITAL_TWIN_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + history
        return await self.generate_response(messages, is_inline=False, max_tokens=400)

    async def generate_business_response(self, history: list[dict], is_girlfriend: bool = False) -> str:
        """Response for Telegram Business personal chat autopilot."""
        system_prompt = GIRLFRIEND_PROMPT if is_girlfriend else DIGITAL_TWIN_PROMPT
        messages = [{"role": "system", "content": system_prompt}] + history
        return await self.generate_response(messages, is_inline=False, max_tokens=300)

    async def generate_vision_response(self, image_base64: str, caption: str = "", is_girlfriend: bool = False) -> str:
        """Vision analysis of an image."""
        system_prompt = GIRLFRIEND_PROMPT if is_girlfriend else DIGITAL_TWIN_PROMPT
        default_caption = "Ой, ты прислала фото... 😳 Какая красота!" if is_girlfriend else "Зацени фотокарточку, чё думаешь?"
        user_text = caption.strip() if caption else default_caption
        user_content = [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
            },
        ]
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        models_to_try = [config.model] + [m for m in config.fallback_models if m != config.model]
        last_error = None
        for model in models_to_try:
            try:
                logger.info("Vision request with model '%s' (girlfriend=%s)...", model, is_girlfriend)
                answer = await self._call_llm(model, messages, max_tokens=400, timeout=12.0)
                return answer
            except Exception as e:
                logger.warning("Vision model '%s' failed: %s", model, e)
                last_error = e

        logger.error("All vision models failed. Last error: %s", last_error)
        if is_girlfriend:
            return "Ой, прости пожалуйста... 🥺 У меня фотка почему-то не открылась... Скинешь ещё раз, если не трудно? 👉👈"
        return "Слушай, фотка чёт не прогрузилась нормально. Перекинь ещё раз или черкани текстом!"

    async def fetch_available_models(self) -> list[str]:
        """Fetches list of registered model IDs from provider."""
        try:
            models_res = await self.client.models.list()
            return [m.id for m in models_res.data]
        except Exception as e:
            logger.error("Failed to fetch models list: %s", e)
            return [config.model] + config.fallback_models

    async def test_single_model(self, model_name: str) -> dict:
        """Tests latency and status of a single model."""
        start_t = time.perf_counter()
        try:
            await self.client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=10,
                timeout=6.0,
            )
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            return {
                "model": model_name,
                "status": "online",
                "latency_ms": elapsed_ms,
                "error": None,
            }
        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            err_msg = str(e)
            if len(err_msg) > 60:
                err_msg = err_msg[:57] + "..."
            return {
                "model": model_name,
                "status": "offline",
                "latency_ms": elapsed_ms,
                "error": err_msg,
            }

    async def craft_image_prompt(self, user_request: str) -> str:
        """Translates user request or keywords into a high-quality descriptive English FLUX prompt."""
        system_prompt = (
            "You are an expert prompt engineer for FLUX and SDXL image generators. "
            "Convert the user request into a concise, detailed, aesthetic English prompt (1-2 sentences). "
            "Focus on visual details, atmosphere, lighting, 8k resolution. "
            "Return ONLY the raw prompt in English, with NO explanations, quotes, or markdown."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_request},
        ]
        try:
            prompt = await self._call_llm(config.model, messages, max_tokens=150, timeout=8.0)
            return prompt.strip().strip('"').strip("'")
        except Exception as e:
            logger.warning("Failed to LLM-craft image prompt: %s, using fallback", e)
            return f"high quality artistic photo of {user_request}, 8k, photorealistic, cinematic lighting"

    async def craft_spontaneous_image(self, history: list[dict], is_girlfriend: bool) -> tuple[str, str]:
        """Generates an image prompt and caption based on conversation context."""
        recent_text = "\n".join([f"{m.get('role')}: {m.get('content')}" for m in history[-4:]])
        if is_girlfriend:
            system_prompt = (
                "Based on the conversation, suggest a cute or romantic image to draw for girlfriend to delight her. "
                "Format: PROMPT: <english prompt for FLUX image>\nCAPTION: <short timid obedient caption in Russian with emojis 🥺👉👈>\n"
                "Return exactly that format."
            )
        else:
            system_prompt = (
                "Based on the recent casual Russian chat, invent a cool, funny, or aesthetic photo that Xalid would randomly generate and send. "
                "Format: PROMPT: <english prompt for FLUX image>\nCAPTION: <short casual Russian caption like 'ща по фану намутил, зацени))' with no period at end>\n"
                "Return exactly that format."
            )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": recent_text or "General casual chat"},
        ]
        try:
            res = await self._call_llm(config.model, messages, max_tokens=180, timeout=9.0)
            lines = res.split("\n")
            p_val = ""
            c_val = ""
            for line in lines:
                if line.upper().startswith("PROMPT:"):
                    p_val = line.split(":", 1)[1].strip()
                elif line.upper().startswith("CAPTION:"):
                    c_val = line.split(":", 1)[1].strip()
            if p_val:
                return p_val, c_val
        except Exception as e:
            logger.warning("Spontaneous image generation failed: %s", e)

        if is_girlfriend:
            return (
                "a tiny adorable fluffy white kitten sitting in a tea cup surrounded by pink rose petals, soft morning light, 8k",
                "Я тут подумал о тебе.. и нарисовал вот это 🥺👉👈 Надеюсь тебе понравится.. ❤️",
            )
        else:
            return (
                "aesthetic modern sports car parked on a quiet street in Tokyo at midnight, neon reflections in rain puddles, cinematic 8k",
                "глянь какой кадр намутил щас))",
            )


ai_service = AIService()
