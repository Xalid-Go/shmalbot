# -*- coding: utf-8 -*-
import asyncio
import logging
import re
import time
from openai import AsyncOpenAI
from config import config
from prompts import SYSTEM_PROMPT, INLINE_PROMPT_EXTRA

logger = logging.getLogger(__name__)

EMERGENCY_FALLBACK = "Извините, сервис временно перегружен. Пожалуйста, повторите запрос через несколько секунд."


def clean_model_output(text: str) -> str:
    """Removes reasoning tags (<think>...</think>) and raw stop artifacts."""
    if not text:
        return ""
    # Strip <think>...</think> tags and internal reasoning blocks
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    # Strip trailing raw model stop tokens
    text = re.sub(r"(stop|<\|im_end\|>|</s>|<\|endoftext\|>)\s*$", "", text, flags=re.IGNORECASE)
    return text.strip()


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
            temperature=0.7,
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
        system_prompt = f"{SYSTEM_PROMPT}\n\n{INLINE_PROMPT_EXTRA}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": query},
        ]
        return await self.generate_response(messages, is_inline=True, max_tokens=200)

    async def generate_chat_response(self, history: list[dict]) -> str:
        """Response for normal chat messages with conversation context."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + history
        return await self.generate_response(messages, is_inline=False, max_tokens=500)

    async def generate_vision_response(self, image_base64: str, caption: str = "") -> str:
        """Vision analysis of an image."""
        user_text = caption.strip() if caption else "Опиши подробно, что изображено на этом фото, и ответь на ключевые детали."
        user_content = [
            {"type": "text", "text": user_text},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"},
            },
        ]
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ]

        models_to_try = [config.model] + [m for m in config.fallback_models if m != config.model]
        last_error = None
        for model in models_to_try:
            try:
                logger.info("Vision request with model '%s'...", model)
                answer = await self._call_llm(model, messages, max_tokens=400, timeout=12.0)
                return answer
            except Exception as e:
                logger.warning("Vision model '%s' failed: %s", model, e)
                last_error = e

        logger.error("All vision models failed. Last error: %s", last_error)
        return "Не удалось распознать изображение через текущую модель. Попробуйте сменить модель в /admin или отправить другое фото."

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

    async def test_all_models(self) -> list[dict]:
        """Tests available models."""
        models = await self.fetch_available_models()
        tasks = [self.test_single_model(m) for m in models[:10]]
        return await asyncio.gather(*tasks)


ai_service = AIService()
