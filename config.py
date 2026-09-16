# -*- coding: utf-8 -*-
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    bot_token: str
    api_key: str
    base_url: str
    model: str
    fallback_models: list[str]
    admin_ids: set[int] = field(default_factory=set)
    vision_mode: str = "all"  # Options: 'all', 'admin_only', 'disabled'
    cloudflare_account_id: str = "a782db9fe21b2103266ff019c4c6f4e6"
    cloudflare_api_token: str = ""
    cloudflare_backup_token: str = ""

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def set_model(self, new_model: str):
        self.model = new_model

    def set_vision_mode(self, mode: str):
        if mode in ("all", "admin_only", "disabled"):
            self.vision_mode = mode


def load_config() -> Config:
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not bot_token:
        raise ValueError("TELEGRAM_BOT_TOKEN is not set (add it to Environment Variables in your hosting dashboard or .env)")

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set (add it to Environment Variables in your hosting dashboard or .env)")

    base_url = os.getenv("OPENAI_BASE_URL", "https://free.sysik.mom/v1").strip()
    model = os.getenv("OPENAI_MODEL", "gemini-3.8-flash").strip()
    fallback_str = os.getenv("FALLBACK_MODELS", "qwen3.8-max,kimi-k2.5").strip()
    fallback_models = [m.strip() for m in fallback_str.split(",") if m.strip()]

    admin_str = os.getenv("ADMIN_ID", "7299369267").strip()
    admin_ids = set()
    for item in admin_str.replace(" ", ",").split(","):
        if item.isdigit():
            admin_ids.add(int(item))

    cf_account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID", "a782db9fe21b2103266ff019c4c6f4e6").strip()
    cf_api_token = os.getenv("CLOUDFLARE_API_TOKEN", "").strip()
    cf_backup_token = os.getenv("CLOUDFLARE_BACKUP_TOKEN", "").strip()

    return Config(
        bot_token=bot_token,
        api_key=api_key,
        base_url=base_url,
        model=model,
        fallback_models=fallback_models,
        admin_ids=admin_ids,
        vision_mode="all",
        cloudflare_account_id=cf_account_id,
        cloudflare_api_token=cf_api_token,
        cloudflare_backup_token=cf_backup_token,
    )


config = load_config()
