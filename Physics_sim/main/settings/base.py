"""Base settings — 被 local / production / test 繼承。"""
from pathlib import Path

from main.utils.env_loader import get_bool, get_list, get_str, get_int


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
    # scenario_store：physics_db 上的劇本/場景倉庫(讓 RAN sim 可脫離 Omniverse)。
    # ran_signal 仍維持 compute-only、不碰 DB;只有這個 app 用 DB。
    "main.apps.scenario_store",
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

# ran_signal 計算路徑仍是 compute-only、不碰 DB。
# 但 scenario_store 需要 physics_db 存劇本/場景(讓 sim 可脫離 Omniverse)。
# 有設 DB_HOST 才配 DB(容器內恆有);純 compute 部署不設 DB_HOST → 維持無 DB。
# Django 是 lazy connect,compute 端點不查 DB → DB 掛掉也不影響光追。
_DB_HOST = get_str("DB_HOST", "")
if _DB_HOST:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "HOST": _DB_HOST,
            "PORT": get_int("DB_PORT", 5432),
            "NAME": get_str("DB_NAME", "physics_db"),
            "USER": get_str("DB_USER", "ransim"),
            "PASSWORD": get_str("DB_PASSWORD", "ransim"),
            "CONN_MAX_AGE": 60,
        }
    }
else:
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
