TG Studio — SaaS для парсинга Telegram-каналов и сборки публикационных пакетов с ИИ

Цель

Сервис, куда пользователь заходит через Telegram SSO, подключает свой Telegram-аккаунт по QR (MTProto), выбирает каналы для слежения, получает инкрементально разобранную ленту, топ-новости/темы, затем запускает ИИ-конвейер:
«Редактор (эксклюзивный текст) → Image Brief (ТЗ) → Генерация изображений → Publisher (пакеты для соцсетей)».

Архитектура (монорепо)

Сервис web (API + UI):

Backend: Python 3.11, FastAPI, SQLAlchemy, Alembic.

Auth: Telegram Login (SSO) с проверкой подписи, JWT в HttpOnly-cookie.

Рендер UI: серверные шаблоны (Jinja2) или SPA на React — на усмотрение генератора, но UI-маршруты должны быть.

Сервис worker (фоновые задачи):

Telethon (MTProto) для логина по QR и парсинга.

Асинхронный цикл опроса подписок пользователя, обработка FLOOD_WAIT, ретраи, инкрементальное чтение.

Запуск ИИ-агентов по запросу API или по правилам (напр., «тема перешла порог»).

Хранилища и интеграции:

PostgreSQL (основные данные).

Redis (анти-replay для SSO, кэши/локи).

Supabase/S3 (объектное хранилище медиа, публичные или подписанные URL).

OpenAI (модели для текста и изображений; текст — GPT-класс, изображения — gpt-image-1).

Страницы (UI)

Login: кнопка «Войти через Telegram» (SSO).

Онбординг: если нет MTProto — экран «Подключить по QR».

Аккаунты: статус подключенных MTProto-сессий, кнопка «Сканировать QR», удаление сессии.

Подписки: добавление/удаление каналов (@username/t.me/...), статус доступности (public/private).

Лента: сообщения из собственных подписок (фильтры: дата/канал/тип/язык).

Топ/Темы: топ-новости (24h/7d), группы сообщений (topics), запуск «Сделать эксклюзив».

Пакеты: предпросмотр публикационных пакетов (тексты/хэштеги/время/картинки), экспорт JSON/CSV.

Настройки: язык/тон, часовой пояс, лимиты/план.

Использование: токены/стоимость по ИИ-вызовам, квоты (free/pro/enterprise).

Основные флоу

SSO: Telegram Login → верификация → upsert пользователя → JWT (HttpOnly, Secure, SameSite=Lax) → редирект в кабинет.

Подключение MTProto: генерация QR, поллинг статуса, при AUTHORIZED — шифровать и сохранять StringSession, помечать аккаунт активным.

Подписки: пользователь добавляет каналы; приватные — только если сессия реально видит канал.

Парсинг: по каждому tg_account — список его подписок → инкрементальное чтение c last_msg_id → нормализация сообщения → загрузка медиа в Storage → сохранение ссылок.

Кластеризация/ранжирование: объединение схожих сообщений в topics; метрики popularity + trend → итоговый score (окна 24h/7d).

ИИ-конвейер:

Редактор: из topic/наборов сообщений → эксклюзивный текст (headline, dek, 3 длины тела, key points, source_links обязательно).

Image Brief: ТЗ на 1..N изображений (title, prompt, negative, size/aspect, caption, style_tags).

Генерация изображений: gpt-image-1, модерация, загрузка в Storage, отдача URL.

Publisher: на платформы (TG/VK/X/IG…): post_time (по TZ с эвристиками), версии текста (short/medium/long), hashtags, CTA, привязка изображения.

Экспорт: выдача пакетов JSON/CSV, предпросмотр в UI.

Таблицы данных (минимум)

users (id, tg_id uniq, username, first/last, photo_url, role, plan, created_at).

tg_accounts (id, user_id, session_cipher, phone, is_active, kver, created_at).

channels (id, username uniq, title, visibility: public|private, owner_account_id?, is_active, last_parsed_at).

subscriptions (user_id, channel_id, added_at).

account_channel_state (account_id, channel_id, last_msg_id).

messages (id, channel_id, msg_id, date, text, author, views, reactions, forwards, comments, lang, type, hashtags[], links[], media_present).

media_assets (id, message_id, kind, url, size, format, hash).

topics (id, title, created_at), topic_messages (topic_id, message_id).

ranking (entity_kind, entity_id, window, score, indexed).

