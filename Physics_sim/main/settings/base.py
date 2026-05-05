"""Base settings — 被 local / production / test 繼承。"""
from pathlib import Path

from main.utils.env_loader import get_bool, get_list, get_str


BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = get_str("DJANGO_SECRET_KEY", "insecure-dev-key", required=False)
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "channels",
    "main.apps.ran_signal",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
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

# 鐵則：本服務為 compute-only，無 DB。留空 dict 讓 Django 不嘗試連 DB。
DATABASES = {}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Channels WebSocket
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# 鐵則 10-3：CORS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True

# DRF：預設 JSONRenderer only；compute API 不做 auth/permission（內部網路）
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
}
