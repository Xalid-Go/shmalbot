# -*- coding: utf-8 -*-
import html
import logging
import random
import re
from datetime import datetime
from typing import Optional, Tuple
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import config
from prompts import GIRLFRIEND_USERNAME

logger = logging.getLogger(__name__)

# Heuristic regex patterns for insults, profanity, threats, family attacks, slurs
DISHONOR_PATTERNS = [
    # Direct insults and slurs
    r"\b(чмо|лох[а-я]*|клоун[а-я]*|петух[а-я]*|черт[а-я]*|мраз[а-я]*|твар[а-я]*|ублюд[а-я]*|выбляд[а-я]*|педик[а-я]*|пидор[а-я]*|даун[а-я]*|дебил[а-я]*|шавк[а-я]*|гной[а-я]*|гнид[а-я]*)\b",
    # Heavy profanity
    r"\b(нахуй|похуй|заебал[а-я]*|ебан[а-я]*|ебл[а-я]*|пизд[а-я]*|хуй[а-я]*|хуе[а-я]*|бля[а-я]*|муд[а-я]+|гандон[а-я]*|гондон[а-я]*|шлюх[а-я]*|шалав[а-я]*|сучк[а-я]*)\b",
    # Attacks on family and parents
    r"(мамк|матер|мамаш|мать\s+(твою|ебал|шатал)|родителе[йм]|семь[ею])",
    # Violent threats
    r"(тебе\s+пиздец|пиздец\s+тебе|зуб[а-я]*\b.*?\bвыбь|выбь[а-я]*\b.*?\bзуб|ног[а-я]*\b.*?\bперелом|найду\s+тебя|убью|сдохни|закопаю|жди\s+гостей|въебу|ушатаю)",
    # Rude silencing and vulgar commands
    r"(закрой\s+рот|завали\s+ебало|рот\s+закрой|рот\s+офни|соси|отсоси|пошел\s+ты|иди\s+ты|пошел\s+вон|свали\s+отсюда)",
    # Ethnic/national offensive slurs
    r"\b(чурк[а-я]*|хач[а-я]*|чеч[её]н[а-я]*)\b",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in DISHONOR_PATTERNS]

# Confident, dignified masculine responses (putting offender in their place)
DIGNITY_RESPONSES = [
    "ты за базаром следи вообще",
    "ты берега попутал? нормально общайся",
    "ты че несешь? за языком своим следи",
    "ты с кем так разговариваешь вообще? фильтруй базар",
    "слышь, обороты сбавь, пока нормально говорю",
    "ты слова подбирай, когда мне пишешь",
    "смелый больно по переписке? за речью следи",
    "ты берега не путай давай, в себя приди",
]


class HonorService:
    def is_exempt(self, user_id: int, username: Optional[str]) -> bool:
        """
        Check if user is exempt from honor checks:
        1. Owner/Admin himself
        2. Beloved girlfriend (@MyloveAdrianaLima_Player) - she can say anything!
        """
        if config.is_admin(user_id):
            return True

        if username and GIRLFRIEND_USERNAME:
            clean_username = username.lower().lstrip("@")
            if clean_username == GIRLFRIEND_USERNAME:
                return True

        return False

    def quick_check(self, text: str) -> Tuple[bool, str]:
        """Fast regex check for explicit offensive language and insults."""
        if not text:
            return False, ""

        for pattern in COMPILED_PATTERNS:
            match = pattern.search(text)
            if match:
                matched_word = match.group(0)
                return True, f"Оскорбление / нецензурная лексика: '{matched_word}'"

        return False, ""

    async def check_dishonor(self, text: str, ai_service_instance=None) -> Tuple[bool, str]:
        """
        Comprehensive check:
        1. Instant regex heuristic
        2. LLM semantic check for toxic provocations if suspicious
        """
        is_bad, reason = self.quick_check(text)
        if is_bad:
            return True, reason

        # If message contains suspicious aggressive punctuation or question combinations
        lowered = text.lower().strip()
        suspicious_cues = ["ты кто", "ты че", "слышь", "рот", "пошел", "заткнись", "эй", "слышишь", "лох", "дурак"]
        has_cue = any(cue in lowered for cue in suspicious_cues) or ("?" in text and "!" in text)

        if has_cue and ai_service_instance:
            try:
                system_prompt = (
                    "You are a strict dignity and honor security classifier. "
                    "Analyze the message. Is it offensive, insulting, threatening, rude, or toxic towards the recipient? "
                    "If yes, reply with 'DISHONOR: <short reason in Russian>'. "
                    "If normal or casual friendly conversation, reply with 'CLEAN'."
                )
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": text},
                ]
                res = await ai_service_instance.generate_response(messages, is_inline=True, max_tokens=50)
                if res and "DISHONOR:" in res.upper():
                    reason = res.split(":", 1)[1].strip() if ":" in res else "Неуважительный тон / токсичность"
                    return True, reason
            except Exception as e:
                logger.debug("LLM honor check skipped: %s", e)

        return False, ""

    def get_response(self) -> str:
        """Returns a calm, firm, dignified response from Xalid."""
        return random.choice(DIGNITY_RESPONSES)

    async def alert_owner(
        self,
        bot: Bot,
        chat_id: int,
        chat_title: str,
        user,
        user_text: str,
        bot_reply: str,
        reason: str,
    ):
        """Sends an immediate high-priority alert to Xalid's personal bot DM."""
        username_str = f"@{user.username}" if user.username else "нет юзернейма"
        user_mention = f"<a href='tg://user?id={user.id}'>{html.escape(user.full_name or 'Собеседник')}</a>"
        chat_name = html.escape(chat_title or f"Личный диалог ({chat_id})")
        now_str = datetime.now().strftime("%d.%m.%Y %H:%M:%S")

        alert_text = (
            "🚨 <b>[ЗАЩИТА ЧЕСТИ] Зафиксировано недостойное поведение!</b>\n\n"
            f"👤 <b>Кто написал:</b> {user_mention} ({username_str})\n"
            f"🆔 <b>ID собеседника:</b> <code>{user.id}</code>\n"
            f"💬 <b>Чат:</b> {chat_name} (<code>{chat_id}</code>)\n"
            f"⏰ <b>Время:</b> {now_str}\n"
            f"⚠️ <b>Детекция:</b> <i>{html.escape(reason)}</i>\n\n"
            f"📩 <b>Что написал тебе:</b>\n"
            f"<blockquote>{html.escape(user_text)}</blockquote>\n\n"
            f"🛡 <b>Бот ответил от твоего лица:</b>\n"
            f"<blockquote>{html.escape(bot_reply)}</blockquote>"
        )

        reply_markup = None
        if user.username:
            reply_markup = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=f"Перейти к @{user.username}",
                            url=f"https://t.me/{user.username}",
                        )
                    ]
                ]
            )

        for admin_id in config.admin_ids:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=alert_text,
                    parse_mode="HTML",
                    reply_markup=reply_markup,
                )
                logger.info("Honor defense alert successfully delivered to admin %s", admin_id)
            except Exception as e:
                logger.error("Failed to send honor alert to admin %s: %s", admin_id, e)


honor_service = HonorService()
