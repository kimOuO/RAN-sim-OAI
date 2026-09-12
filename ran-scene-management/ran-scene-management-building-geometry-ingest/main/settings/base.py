"""Base Django settings — ran-scene-management-building-geometry-ingest。"""
from __future__ import annotations
from pathlib import Path
from main.utils.env_loader import get_bool, get_int, get_list, get_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = get_str("DJANGO_SECRET_KEY", "building-geometry-ingest-insecure-default")
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
INSTALLED_APPS = [
    "django.contrib.contenttypes", "django.contrib.auth", "corsheaders", "rest_framework",
    "main.apps.scan_mesh_ingest.apps.ScanMeshIngestConfig",
    "main.apps.osm_footprint_ingest.apps.OsmFootprintIngestConfig",
]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
DB_HOST = get_str("DB_HOST", "")
if DB_HOST:
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": get_str("DB_NAME", "building_ingest_db"),
        "USER": get_str("DB_USER", "building_ingest_user"), "PASSWORD": get_str("DB_PASSWORD", ""), "HOST": DB_HOST, "PORT": get_int("DB_PORT", 5432)}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}}
LANGUAGE_CODE = "en-us"; TIME_ZONE = "UTC"; USE_I18N = True; USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_URL = "/static/"
CORS_ALLOW_CREDENTIALS = True; CORS_ALLOW_ALL_ORIGINS = True
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": []}
DATA_UPLOAD_MAX_MEMORY_SIZE = 400 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 16 * 1024 * 1024
SCANNED_ASSETS_DIR = get_str("SCANNED_ASSETS_DIR", str(BASE_DIR / "assets"))
MAX_GLB_BYTES = get_int("MAX_GLB_BYTES", 300 * 1024 * 1024)
HTTP_REGISTRY_HOST = get_str("HTTP_REGISTRY_HOST", "network-element-registry")
HTTP_REGISTRY_PORT = get_int("HTTP_REGISTRY_PORT", 8000)
