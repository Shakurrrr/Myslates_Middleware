import os
from dotenv import load_dotenv
from celery.schedules import crontab

load_dotenv()

# MySlates service account credentials
MYSLATES_SERVICE_EMAIL    = os.getenv("MYSLATES_SERVICE_EMAIL")
MYSLATES_SERVICE_PASSWORD = os.getenv("MYSLATES_SERVICE_PASSWORD")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "change-me-in-production")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_celery_beat",
    "queue_app",
    "engine",
    "api",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "core.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "core.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME":   os.path.join(BASE_DIR, "db.sqlite3"),
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ── Celery ─────────────────────────────────────────────────
CELERY_BROKER_URL     = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_RESULT_BACKEND = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT  = ["json"]
CELERY_TASK_SERIALIZER = "json"

CELERY_BEAT_SCHEDULE = {
    "poll-django-to-firestore": {
        "task":     "tasks.celery_tasks.poll_django_to_firestore",
        "schedule": 300.0,   # every 5 minutes
    },
    "flush-pending-ops": {
        "task":     "tasks.celery_tasks.flush_pending_ops",
        "schedule": 60.0,    # every 60 seconds
    },
    "retry-dead-letter": {
        "task":     "tasks.celery_tasks.retry_dead_letter",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
}

# ── Firebase ───────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "./serviceAccountKey.json")

# ── MySlates Django API ────────────────────────────────────
DJANGO_API_BASE_URL = os.getenv("DJANGO_API_BASE_URL", "http://localhost:8000/api/v1")
DJANGO_API_KEY      = os.getenv("DJANGO_API_KEY", "")

# ── Sync Engine ────────────────────────────────────────────
SYNC_MAX_RETRIES  = int(os.getenv("SYNC_MAX_RETRIES", 5))
SYNC_BATCH_SIZE   = int(os.getenv("SYNC_BATCH_SIZE", 100))
SYNC_RETRY_DELAYS = [10, 30, 60, 300, 600]

# ── REST Framework ─────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}

STATIC_URL = "/static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"