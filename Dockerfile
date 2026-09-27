FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data logs

# Railway Volume mount point
VOLUME ["/data"]

# Default DATABASE_URL pointing to the volume
ENV DATABASE_URL=sqlite+aiosqlite:////data/bot.db

CMD ["python", "-m", "gatebot.main"]
