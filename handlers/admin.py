# -*- coding: utf-8 -*-
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from config import config
from ai_service import ai_service
from handlers.chat import CHAT_HISTORIES

logger = logging.getLogger(__name__)
router = Router(name="admin_router")


def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Main admin dashboard keyboard."""
    v_mode_labels = {
        "all": "🟢 Для всех",
        "admin_only": "🔒 Только админ",
        "disabled": "🔴 Выключено",
    }
    v_label = v_mode_labels.get(config.vision_mode, config.vision_mode)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🤖 Модель: {config.model}",
                    callback_data="adm_menu_models",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👁️ Зрение (фото): {v_label}",
                    callback_data="adm_menu_vision",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧪 Тест всех моделей (Пинг)",
                    callback_data="adm_test_models",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Статистика и инфо",
                    callback_data="adm_stats",
                ),
                InlineKeyboardButton(
                    text="🧹 Сброс памяти чатов",
                    callback_data="adm_clear_memory",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="❌ Закрыть панель",
                    callback_data="adm_close",
                )
            ],
        ]
    )
    return kb


def get_vision_kb() -> InlineKeyboardMarkup:
    """Keyboard to select vision mode."""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=("✅ " if config.vision_mode == "all" else "") + "🟢 Включено для ВСЕХ",
                    callback_data="adm_set_vis_all",
                )
            ],
            [
                InlineKeyboardButton(
                    text=("✅ " if config.vision_mode == "admin_only" else "") + "🔒 ТОЛЬКО ДЛЯ АДМИНА",
                    callback_data="adm_set_vis_admin",
                )
            ],
            [
                InlineKeyboardButton(
                    text=("✅ " if config.vision_mode == "disabled" else "") + "🔴 ПОЛНОСТЬЮ ОТКЛЮЧЕНО",
                    callback_data="adm_set_vis_disabled",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад в меню",
                    callback_data="adm_main",
                )
            ],
        ]
    )
    return kb


async def get_models_kb() -> InlineKeyboardMarkup:
    """Keyboard to pick active model."""
    models = await ai_service.fetch_available_models()
    buttons = []
    for m in models:
        prefix = "✅ " if m == config.model else ""
        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"{prefix}{m}",
                    callback_data=f"adm_pick_model:{m}",
                )
            ]
        )
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


# --- Handlers ---


@router.message(Command("admin"))
async def handle_admin_command(message: Message):
    user_id = message.from_user.id
    if not config.is_admin(user_id):
        await message.answer("⛔ Доступ ограничен. Панель управления доступна только администратору.")
        return

    text = (
        "👑 **Панель управления AI-ботом**\n\n"
        f"👤 Админ ID: `{user_id}`\n"
        f"🤖 Активная модель: `{config.model}`\n"
        f"👁️ Режим фото: `{config.vision_mode}`\n"
        f"🎛️ Выберите действие в меню ниже:"
    )
    await message.answer(text, reply_markup=get_admin_main_kb(), parse_mode="Markdown")


@router.callback_query(F.data == "adm_main")
async def cb_admin_main(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    text = (
        "👑 **Панель управления AI-ботом**\n\n"
        f"🤖 Активная модель: `{config.model}`\n"
        f"👁️ Режим фото: `{config.vision_mode}`\n"
        f"🎛️ Выберите действие в меню:"
    )
    await call.message.edit_text(text, reply_markup=get_admin_main_kb(), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "adm_menu_vision")
async def cb_admin_vision_menu(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    text = (
        "👁️ **Настройка распознавания фото и картинок (Vision)**\n\n"
        "Выберите, кто может отправлять фото боту для анализа:"
    )
    await call.message.edit_text(text, reply_markup=get_vision_kb(), parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data.startswith("adm_set_vis_"))
async def cb_admin_set_vision(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    mode_map = {
        "adm_set_vis_all": "all",
        "adm_set_vis_admin": "admin_only",
        "adm_set_vis_disabled": "disabled",
    }
    mode = mode_map.get(call.data, "all")
    config.set_vision_mode(mode)

    await call.answer(f"Режим фото изменён: {mode}", show_alert=True)
    await cb_admin_main(call)


@router.callback_query(F.data == "adm_menu_models")
async def cb_admin_models_menu(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    await call.answer("Загружаю список моделей...")
    kb = await get_models_kb()
    text = (
        "🤖 **Выбор активной модели ИИ**\n\n"
        f"Текущая модель: `{config.model}`\n"
        "Нажмите на нужную модель, чтобы переключить бота:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")


@router.callback_query(F.data.startswith("adm_pick_model:"))
async def cb_admin_pick_model(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    new_model = call.data.split(":", 1)[1]
    config.set_model(new_model)

    await call.answer(f"Модель переключена на: {new_model}", show_alert=True)
    await cb_admin_main(call)


@router.callback_query(F.data == "adm_test_models")
async def cb_admin_test_models(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    await call.message.edit_text("⏳ **Тестирую модели через API... Подождите несколько секунд.**", parse_mode="Markdown")

    results = await ai_service.test_all_models()
    lines = ["🧪 **Результаты тестирования моделей:**\n"]
    for r in results:
        status_icon = "🟢" if r["status"] == "online" else "🔴"
        m_name = r["model"]
        is_curr = " (ТЕКУЩАЯ)" if m_name == config.model else ""
        if r["status"] == "online":
            lines.append(f"{status_icon} `{m_name}`: **{r['latency_ms']}ms**{is_curr}")
        else:
            err = r["error"] or "error"
            lines.append(f"{status_icon} `{m_name}`: {err}{is_curr}")

    lines.append("\n_Обновите меню для возврата._")
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить тест", callback_data="adm_test_models")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main")],
        ]
    )
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "adm_stats")
async def cb_admin_stats(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    active_chats = len(CHAT_HISTORIES)
    total_messages = sum(len(h) for h in CHAT_HISTORIES.values())

    text = (
        "📊 **Статистика и состояние бота**\n\n"
        f"🤖 **Текущая модель:** `{config.model}`\n"
        f"🔄 **Фолбек-модели:** `{', '.join(config.fallback_models)}`\n"
        f"👁️ **Режим фото:** `{config.vision_mode}`\n"
        f"💬 **Активных чатов в памяти:** {active_chats}\n"
        f"✉️ **Всего реплик в буфере памяти:** {total_messages}\n"
        f"🌐 **Базовый URL API:** `{config.base_url}`\n"
    )
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main")]]
    )
    await call.message.edit_text(text, reply_markup=back_kb, parse_mode="Markdown")
    await call.answer()


@router.callback_query(F.data == "adm_clear_memory")
async def cb_admin_clear_memory(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    CHAT_HISTORIES.clear()
    await call.answer("Память всех диалогов очищена!", show_alert=True)
    await cb_admin_main(call)


@router.callback_query(F.data == "adm_close")
async def cb_admin_close(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    await call.message.delete()
    await call.answer("Админка закрыта.")
