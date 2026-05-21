"""RANsim-UE Django base settings — minimal HTTP server，無 DB。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "ransim-ue-dev")
DEBUG = os.getenv("DJANGO_DEBUG", "True").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "corsheaders",
    "main.apps.ue_lifecycle",
    "main.apps.scenario",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

CORS_ALLOW_ALL_ORIGINS = True

ROOT_URLCONF = "main.urls"

# 完全沒 DB 需求（in-memory state），但 Django 啟動需要 default 設定 → SQLite memory
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    },
}

USE_TZ = True
TIME_ZONE = "UTC"

LOG_DIR = os.getenv("LOG_DIR", str(BASE_DIR / "logs"))
os.makedirs(LOG_DIR, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "console"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "main.apps.ue_lifecycle": {"level": "INFO", "propagate": True},
    },
}

# RANsim 各 component URL
SIM_CU_URL = os.getenv("SIM_CU_URL", "http://cu:8000")
SIM_DU_URL = os.getenv("SIM_DU_URL", "http://du:8000")
SIM_RU_URL = os.getenv("SIM_RU_URL", "http://ru:8000")
SIM_PHYSICS_URL = os.getenv("SIM_PHYSICS_URL", "http://physics:8000")
OMNIVERSE_KIT_URL = os.getenv("OMNIVERSE_KIT_URL", "http://localhost:8080")
# Omniverse Django backend (scene + UE + handover write-back) — port 8001
OMNIVERSE_URL = os.getenv("OMNIVERSE_URL", "http://host.docker.internal:8001")

# Tick periods (ms)
UE_TRAJECTORY_PERIOD_MS = int(os.getenv("UE_TRAJECTORY_PERIOD_MS", "100"))
UE_MEASUREMENT_PERIOD_MS = int(os.getenv("UE_MEASUREMENT_PERIOD_MS", "80"))

# UE list polling cadence (s)
UE_LIST_POLL_PERIOD_SEC = int(os.getenv("UE_LIST_POLL_PERIOD_SEC", "5"))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
