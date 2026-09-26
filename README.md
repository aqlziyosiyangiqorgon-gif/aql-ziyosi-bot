# AQL ZIYOSI — Join Request Gatekeeper Bot

Production-ready Telegram bot in Python designed to act as an automated membership gatekeeper for Telegram groups.

## Overview
When a user sends a **join request** to any "protected" Telegram group, the bot automatically checks whether the user is subscribed to all active "required" Telegram channels.
- **Subscribed to all required channels**: The bot automatically **approves** the request and sends a welcome direct message.
- **Missing one or more channels**: The bot automatically **declines** the request and sends a direct message clearly listing which channels must be joined first (including clickable invite links).
- **Admin Self-Service**: Group administrators configure protected groups, required channels, invite URLs, and bot admins directly via `/admin` or by adding the bot as an administrator in groups/channels.

---

## Architecture
- **Language & Runtime**: Python 3.11+
- **Telegram Framework**: [aiogram 3.x](https://docs.aiogram.dev/) (Long polling with `chat_join_request` and `my_chat_member` updates)
- **Database Layer**: SQLAlchemy 2.0 Async + Alembic migrations. Works out-of-the-box with SQLite (`aiosqlite`) and PostgreSQL (`asyncpg`).
- **Subscription Cache**: In-memory TTL cache (`SUB_CACHE_SECONDS`) caching *only* positive results to prevent Telegram API rate limits.
- **Fail-Closed Security**: Any Telegram API failure during membership checks treats the user as unverified and triggers rate-limited administrator alerts.
- **Scheduler**: [APScheduler](https://apscheduler.readthedocs.io/) running daily SQLite online backups at 03:00 and daily permission audits at 09:00 (Asia/Tashkent).

---

## Setup & Quick Start

### 1. Requirements
- Python 3.11 or higher
- SQLite3 or PostgreSQL

### 2. Installation
```bash
git clone <repository_url>
cd gatebot
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Environment Configuration
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Configure your `.env` variables:
```dotenv
BOT_TOKEN=123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ_example
ADMIN_IDS=111222333,444555666
DATABASE_URL=sqlite+aiosqlite:///./data/bot.db
BACKUP_CHAT_ID=111222333
SUB_CACHE_SECONDS=60
TIMEZONE=Asia/Tashkent
LOG_LEVEL=INFO
```

### 4. Database Migrations & Running
Run migrations and start the bot:
```bash
python -m gatebot.main
```

---

## BotFather Configuration
1. Open [@BotFather](https://t.me/BotFather) on Telegram.
2. Create or select your bot (`/newbot` or `/mybots`).
3. Enable adding the bot to groups:
   - Go to **Bot Settings** -> **Allow Groups?** -> Select **Turn groups on** (or send `/setjoingroups` -> `Enable`).
4. Privacy Mode:
   - Privacy Mode can stay **Enabled** or Disabled (`/setprivacy`). The bot receives `chat_join_request` and `my_chat_member` regardless of privacy settings.
5. Set Commands (`/setcommands`):
```text
start - Botni ishga tushirish
admin - Administrator boshqaruv paneli
```

---

## Telegram Admin Rights & Permissions

### In Protected Groups:
1. Set the Group Type to **Private**.
2. Under Group Permissions / Invite Links, enable **"Approve new members"** (Join Requests mode).
3. Add the bot as an **Administrator** with at least:
   - **Invite Users via Link** (or "Manage Join Requests" / "Add Members").
4. The bot will automatically detect its promotion and prompt the admin in DM with:
   `"✅ Ha, himoyalash"` / `"❌ Yo'q"`.

### In Required Channels:
1. Add the bot as an **Administrator** to the channel (any basic admin rights that allow `get_chat_member` checks).
2. The bot will automatically detect its promotion and prompt the admin in DM with:
   `"✅ Ha, majburiy qilish"` / `"❌ Yo'q"`.
3. If the channel is private, set an invite URL via `/admin` -> **Kanallar** -> **[Kanal]** -> **Havolani o'zgartirish**.

---

## `/admin` Management Panel
Only accessible in private chat to users in `ADMIN_IDS` and database administrators:
- **👥 Guruhlar**: View protected groups, check permissions (`🔗 Tekshirish`), toggle active/inactive, or add manually by ID/forwarded message.
- **📢 Kanallar**: View required channels, toggle active status, adjust priority/sorting (`sort_order`), update invite URLs, or add manually.
- **👥 Adminlar**: List admins (super admins marked with ⭐ cannot be removed), add new admins by Telegram ID, remove DB admins.
- **📊 Statistika**: View total approved/declined requests (all-time & last 7 days), per-group breakdown, and top missing channels.
- **💾 Zaxira nusxa**: Trigger an immediate online backup dispatch.

---

## Backups & Restores

### Online SQLite Backup
- Uses Python's native `sqlite3.Connection.backup()` to create a consistent, lock-free snapshot even during live traffic.
- Zips the snapshot and delivers it to `BACKUP_CHAT_ID`.
- Scheduled daily at **03:00 Asia/Tashkent**.
- Manual trigger via CLI:
```bash
python scripts/backup_now.py
```

### Restoring from Backup
1. Stop the bot: `systemctl stop gatebot` (or `docker-compose down`).
2. Extract the `.zip` archive:
   ```bash
   unzip gatebot_backup_2026-09-26_03-00-00.zip
   ```
3. Replace `data/bot.db` with the extracted `.db` file:
   ```bash
   cp bot_2026-09-26_03-00-00.db data/bot.db
   ```
4. Start the bot: `systemctl start gatebot` (or `docker-compose up -d`).

---

## Deployment

### Systemd Service (Ubuntu/Debian)
1. Copy service file:
   ```bash
   sudo cp deploy/gatebot.service /etc/systemd/system/gatebot.service
   ```
2. Reload and enable:
   ```bash
   sudo systemctl daemon-reload
   sudo systemctl enable --now gatebot
   ```
3. Check status and logs:
   ```bash
   sudo systemctl status gatebot
   journalctl -u gatebot -f
   ```

### Docker & Docker Compose
```bash
cd deploy
docker-compose up -d --build
docker-compose logs -f
```

---

## Manual Test Checklist
- [x] **Group auto-detection**: Add bot to private group with "Approve new members" enabled -> bot sends prompt -> clicking "Ha" registers it.
- [x] **Unsubscribed user rejected**: User not subscribed sends join request -> request declined -> bot DMs missing channel links.
- [x] **Subscribed user approved**: User joins channels and sends join request -> request approved -> bot DMs welcome message.
- [x] **Bot removed from group**: Bot kicked/demoted -> group marked `is_active=False`, admin alerted.
- [x] **Bot removed from channel**: Bot removed from required channel -> channel marked `is_active=False`, admin alerted loudly.
- [x] **Admin panel**: `/admin` allows full CRUD on groups, channels, and admins; prevents removing super admins.
- [x] **Backup command**: Produces a valid, restorable SQLite `.zip` file sent to `BACKUP_CHAT_ID`.
- [x] **Persistence**: Restarting the bot preserves all registered groups, channels, and admin records.

---

## Troubleshooting
- **Bot does not receive join requests**: Ensure the group is set to **Private** and **"Approve new members"** is toggled ON in Telegram group settings.
- **Bot cannot approve requests**: Verify the bot has **"Invite users via link"** admin permission in the group.
- **Private channel has no link in decline DM**: Provide a display invite link via `/admin` -> **Kanallar** -> **[Kanal]** -> **Havola**.

---

## Assumptions
- The bot token is kept secure and never committed to version control.
- Super administrators (`ADMIN_IDS`) have permanent, immutable access.
- In-memory subscription cache (`SUB_CACHE_SECONDS=60`) is per-process; restarting the bot harmlessly clears the cache.
