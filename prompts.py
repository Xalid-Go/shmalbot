# -*- coding: utf-8 -*-
import base64
import hashlib
import hmac
import json
import logging
import os

logger = logging.getLogger(__name__)

# Fallback neutral prompt for public repository visibility
DEFAULT_DIGITAL_TWIN_PROMPT = (
    "Ты — личный помощник в Telegram. Отвечай коротко, по-человечески, 1-2 предложениями, "
    "без канцелярита и без точек на конце последнего предложения. Будь дружелюбным и естественным."
)

DEFAULT_INLINE_PROMPT_EXTRA = (
    "Ты выдаёшь быстрый, остроумный и меткий ответ в чате (1 короткая строка без точки в конце)."
)

DEFAULT_GIRLFRIEND_PROMPT = DEFAULT_DIGITAL_TWIN_PROMPT
DEFAULT_GIRLFRIEND_USERNAME = ""

# Encrypted payload containing private personas and triggers (protected with AES/HMAC-SHA256)
SECURE_PROMPTS_BUNDLE = "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"


def _decrypt_bundle(token_b64: str, password: str) -> dict:
    bundle = base64.b64decode(token_b64.encode("utf-8"))
    salt = bundle[:16]
    auth_tag = bundle[16:48]
    ciphertext = bundle[48:]

    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 100000, dklen=32)
    expected_tag = hmac.new(key, salt + ciphertext, hashlib.sha256).digest()
    if not hmac.compare_digest(auth_tag, expected_tag):
        raise ValueError("Invalid secret key or corrupted data")

    keystream = bytearray()
    counter = 0
    while len(keystream) < len(ciphertext):
        block = hmac.new(key, counter.to_bytes(4, "big"), hashlib.sha256).digest()
        keystream.extend(block)
        counter += 1

    plaintext = bytes(c ^ k for c, k in zip(ciphertext, keystream[:len(ciphertext)]))
    return json.loads(plaintext.decode("utf-8"))


def _load_prompts():
    secret_key = os.getenv("APP_SECRET_KEY", "").strip()
    decrypted = {}

    if secret_key:
        try:
            decrypted = _decrypt_bundle(SECURE_PROMPTS_BUNDLE, secret_key)
            logger.info("Secure persona prompts decrypted and loaded")
        except Exception as e:
            logger.warning("Could not decrypt secure prompts bundle: %s. Using default/env prompts.", e)

    # Environment variables take top precedence, followed by decrypted bundle, then defaults
    twin = os.getenv("DIGITAL_TWIN_PROMPT") or decrypted.get("DIGITAL_TWIN_PROMPT") or DEFAULT_DIGITAL_TWIN_PROMPT
    inline = os.getenv("INLINE_PROMPT_EXTRA") or decrypted.get("INLINE_PROMPT_EXTRA") or DEFAULT_INLINE_PROMPT_EXTRA
    gf_username = (
        os.getenv("GIRLFRIEND_USERNAME")
        or decrypted.get("GIRLFRIEND_USERNAME")
        or DEFAULT_GIRLFRIEND_USERNAME
    ).lower().lstrip("@")
    gf_prompt = os.getenv("GIRLFRIEND_PROMPT") or decrypted.get("GIRLFRIEND_PROMPT") or DEFAULT_GIRLFRIEND_PROMPT

    return twin, inline, gf_username, gf_prompt


DIGITAL_TWIN_PROMPT, INLINE_PROMPT_EXTRA, GIRLFRIEND_USERNAME, GIRLFRIEND_PROMPT = _load_prompts()
