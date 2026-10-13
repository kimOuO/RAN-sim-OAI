"""RANsim-AMF Django settings —— 全場共用的 AMF(多 gNB 計畫 4.1)。狀態全在記憶體,不用 DB。"""
from __future__ import annotations

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "ransim-amf-dev")
DEBUG = os.getenv("DJANGO_DEBUG", "False").lower() == "true"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "*").split(",")

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "main.apps.amf",
]

MIDDLEWARE = ["django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "main.urls"

# Django 啟動需要 default DB 設定;AMF 本身不落地(一場一個容器,場次結束即丟)
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

USE_TZ = True
TIME_ZONE = "UTC"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"console": {"format": "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "console"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}

AMF_NAME = os.getenv("AMF_NAME", "ransim-amf")
PLMN_MCC = os.getenv("PLMN_MCC", "208")
PLMN_MNC = os.getenv("PLMN_MNC", "95")
AMF_REGION_ID = int(os.getenv("AMF_REGION_ID", "1"))
AMF_SET_ID = int(os.getenv("AMF_SET_ID", "1"))
AMF_POINTER = int(os.getenv("AMF_POINTER", "1"))
# NGAP 往 CU 的 HTTP 逾時(秒)
NGAP_TIMEOUT_SEC = float(os.getenv("NGAP_TIMEOUT_SEC", "5"))
