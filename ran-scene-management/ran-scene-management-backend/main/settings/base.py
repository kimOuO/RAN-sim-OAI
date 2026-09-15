"""Base Django settings — ran-scene-management-backend."""
from __future__ import annotations
from pathlib import Path
from main.utils.env_loader import get_bool, get_int, get_list, get_str

BASE_DIR = Path(__file__).resolve().parent.parent.parent
SECRET_KEY = get_str("DJANGO_SECRET_KEY", "scene-management-backend-insecure-default")
DEBUG = get_bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = get_list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
INSTALLED_APPS = [
    "django.contrib.contenttypes", "django.contrib.auth", "corsheaders", "rest_framework",
    "main.apps.equipment_preset.apps.EquipmentPresetConfig",
    "main.apps.field_scene.apps.FieldSceneConfig",
    "main.apps.equipment_ran.apps.EquipmentRanConfig",
    "main.apps.equipment_ue.apps.EquipmentUeConfig",
    "main.apps.simulation_run.apps.SimulationRunConfig",
    "main.apps.render_scan_mesh.apps.RenderScanMeshConfig",
    "main.apps.render_osm_footprint.apps.RenderOsmFootprintConfig",
]
MIDDLEWARE = ["corsheaders.middleware.CorsMiddleware", "django.middleware.common.CommonMiddleware"]
ROOT_URLCONF = "main.urls"
WSGI_APPLICATION = "main.wsgi.application"
TEMPLATES = [{"BACKEND": "django.template.backends.django.DjangoTemplates", "DIRS": [], "APP_DIRS": True, "OPTIONS": {"context_processors": []}}]
DB_HOST = get_str("DB_HOST", "")
if DB_HOST:
    DATABASES = {"default": {"ENGINE": "django.db.backends.postgresql", "NAME": get_str("DB_NAME", "scene_registry_db"),
        "USER": get_str("DB_USER", "scene_registry_user"), "PASSWORD": get_str("DB_PASSWORD", ""), "HOST": DB_HOST, "PORT": get_int("DB_PORT", 5432)}}
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": str(BASE_DIR / "db.sqlite3")}}
LANGUAGE_CODE = "en-us"; TIME_ZONE = "UTC"; USE_I18N = True; USE_TZ = True
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
STATIC_URL = "/static/"
CORS_ALLOW_CREDENTIALS = True; CORS_ALLOW_ALL_ORIGINS = True
REST_FRAMEWORK = {"DEFAULT_AUTHENTICATION_CLASSES": [], "DEFAULT_PERMISSION_CLASSES": []}

# ── 3D 幾何匯入(2026-09-16 自 building-geometry-ingest 併入)──
SCANNED_ASSETS_DIR = get_str("SCANNED_ASSETS_DIR", str(BASE_DIR / "assets"))
MAX_GLB_BYTES = get_int("MAX_GLB_BYTES", 300 * 1024 * 1024)
# 匯入管線把幾何掛進 scene 時走自己的 HTTP API(同一服務;保留 §12-2 只傳 uuid 的邊界)
HTTP_REGISTRY_HOST = get_str("HTTP_REGISTRY_HOST", "127.0.0.1")
HTTP_REGISTRY_PORT = get_int("HTTP_REGISTRY_PORT", 8000)