editor_results (id, user_id, topic_id?, message_ids[], language, headline, dek, body_variants json, key_points json, source_links json, created_at).

image_briefs (id, editor_result_id, title, prompt, negative, size, variants, caption, style_tags json).

content_packages (id, user_id, editor_result_id, created_at).

content_package_items (id, package_id, platform, post_time, post_text json, hashtags json, cta, image_url).

ai_usage (id, user_id, ts, model, input_tokens, output_tokens, cost_usd, purpose).

API (ключевые контракты, без кода)

Auth/SSO: /auth/telegram/callback (cookie + 200), /auth/logout.

MTProto/QR: POST /v1/auth/qr → {login_id, qr_png_b64}, GET /v1/auth/qr/{login_id} → PENDING|AUTHORIZED|FAILED|EXPIRED, GET /v1/accounts, DELETE /v1/accounts/{id}.

Подписки: POST /v1/channels/subscribe, DELETE /v1/channels/unsubscribe, GET /v1/channels/my.

Лента/Топ: GET /v1/feed?filters..., GET /v1/top?window=24h|7d&by=message|topic.

ИИ-конвейер:
POST /v1/transform (Редактор) → результат с source_links;
POST /v1/image-brief;
POST /v1/images;
POST /v1/package, GET /v1/packages.

Usage/метрики: GET /v1/usage?window=30d; /metrics (Prometheus).

Поведение ИИ-агентов (нужные правила)

Редактор: анти-копипаст, ссылки на источники обязательны; спорные факты помечать «needs_verification»; три длины текста; чёткий JSON-выход.

Image Brief: конкретная сцена, negative для удаления артефактов (текст/водяные знаки/логотипы), корректный размер/соотношение сторон.

Генерация изображений: модерация контента; кэшировать по хэшу брифа; возврат массива URL.

Publisher: тексты под лимиты площадок; 8–20 релевантных хэштегов; слоты времени по TZ (вечер будней/утро выходных как базовые эвристики); выдача JSON.

Безопасность и приватность

Cookie: HttpOnly + Secure + SameSite=Lax; CORS — только доверенные домены.

StringSession хранить шифрованно (AES-GCM), версия ключа (ротация).

Доступ к приватным каналам — только если видимы из сессии пользователя.

Изоляция арендаторов (multi-tenant): пользователь видит только свои данные.

Нефункциональные требования

Надёжность: FLOOD_WAIT → бэкофф и ретраи, воркер не падает.

Производительность: инкрементальный парсинг, индексы БД, кэш топов.

Наблюдаемость: структурные логи, /metrics по web/worker, алерты на массовые ошибки.

Квоты/планы: free/pro/enterprise — лимиты на каналы/генерации/изображения/медиа; 429 при превышении; учёт в ai_usage.

Переменные окружения (минимальный набор)

Общие (web & worker): DATABASE_URL(supabase), REDIS_URL(Redis), OPENAI_API_KEY, SECRET_KEY, SESSION_KEY_1, SUPABASE_URL, SUPABASE_KEY, SUPABASE_BUCKET, FRONTEND_ORIGINS, SENTRY_DSN?
web: TELEGRAM_AUTH_TOKEN, TELEGRAM_BOT_USERNAME
worker: TELEGRAM_API_ID, TELEGRAM_API_HASH

Деплой (Railway, без Template — требования к сборке)

Два сервиса: web  и worker .

Оба сервиса перед стартом выполняют alembic upgrade; если БД ещё не готова — ожидают доступности и ретраят.

DATABASE_URL и REDIS_URL подтягиваются как reference variables из сервисов Postgres и Redis в том же проекте.

Supabase конфиг един для web/worker; медиа попадают в один bucket; ссылки публичные или подписанные — единообразно.

Health-check для web (200), логи worker стабильны (нет «Missing tables», FLOOD_WAIT не валит процесс).

Acceptance (Definition of Done)

Пользователь заходит через Telegram SSO, подключает MTProto по QR, подписывается на каналы, видит ленту и топы.

По теме можно пройти полный конвейер: Редактор → Image Brief → Изображения → Publisher; получить пакеты на платформы и экспортировать.

Все приватные данные изолированы; метрики и usage собираются; лимиты работают.

Ограничения и соответствие

Соблюдать TOS Telegram: никаких данных без доступа пользователя; не нарушать rate-limits/анти-спам.

Генерация/контент — с модерацией; без чужих логотипов/торговых марок по умолчанию.
