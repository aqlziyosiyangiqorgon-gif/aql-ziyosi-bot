# AQL ZIYOSI — Join Request Gatekeeper Bot (Stage 1 Core)

Production-ready Telegram bot in Python for automatic verification of channel subscriptions before approving join requests in protected Telegram groups.

## Features
- **Auto Join Request Handling**: Automatically approves join requests if user is subscribed to all active required channels; otherwise declines and DMs user with missing channel links.
- **In-memory Subscription Caching**: Caches positive checks for `SUB_CACHE_SECONDS` to prevent Telegram API rate limits. Negative checks are never cached.
- **Fail-Closed Protection**: Any API error while checking required channels treats user as missing and triggers rate-limited admin alerts (cooldown 30 min per channel).
- **Auto Detection via `my_chat_member`**: Prompts admin with 1-click confirmation when bot is added to groups or channels. Rejects additions by non-admins.
- **Group Migration**: Seamlessly handles basic group -> supergroup migration (`migrate_to_chat_id`).
- **Admin Dashboard**: Manage protected groups, required channels, URLs, and administrators via `/admin`.
- **Database Flexibility**: SQLAlchemy 2.0 Async + Alembic. Works seamlessly with SQLite and PostgreSQL.

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and set your credentials:
```bash
cp .env.example .env
```

3. Run migrations and start bot:
```bash
python -m gatebot.main
```

## Running Tests
```bash
pytest -v
ruff check .
```
