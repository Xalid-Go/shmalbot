# -*- coding: utf-8 -*-
import html
from datetime import datetime
from typing import Optional

BASE_CSS = """
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background-color: #0f141c;
    color: #e4ecf5;
    line-height: 1.45;
    padding: 20px;
}
.container {
    max-width: 800px;
    margin: 0 auto;
}
.header {
    background: #17212b;
    border-radius: 14px;
    padding: 20px 24px;
    margin-bottom: 24px;
    display: flex;
    align-items: center;
    gap: 16px;
    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3);
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.avatar {
    width: 54px;
    height: 54px;
    border-radius: 50%;
    background: linear-gradient(135deg, #4da9ff, #0078d4);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 22px;
    font-weight: 700;
    color: #ffffff;
    flex-shrink: 0;
}
.header-info h1 {
    font-size: 20px;
    font-weight: 600;
    color: #ffffff;
    margin-bottom: 4px;
}
.header-info .meta {
    font-size: 13px;
    color: #798b9e;
}
.stats-badge {
    margin-left: auto;
    background: rgba(77, 169, 255, 0.12);
    color: #5bb2ff;
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
    border: 1px solid rgba(77, 169, 255, 0.25);
}
.chat-window {
    display: flex;
    flex-direction: column;
    gap: 10px;
}
.message-row {
    display: flex;
    width: 100%;
}
.message-row.user {
    justify-content: flex-start;
}
.message-row.assistant {
    justify-content: flex-end;
}
.bubble {
    max-width: 78%;
    padding: 10px 14px;
    border-radius: 14px;
    position: relative;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    font-size: 14.5px;
    word-break: break-word;
}
.message-row.user .bubble {
    background: #182533;
    border-bottom-left-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.04);
}
.message-row.assistant .bubble {
    background: #2b5278;
    color: #ffffff;
    border-bottom-right-radius: 4px;
}
.sender-name {
    font-size: 12px;
    font-weight: 600;
    margin-bottom: 4px;
}
.message-row.user .sender-name {
    color: #5bb2ff;
}
.message-row.assistant .sender-name {
    color: #7ee0b1;
}
.message-text {
    white-space: pre-wrap;
    line-height: 1.45;
}
.message-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 5px;
    font-size: 11px;
    opacity: 0.65;
}
.photo-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: rgba(0, 0, 0, 0.25);
    padding: 3px 8px;
    border-radius: 6px;
    font-size: 12px;
    margin-bottom: 6px;
}
.section-divider {
    text-align: center;
    margin: 30px 0 16px 0;
    position: relative;
}
.section-divider span {
    background: #17212b;
    padding: 6px 16px;
    border-radius: 12px;
    font-size: 13px;
    color: #798b9e;
    border: 1px solid rgba(255, 255, 255, 0.05);
}
.footer-tag {
    text-align: center;
    margin-top: 30px;
    font-size: 12px;
    color: #556677;
}
"""


def get_initials(name: str) -> str:
    parts = name.strip().split()
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][:1] + parts[1][:1]).upper()


def format_message_bubble(msg: dict) -> str:
    role = msg.get("role", "user")
    is_user = (role == "user")
    row_class = "user" if is_user else "assistant"
    
    sender_name = html.escape(msg.get("full_name") or ("Собеседник" if is_user else "Халид (ИИ)"))
    text = html.escape(msg.get("text") or "")
    is_photo = bool(msg.get("is_photo", 0))
    
    # Timestamp formatting
    created_at = msg.get("created_at", "")
    time_str = created_at
    if created_at:
        try:
            # Handle SQLite default format YYYY-MM-DD HH:MM:SS
            dt = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
            time_str = dt.strftime("%d.%m %H:%M")
        except Exception:
            time_str = str(created_at)[-8:]

    photo_html = ""
    if is_photo:
        photo_html = "<div class=\"photo-badge\">📷 <i>Фотография</i></div>"

    return f"""
    <div class="message-row {row_class}">
        <div class="bubble">
            <div class="sender-name">{sender_name}</div>
            {photo_html}
            <div class="message-text">{text}</div>
            <div class="message-footer">
                <span>{html.escape(time_str)}</span>
            </div>
        </div>
    </div>
    """


def generate_chat_html(chat_id: int, messages: list[dict], chat_meta: Optional[dict] = None) -> str:
    chat_meta = chat_meta or {}
    contact_name = chat_meta.get("full_name") or chat_meta.get("chat_title") or f"Чат {chat_id}"
    username = chat_meta.get("username", "")
    source = chat_meta.get("source", "business")
    source_label = "Telegram Business" if source == "business" else "Личные сообщения"

    initials = get_initials(contact_name)
    escaped_contact = html.escape(contact_name)
    username_line = f"@{html.escape(username)} • " if username else ""
    
    bubbles_html = "\n".join(format_message_bubble(m) for m in messages)
    total_count = len(messages)
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Диалог: {escaped_contact}</title>
    <style>{BASE_CSS}</style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="avatar">{html.escape(initials)}</div>
            <div class="header-info">
                <h1>{escaped_contact}</h1>
                <div class="meta">{username_line}{source_label} • Экспорт: {now_str}</div>
            </div>
            <div class="stats-badge">{total_count} сообщений</div>
        </header>
        
        <main class="chat-window">
            {bubbles_html}
        </main>

        <div class="footer-tag">
            Сгенерировано ботом Халида • @bipbup992_robot
        </div>
    </div>
</body>
</html>"""


def generate_all_chats_html(chats_with_messages: list[tuple[dict, list[dict]]]) -> str:
    total_chats = len(chats_with_messages)
    total_msgs = sum(len(msgs) for _, msgs in chats_with_messages)
    now_str = datetime.now().strftime("%d.%m.%Y %H:%M")

    sections_html = []
    for chat_meta, msgs in chats_with_messages:
        chat_id = chat_meta.get("chat_id", "")
        contact_name = chat_meta.get("full_name") or chat_meta.get("chat_title") or f"Чат {chat_id}"
        username = chat_meta.get("username", "")
        u_str = f" (@{username})" if username else ""
        
        bubbles = "\n".join(format_message_bubble(m) for m in msgs)
        
        sections_html.append(f"""
        <div class="section-divider">
            <span>👤 <b>{html.escape(contact_name)}</b>{html.escape(u_str)} • {len(msgs)} сообщ.</span>
        </div>
        <div class="chat-window">
            {bubbles}
        </div>
        """)

    all_sections = "\n".join(sections_html)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Все диалоги ({total_chats} чатов)</title>
    <style>{BASE_CSS}</style>
</head>
<body>
    <div class="container">
        <header class="header">
            <div class="avatar">📚</div>
            <div class="header-info">
                <h1>Полный архив переписок</h1>
                <div class="meta">{total_chats} диалогов • Экспорт: {now_str}</div>
            </div>
            <div class="stats-badge">Всего {total_msgs} сообщений</div>
        </header>
        
        {all_sections}

        <div class="footer-tag">
            Сгенерировано ботом Халида • @bipbup992_robot
        </div>
    </div>
</body>
</html>"""
