"""Base Django settings — ran-emulation-runtime-run-orchestrator。"""
from __future__ import annotations
from pathlib import Path
from main.utils.env_loader import get_bool, get_int, get_list, get_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = get_str("DJANGO_SECRET_KEY", "run-orchestrator-insecure-default")
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
INSTALLED_APPS = [
    "django.contrib.contenttypes", "django.contrib.auth", "corsheaders", "rest_framework",
    "main.apps.run_lifecycle.apps.RunLifecycleConfig",
    "main.apps.run_telemetry_archive.apps.RunTelemetryArchiveConfig",
]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
DB_HOST = get_str("DB_HOST", "")
if DB_HOST:
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": get_str("DB_NAME", "run_orchestrator_db"),
        "USER": get_str("DB_USER", "run_orchestrator_user"), "PASSWORD": get_str("DB_PASSWORD", ""), "HOST": DB_HOST, "PORT": get_int("DB_PORT", 5432)}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}}
LANGUAGE_CODE = "en-us"; TIME_ZONE = "UTC"; USE_I18N = True; USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_URL = "/static/"
CORS_ALLOW_CREDENTIALS = True; CORS_ALLOW_ALL_ORIGINS = True
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": []}
# 跨系統 API(backend_rule §8-2)
HTTP_REGISTRY_HOST = get_str("HTTP_REGISTRY_HOST", "network-element-registry")
HTTP_REGISTRY_PORT = get_int("HTTP_REGISTRY_PORT", 8000)
HTTP_UE_DRIVER_HOST = get_str("HTTP_UE_DRIVER_HOST", "ue")
HTTP_UE_DRIVER_PORT = get_int("HTTP_UE_DRIVER_PORT", 8000)
