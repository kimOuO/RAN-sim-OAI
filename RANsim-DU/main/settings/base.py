"""共用 Django settings — local / production / test 都繼承這個。"""
from __future__ import annotations

from pathlib import Path

from main.utils.env_loader import get_bool, get_list, get_str

BASE_DIR = Path(__file__).resolve().parents[2]

SECRET_KEY = get_str("DJANGO_SECRET_KEY", "ransim-du-dev-secret-please-override")
DEBUG = get_bool("DJANGO_DEBUG", default=True)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["*"])

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "corsheaders",
    "main.apps.mac.apps.MacConfig",
    "main.apps.rlc.apps.RlcConfig",
    "main.apps.phy_high.apps.PhyHighConfig",
    "main.apps.f1ap_du.apps.F1apDuConfig",
    "main.apps.fapi_north.apps.FapiNorthConfig",
    "main.apps.tick.apps.TickConfig",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "main.middleware.ran_log_middleware.RanLogMiddleware",
]

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
ASGI_APPLICATION = "main.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "HOST": get_str("DB_HOST", "postgres"),
        "PORT": get_str("DB_PORT", "5432"),
        "NAME": get_str("DB_NAME", "du_db"),
        "USER": get_str("DB_USER", "ransim"),
        "PASSWORD": get_str("DB_PASSWORD", "ransim"),
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
USE_TZ = True
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
