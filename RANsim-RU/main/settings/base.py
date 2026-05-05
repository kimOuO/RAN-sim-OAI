"""Base settings — 被 local / production / test 繼承。

backend_rule §3-2-1：禁止 os.getenv()，全經 env_loader。
"""
from pathlib import Path

from main.utils.env_loader import get_bool, get_int, get_list, get_str


BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = get_str("DJANGO_SECRET_KEY", "insecure-dev-key")
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "rest_framework",
    "main.apps.antenna",
    "main.apps.phy_low",
    "main.apps.beamforming",
    "main.apps.physics_client",
    "main.apps.fapi_south",
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

# backend_rule §11-1：預設 PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": get_str("DB_HOST", "localhost"),
        "PORT": get_int("DB_PORT", 5432),
        "NAME": get_str("DB_NAME", "ru_db"),
        "USER": get_str("DB_USER", "ru"),
        "PASSWORD": get_str("DB_PASSWORD", "ru"),
    },
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = False
USE_TZ = True

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# §10：CORS
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True

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

# 對外 HTTP client target hosts（DU、Physics）
HTTP_DU_HOST = get_str("HTTP_DU_HOST", "du")
HTTP_DU_PORT = get_int("HTTP_DU_PORT", 8000)
HTTP_PHYSICS_HOST = get_str("HTTP_PHYSICS_HOST", "physics")
HTTP_PHYSICS_PORT = get_int("HTTP_PHYSICS_PORT", 8000)

# RU 預設天線配置 / numerology / noise floor
RU_DEFAULT_ANTENNA_ROWS = get_int("RU_DEFAULT_ANTENNA_ROWS", 4)
RU_DEFAULT_ANTENNA_COLS = get_int("RU_DEFAULT_ANTENNA_COLS", 2)
RU_DEFAULT_POLARIZATION = get_str("RU_DEFAULT_POLARIZATION", "cross")
RU_DEFAULT_PATTERN = get_str("RU_DEFAULT_PATTERN", "tr38901")
RU_NUMEROLOGY = get_int("RU_NUMEROLOGY", 1)
