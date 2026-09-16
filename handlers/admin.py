import os
import logging
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BufferedInputFile,
    FSInputFile,
    InputProfilePhotoStatic,
)
from config import config
from ai_service import ai_service
from handlers.chat import CHAT_HISTORIES
from database import (
    is_ai_enabled,
    set_ai_enabled,
    get_setting,
    set_setting,
    get_recent_chats,
    get_chat_history,
)
from html_exporter import generate_chat_html, generate_all_chats_html

logger = logging.getLogger(__name__)
router = Router(name="admin_router")

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def get_ai_avatar_path() -> Path:
    """Returns absolute path to the active AI warning avatar based on theme setting."""
    theme = get_setting("avatar_theme", "white")
    if theme == "dark":
        p = ASSETS_DIR / "ai_avatar_dark.jpg"
        if p.exists():
            return p
    return ASSETS_DIR / "ai_avatar_on.jpg"


async def update_bot_profile_description(bot: Bot, enabled: bool):
    """Updates bot profile bio/description AND personal Telegram Business account (@xaiid77) bio & avatar."""
    target_bio = "ВКЛЮЧЕН ИИ ! ! ! (ПИШЕТ НЕ ХАЛИД)" if enabled else ""

    # 1. Update bot's own profile description
    try:
        if enabled:
            await bot.set_my_short_description(target_bio)
            await bot.set_my_description(f"{target_bio}\n\nБот общается в режиме цифрового двойника от имени Халида.")
        else:
            await bot.set_my_short_description("")
            await bot.set_my_description("")
        logger.info("Bot's own description updated (enabled=%s)", enabled)
    except Exception as e:
        logger.error("Failed to update bot profile description: %s", e)

    # 2. Update Xalid's personal Telegram account bio & avatar (@xaiid77) via Telegram Business API
    conn_id = get_setting("business_conn_id") or "QG8fe7FvUUVZAQAAW2Du6Na2_7E"
    if conn_id:
        # Update Bio
        try:
            await bot.set_business_account_bio(business_connection_id=conn_id, bio=target_bio)
            logger.info("Successfully updated @xaiid77 business account bio to: '%s'", target_bio)
        except Exception as e:
            logger.warning("Could not set business account bio on @xaiid77: %s (ensure 'Manage Bio' permission is granted)", e)

        # 3. Automatic Profile Avatar Swapper on @xaiid77
        try:
            if enabled:
                avatar_path = get_ai_avatar_path()
                if avatar_path.exists():
                    photo = InputProfilePhotoStatic(photo=FSInputFile(str(avatar_path)))
                    res = await bot.set_business_account_profile_photo(
                        business_connection_id=conn_id,
                        photo=photo
                    )
                    # Also set public profile photo
                    try:
                        await bot.set_business_account_profile_photo(
                            business_connection_id=conn_id,
                            photo=photo,
                            is_public=True
                        )
                    except Exception as pe:
                        logger.debug("Public avatar set note: %s", pe)
                    logger.info("Successfully applied AI warning avatar on @xaiid77 (result=%s, path=%s)", res, avatar_path.name)
                else:
                    logger.warning("Avatar file not found at: %s", avatar_path)
            else:
                res = await bot.remove_business_account_profile_photo(business_connection_id=conn_id)
                try:
                    await bot.remove_business_account_profile_photo(business_connection_id=conn_id, is_public=True)
                except Exception:
                    pass
                logger.info("Successfully removed AI warning avatar from @xaiid77, original photo restored (result=%s)", res)
        except Exception as e:
            logger.warning("Could not sync business account profile photo on @xaiid77: %s", e)


