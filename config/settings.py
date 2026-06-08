# config/settings.py

import os
from dotenv import load_dotenv
load_dotenv()

# ── Firebase ───────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH")
DJANGO_API_BASE_URL        = os.getenv("DJANGO_API_BASE_URL")
DJANGO_API_KEY             = os.getenv("DJANGO_API_KEY")

SYNC_MAX_RETRIES  = int(os.getenv("SYNC_MAX_RETRIES", 5))
SYNC_BATCH_SIZE   = int(os.getenv("SYNC_BATCH_SIZE", 100))
SYNC_RETRY_DELAYS = [10, 30, 60, 300, 600]

# ── Celery ─────────────────────────────────────────────
from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "flush-sync-queue": {
        "task":     "sync.flush_pending_ops",
        "schedule": 60.0,
    },
    "retry-dead-letter": {
        "task":     "sync.retry_dead_letter",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
}
