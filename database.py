# -*- coding: utf-8 -*-
from __future__ import annotations
import sqlite3
from pathlib import Path

from typing import Optional

DB_PATH = Path(__file__).parent / "bot.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes settings and messages tables."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )
        # Default: AI is ENABLED
        cursor.execute(
            """
            INSERT OR IGNORE INTO settings (key, value) VALUES ('ai_enabled', 'true')
            """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER NOT NULL,
                chat_title TEXT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT NOT NULL,
                text TEXT,
                is_photo INTEGER DEFAULT 0,
                source TEXT DEFAULT 'direct',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages (chat_id)
            """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages (created_at)
            """
        )
        conn.commit()


def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves a setting value by key."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        if row:
            return row["value"]
        return default


def set_setting(key: str, value: str):
    """Sets a setting key-value pair."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = ?",
            (key, value, value),
        )
        conn.commit()


def is_ai_enabled() -> bool:
    """Returns True if the AI interlocutor is active, False if turned off."""
    val = get_setting("ai_enabled", "true")
    return val.lower() == "true" if val else True


def set_ai_enabled(enabled: bool):
    """Sets AI interlocutor state (True=ON, False=OFF)."""
    set_setting("ai_enabled", "true" if enabled else "false")


def save_chat_message(
    chat_id: int,
    chat_title: Optional[str],
    user_id: int,
    username: Optional[str],
    full_name: Optional[str],
    role: str,
    text: str,
    is_photo: bool = False,
    source: str = "direct",
):
    """Saves a message to the database."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO messages (
                chat_id, chat_title, user_id, username, full_name, role, text, is_photo, source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat_id,
                chat_title or "",
                user_id,
                username or "",
                full_name or "",
                role,
                text or "",
                1 if is_photo else 0,
                source,
            ),
        )
        conn.commit()


def get_recent_chats(limit: int = 30) -> list[dict]:
    """Returns distinct chats with stats on recent activity."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                chat_id,
                COALESCE(MAX(chat_title), '') AS chat_title,
                COALESCE(MAX(CASE WHEN role = 'user' THEN username ELSE '' END), MAX(username), '') AS username,
                COALESCE(MAX(CASE WHEN role = 'user' THEN full_name ELSE '' END), MAX(full_name), '') AS full_name,
                COUNT(id) AS message_count,
                MAX(created_at) AS last_message_time,
                MAX(source) AS source
            FROM messages
            GROUP BY chat_id
            ORDER BY last_message_time DESC
            LIMIT ?
            """,
            (limit,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_chat_history(chat_id: int) -> list[dict]:
    """Returns chronological messages for a specific chat."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, chat_id, chat_title, user_id, username, full_name, role, text, is_photo, source, created_at
            FROM messages
            WHERE chat_id = ?
            ORDER BY id ASC
            """,
            (chat_id,),
        )
        return [dict(row) for row in cursor.fetchall()]


def get_all_chats_history() -> list[dict]:
    """Returns all messages ordered by chat_id and id ASC."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, chat_id, chat_title, user_id, username, full_name, role, text, is_photo, source, created_at
            FROM messages
            ORDER BY chat_id ASC, id ASC
            """
        )
        return [dict(row) for row in cursor.fetchall()]
