# 🤖 Telegram AI Assistant Bot (Inline + Chat + Vision)

Умный и быстрый Telegram-бот на базе LLM API с поддержкой **Inline-режима** (вызов прямо в диалоге с любым собеседником через `@имя_бота <вопрос>`), распознаванием изображений и панелью управления администратора.

---

## 🚀 Быстрый старт

### 1. Активация виртуального окружения
```bash
source venv/bin/activate
```

### 2. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 3. Настройка `.env`
Создайте файл `.env` на основе примера `.env.example`:
```ini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_BASE_URL=https://free.sysik.mom/v1
OPENAI_MODEL=kimi-k2.5
FALLBACK_MODELS=qwen3.8-max,gemini-3.8-flash
ADMIN_ID=7299369267
```

### 4. Запуск бота
```bash
python3 main.py
```

---

## ⚡ Как включить Inline-режим в Telegram
Чтобы бота можно было вызывать в любом чате (как Mira или @gif):

1. Откройте диалог с [@BotFather](https://t.me/BotFather).
2. Отправьте команду `/setinline`.
3. Выберите вашего бота из списка.
4. Отправьте текст-плейсхолдер: `Задайте вопрос ассистенту...`

Готово! Теперь в любом личном чате или группе напишите:
```
@username_бота ваш вопрос
```
Появится карточка с ответом — нажмите на неё, и сообщение отправится в чат!

---

## 📁 Структура проекта
- `config.py` — конфигурация и управление правами администратора.
- `prompts.py` — системные промпты для чата, инлайна и зрения.
- `ai_service.py` — асинхронный сервис с автоматическим переключением моделей (fallback).
- `handlers/admin.py` — админ-панель (`/admin`) с переключением моделей, тестами и настройками.
- `handlers/vision.py` — распознавание и анализ фотографий.
- `handlers/inline.py` — обработка инлайн-запросов (`@bot ...`).
- `handlers/chat.py` — обработка личных сообщений с контекстом.
- `main.py` — точка входа.
