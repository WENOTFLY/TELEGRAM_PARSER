# TG Studio

TG Studio — SaaS-платформа для парсинга Telegram-каналов и сборки публикационных пакетов с использованием ИИ. Пользователь авторизуется через Telegram SSO, подключает свой аккаунт по QR (MTProto), выбирает каналы и получает:

- инкрементально обновляемую ленту сообщений;
- топ-новости и темы за 24 часа и 7 дней;
- ИИ-конвейер: **Редактор → Image Brief → Генерация изображений → Publisher**.

## Архитектура

Монорепозиторий содержит два сервиса:

### Web (API + UI)
- Python 3.11, FastAPI, SQLAlchemy, Alembic
- Telegram Login (SSO) с выдачей JWT в HttpOnly-cookie
- Серверные шаблоны Jinja2 для UI
- `/metrics` для Prometheus

### Worker (фоновые задачи)
- Telethon для MTProto‑логина по QR и парсинга каналов
- Обработчик FLOOD_WAIT, ретраи, инкрементальное чтение
- Запуск ИИ‑агентов по запросу API или правилам

### Хранилища и интеграции
- PostgreSQL — основные данные
- Redis — кэши, анти‑replay, локи
- Supabase/S3 — хранение медиафайлов
- OpenAI (GPT‑класс и gpt-image-1) — генерация текста и изображений

## Локальный запуск
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
uvicorn web:app --reload
```
Worker можно запустить скриптом `python worker/__init__.py` (заглушка).

## Переменные окружения
Все переменные можно задать через `.env` для локальной разработки или в настройках Railway. Ниже перечислены требуемые значения и где их задавать.

| Переменная | Описание | Где задаётся |
| --- | --- | --- |
| `DATABASE_URL` | Строка подключения к PostgreSQL | **Автоматически**: плагин `postgres` в Railway |
| `REDIS_URL` | Строка подключения к Redis | **Автоматически**: плагин `redis` в Railway |
| `OPENAI_API_KEY` | Ключ OpenAI | Project Variables (для web и worker) |
| `SECRET_KEY` | Секрет для подписи JWT | Project Variables |
| `SESSION_KEY_1` | AES‑ключ для шифрования MTProto‑сессий | Project Variables |
| `SUPABASE_URL` | URL проекта Supabase | Project Variables |
| `SUPABASE_KEY` | Сервисный или anon ключ Supabase | Project Variables |
| `SUPABASE_BUCKET` | Bucket для медиа | Project Variables |
| `FRONTEND_ORIGINS` | Разрешённые CORS‑домены, через запятую | Project Variables |
| `SENTRY_DSN` | (опц.) DSN для Sentry | Project Variables |
| `TELEGRAM_AUTH_TOKEN` | Токен бота для Telegram Login | Service `web` |
| `TELEGRAM_BOT_USERNAME` | Username бота | Service `web` |
| `TELEGRAM_API_ID` | API ID для Telethon | Service `worker` |
| `TELEGRAM_API_HASH` | API hash для Telethon | Service `worker` |
| `PORT` | Порт web-сервиса | **Автоматически** выдаётся Railway |

## Деплой на Railway
1. Установите CLI: `npm i -g @railway/cli` и выполните `railway login`.
2. Создайте новый проект: `railway init` и подключите репозиторий.
3. Railway автоматически создаст два сервисa согласно `railway.json`: `web` и `worker`.
4. В проект добавьте плагины **PostgreSQL** и **Redis**.
5. В разделе **Variables** задайте значения из таблицы выше:
   - переменные из блока *Project Variables* добавьте на уровне проекта, чтобы они наследовались обоими сервисами;
   - переменные из блоков *Service* добавьте отдельно для сервисов `web` и `worker`.
6. При запуске каждый сервис выполняет `alembic upgrade head` до старта. Web слушает порт, выданный Railway, worker логирует heartbeat.

После деплоя вы получите публичный URL web‑сервиса и сможете работать с API и UI.

## Лицензия
Проект распространяется под лицензией MIT.