def get_admin_main_kb() -> InlineKeyboardMarkup:
    """Main clean admin dashboard keyboard."""
    ai_on = is_ai_enabled()
    ai_btn_text = "🤖 ИИ-собеседник: 🟢 ВКЛЮЧЁН" if ai_on else "🤖 ИИ-собеседник: 🔴 ВЫКЛЮЧЕН"

    v_mode_labels = {
        "all": "🟢 Для всех",
        "admin_only": "🔒 Только админ",
        "disabled": "🔴 Выключено",
    }
    v_label = v_mode_labels.get(config.vision_mode, config.vision_mode)

    av_theme = get_setting("avatar_theme", "white")
    theme_icon = "⚪ Светлая" if av_theme == "white" else "⚫ Тёмная"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=ai_btn_text,
                    callback_data="adm_toggle_ai",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📜 Экспорт диалогов (HTML)",
                    callback_data="adm_menu_export",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"⚙️ Модель: {config.model}",
                    callback_data="adm_menu_models",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"👁️ Реакция на фото: {v_label}",
                    callback_data="adm_menu_vision",
                )
            ],
            [
                InlineKeyboardButton(
                    text=f"🖼️ Аватарка ИИ: {theme_icon}",
                    callback_data="adm_menu_avatar",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧪 Тест скорости моделей (Пинг)",
                    callback_data="adm_test_models",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🧹 Сбросить контекст диалогов",
                    callback_data="adm_clear_memory",
                )
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


def get_avatar_menu_kb() -> InlineKeyboardMarkup:
    """Keyboard for AI warning avatar management."""
    theme = get_setting("avatar_theme", "white")
    w_mark = "✅ " if theme == "white" else ""
    d_mark = "✅ " if theme == "dark" else ""
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{w_mark}⚪ Светлый стиль (Оригинал)",
                    callback_data="adm_set_av_white",
                ),
                InlineKeyboardButton(
                    text=f"{d_mark}⚫ Тёмный кибер-стиль",
                    callback_data="adm_set_av_dark",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👁️ Отправить превью в чат",
                    callback_data="adm_av_preview",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⚡ Установить на аву сейчас",
                    callback_data="adm_av_apply_now",
                ),
                InlineKeyboardButton(
                    text="🧹 Снять с авы (вернуть свою)",
                    callback_data="adm_av_remove_now",
                ),
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
        await message.answer("⛔ Доступ ограничен. Панель управления доступна только владельцу бота.")
        return

    ai_status = "🟢 ВКЛЮЧЁН (активно отвечает)" if is_ai_enabled() else "🔴 ВЫКЛЮЧЕН (молчит)"
    text = (
        "👑 <b>Панель управления (ИИ-собеседник)</b>\n\n"
        f"🤖 <b>Статус ИИ:</b> {ai_status}\n"
        f"⚙️ <b>Активная модель:</b> <code>{config.model}</code>\n"
        f"👁️ <b>Режим фото:</b> {config.vision_mode}\n\n"
        "Нажмите на кнопку ниже, чтобы включить/выключить ИИ или изменить настройки:"
    )
    await message.answer(text, reply_markup=get_admin_main_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm_main")
async def cb_admin_main(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    ai_status = "🟢 ВКЛЮЧЁН (активно отвечает)" if is_ai_enabled() else "🔴 ВЫКЛЮЧЕН (молчит)"
    text = (
        "👑 <b>Панель управления (ИИ-собеседник)</b>\n\n"
        f"🤖 <b>Статус ИИ:</b> {ai_status}\n"
        f"⚙️ <b>Активная модель:</b> <code>{config.model}</code>\n"
        f"👁️ <b>Режим фото:</b> {config.vision_mode}\n\n"
        "Выберите нужное действие:"
    )
    await call.message.edit_text(text, reply_markup=get_admin_main_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "adm_toggle_ai")
async def cb_toggle_ai(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    current = is_ai_enabled()
    new_state = not current
    set_ai_enabled(new_state)

    # Sync bot profile description
    await update_bot_profile_description(call.bot, new_state)

    status_str = "🟢 ВКЛЮЧЁН" if new_state else "🔴 ВЫКЛЮЧЕН"
    av_info = " (Аватарка ИИ активирована)" if new_state else " (Аватарка ИИ снята)"
    await call.answer(f"ИИ-собеседник теперь {status_str}!{av_info}", show_alert=True)
    await cb_admin_main(call)


@router.message(Command("avatar"))
async def handle_avatar_command(message: Message):
    if not config.is_admin(message.from_user.id):
        return

    theme = get_setting("avatar_theme", "white")
    theme_str = "⚪ Светлый (Оригинал)" if theme == "white" else "⚫ Тёмный (Кибер)"
    ai_state = "🟢 ВКЛЮЧЁН (аватарка активна)" if is_ai_enabled() else "🔴 ВЫКЛЮЧЕН (аватарка снята)"

    text = (
        "🖼️ <b>Управление аватаркой ИИ</b>\n\n"
        f"🎨 <b>Текущий стиль:</b> {theme_str}\n"
        f"🤖 <b>Статус ИИ:</b> {ai_state}\n\n"
        "<i>Когда режим ИИ включён — эта аватарка автоматически ставится на ваш профиль @xaiid77.\n"
        "Когда режим ИИ выключен — аватарка удаляется и возвращается ваша обычная!</i>"
    )
    await message.answer(text, reply_markup=get_avatar_menu_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm_menu_avatar")
async def cb_admin_avatar_menu(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    theme = get_setting("avatar_theme", "white")
    theme_str = "⚪ Светлый (Оригинал)" if theme == "white" else "⚫ Тёмный (Кибер)"
    ai_state = "🟢 ВКЛЮЧЁН (аватарка активна)" if is_ai_enabled() else "🔴 ВЫКЛЮЧЕН (аватарка снята)"

    text = (
        "🖼️ <b>Управление аватаркой ИИ</b>\n\n"
        f"🎨 <b>Текущий стиль:</b> {theme_str}\n"
        f"🤖 <b>Статус ИИ:</b> {ai_state}\n\n"
        "<i>Когда режим ИИ включён — аватарка автоматически ставится на ваш профиль.\n"
        "Когда режим ИИ выключен — аватарка автоматически убирается!</i>\n\n"
        "Выберите нужное действие:"
    )
    await call.message.edit_text(text, reply_markup=get_avatar_menu_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data == "adm_set_av_white")
async def cb_admin_set_av_white(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    set_setting("avatar_theme", "white")
    if is_ai_enabled():
        await update_bot_profile_description(call.bot, True)

    await call.answer("Выбран светлый стиль (Оригинал)!", show_alert=True)
    await cb_admin_avatar_menu(call)


@router.callback_query(F.data == "adm_set_av_dark")
async def cb_admin_set_av_dark(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    set_setting("avatar_theme", "dark")
    if is_ai_enabled():
        await update_bot_profile_description(call.bot, True)

    await call.answer("Выбран тёмный кибер-стиль!", show_alert=True)
    await cb_admin_avatar_menu(call)


@router.callback_query(F.data == "adm_av_preview")
async def cb_admin_avatar_preview(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    avatar_path = get_ai_avatar_path()
    if not avatar_path.exists():
        await call.answer("Файл аватарки не найден!", show_alert=True)
        return

    await call.answer("Отправляю превью...")
    theme = get_setting("avatar_theme", "white")
    theme_str = "Светлый стиль (Оригинал)" if theme == "white" else "Тёмный кибер-стиль"
    caption = (
        f"🖼️ <b>Превью аватарки ИИ ({theme_str})</b>\n\n"
        "Предупреждение на фото:\n"
        "⚠️ <i>ВНИМАНИЕ: ВКЛЮЧЕН ИИ\nПИШЕТ ИИ, А НЕ ЧЕЛОВЕК\nОБЩАЕТСЯ НЕЙРОСЕТЬ (НЕ ХАЛИД)</i>\n\n"
        "Ставится на аватарку при включении ИИ, убирается при выключении!"
    )
    await call.message.answer_photo(
        photo=FSInputFile(str(avatar_path)),
        caption=caption,
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_av_apply_now")
async def cb_admin_avatar_apply_now(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    conn_id = get_setting("business_conn_id") or "QG8fe7FvUUVZAQAAW2Du6Na2_7E"
    avatar_path = get_ai_avatar_path()
    try:
        photo = InputProfilePhotoStatic(photo=FSInputFile(str(avatar_path)))
        await call.bot.set_business_account_profile_photo(business_connection_id=conn_id, photo=photo)
        try:
            await call.bot.set_business_account_profile_photo(business_connection_id=conn_id, photo=photo, is_public=True)
        except Exception:
            pass
        await call.answer("✅ Аватарка успешно установлена на профиль @xaiid77!", show_alert=True)
    except Exception as e:
        await call.answer(f"Ошибка установки: {e}", show_alert=True)


@router.callback_query(F.data == "adm_av_remove_now")
async def cb_admin_avatar_remove_now(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    conn_id = get_setting("business_conn_id") or "QG8fe7FvUUVZAQAAW2Du6Na2_7E"
    try:
        await call.bot.remove_business_account_profile_photo(business_connection_id=conn_id)
        try:
            await call.bot.remove_business_account_profile_photo(business_connection_id=conn_id, is_public=True)
        except Exception:
            pass
        await call.answer("✅ Аватарка ИИ снята! Ваша обычная аватарка возвращена.", show_alert=True)
    except Exception as e:
        await call.answer(f"Ошибка снятия: {e}", show_alert=True)


@router.callback_query(F.data == "adm_menu_vision")
async def cb_admin_vision_menu(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    text = (
        "👁️ <b>Настройка реакции на фото</b>\n\n"
        "Выберите, кому бот будет отвечать на присланные фотографии:"
    )
    await call.message.edit_text(text, reply_markup=get_vision_kb(), parse_mode="HTML")
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
        "⚙️ <b>Выбор активной модели ИИ</b>\n\n"
        f"Текущая модель: <code>{config.model}</code>\n"
        "Нажмите на нужную модель для переключения:"
    )
    await call.message.edit_text(text, reply_markup=kb, parse_mode="HTML")


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

    await call.message.edit_text("⏳ <b>Тестирую скорость моделей... Подождите пару секунд.</b>", parse_mode="HTML")

    results = await ai_service.test_all_models()
    lines = ["🧪 <b>Результаты пинга моделей:</b>\n"]
    for r in results:
        status_icon = "🟢" if r["status"] == "online" else "🔴"
        m_name = r["model"]
        is_curr = " (ТЕКУЩАЯ)" if m_name == config.model else ""
        if r["status"] == "online":
            lines.append(f"{status_icon} <code>{m_name}</code>: <b>{r['latency_ms']}ms</b>{is_curr}")
        else:
            err = r["error"] or "error"
            lines.append(f"{status_icon} <code>{m_name}</code>: {err}{is_curr}")

    lines.append("\n_Нажмите Назад для возврата в меню._")
    back_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Повторить тест", callback_data="adm_test_models")],
            [InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main")],
        ]
    )
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb, parse_mode="HTML")
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
    await call.answer("Панель закрыта.")


def get_export_kb() -> InlineKeyboardMarkup:
    """Keyboard listing chats for HTML export."""
    chats = get_recent_chats(limit=15)
    buttons = []
    for c in chats:
        c_id = c["chat_id"]
        c_name = c["full_name"] or c["chat_title"] or f"Чат {c_id}"
        u_name = f" (@{c['username']})" if c["username"] else ""
        cnt = c["message_count"]
        btn_text = f"👤 {c_name}{u_name} [{cnt}]"
        if len(btn_text) > 38:
            btn_text = btn_text[:35] + "..."
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"adm_dl_chat:{c_id}")])

    if chats:
        buttons.append([InlineKeyboardButton(text="📦 Скачать ВСЕ диалоги единым HTML", callback_data="adm_dl_all")])

    buttons.append([InlineKeyboardButton(text="🔄 Обновить", callback_data="adm_menu_export")])
    buttons.append([InlineKeyboardButton(text="⬅️ Назад в меню", callback_data="adm_main")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(Command("export", "chats"))
async def cmd_export_chats(message: Message):
    if not config.is_admin(message.from_user.id):
        await message.answer("Доступ запрещён!")
        return
    chats = get_recent_chats(limit=15)
    cnt_info = f"Найдено диалогов: {len(chats)}" if chats else "Сохранённых диалогов пока нет"
    text = (
        "📜 <b>Экспорт сохранённых диалогов в HTML</b>\n\n"
        f"{cnt_info}.\n"
        "Выберите диалог ниже, чтобы получить структурированный HTML-файл с полной историей сообщений:"
    )
    await message.answer(text, reply_markup=get_export_kb(), parse_mode="HTML")


@router.callback_query(F.data == "adm_menu_export")
async def cb_admin_menu_export(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return
    chats = get_recent_chats(limit=15)
    cnt_info = f"Найдено диалогов: {len(chats)}" if chats else "Сохранённых диалогов пока нет"
    text = (
        "📜 <b>Экспорт сохранённых диалогов в HTML</b>\n\n"
        f"{cnt_info}.\n"
        "Выберите диалог ниже, чтобы получить структурированный HTML-файл с полной историей сообщений:"
    )
    await call.message.edit_text(text, reply_markup=get_export_kb(), parse_mode="HTML")
    await call.answer()


@router.callback_query(F.data.startswith("adm_dl_chat:"))
async def cb_download_chat_html(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    chat_id = int(call.data.split(":", 1)[1])
    msgs = get_chat_history(chat_id)
    if not msgs:
        await call.answer("В этом чате нет сохранённых сообщений!", show_alert=True)
        return

    await call.answer("Генерирую HTML...")
    contact_name = msgs[0].get("full_name") or msgs[0].get("chat_title") or f"Чат {chat_id}"
    username = msgs[0].get("username")
    chat_meta = {
        "chat_id": chat_id,
        "full_name": contact_name,
        "username": username,
        "source": msgs[0].get("source", "business"),
    }

    html_str = generate_chat_html(chat_id, msgs, chat_meta)
    doc = BufferedInputFile(html_str.encode("utf-8"), filename=f"chat_{chat_id}.html")

    u_info = f" (@{username})" if username else ""
    await call.message.answer_document(
        document=doc,
        caption=f"📜 <b>Диалог: {contact_name}{u_info}</b>\nВсего сообщений: {len(msgs)}",
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm_dl_all")
async def cb_download_all_chats_html(call: CallbackQuery):
    if not config.is_admin(call.from_user.id):
        await call.answer("Доступ запрещён!", show_alert=True)
        return

    chats = get_recent_chats(limit=100)
    if not chats:
        await call.answer("Нет сохранённых диалогов!", show_alert=True)
        return

    await call.answer("Формирую единый архив HTML...")
    chats_with_msgs = []
    total_msgs = 0
    for c in chats:
        c_msgs = get_chat_history(c["chat_id"])
        if c_msgs:
            chats_with_msgs.append((c, c_msgs))
            total_msgs += len(c_msgs)

    if not chats_with_msgs:
        await call.answer("Нет сообщений для экспорта!", show_alert=True)
        return

    html_str = generate_all_chats_html(chats_with_msgs)
    doc = BufferedInputFile(html_str.encode("utf-8"), filename="all_chats_archive.html")

    await call.message.answer_document(
        document=doc,
        caption=f"📦 <b>Полный архив всех диалогов</b>\nЧатов: {len(chats_with_msgs)} | Сообщений: {total_msgs}",
        parse_mode="HTML",
    )
