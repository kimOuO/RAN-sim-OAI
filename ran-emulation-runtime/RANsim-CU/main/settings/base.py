"""Base Django settings shared across local / production / test."""
from __future__ import annotations

from pathlib import Path

from main.utils.env_loader import get_bool, get_int, get_list, get_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = get_str("DJANGO_SECRET_KEY", "ransim-cu-insecure-default")
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "daphne",                              # ASGI server（必須在 staticfiles 之前；WebSocket 用）
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "channels",                            # WebSocket framework
    "corsheaders",
    "rest_framework",
    "main.apps.cu_cp.apps.CuCpConfig",
    "main.apps.cu_up.apps.CuUpConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "main.middleware.ran_log_middleware.RanLogMiddleware",
]

ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
ASGI_APPLICATION = "main.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

DB_HOST = get_str("DB_HOST", "")
if DB_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": get_str("DB_NAME", "cu_db"),
            "USER": get_str("DB_USER", "cu_user"),
            "PASSWORD": get_str("DB_PASSWORD", ""),
            "HOST": DB_HOST,
            "PORT": get_int("DB_PORT", 5432),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": str(BASE_DIR / "db.sqlite3"),
        }
    }

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_URL = "/static/"

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

# Channels：用 in-memory channel layer（單 process 夠用；多 worker 才要 Redis）
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    },
}
