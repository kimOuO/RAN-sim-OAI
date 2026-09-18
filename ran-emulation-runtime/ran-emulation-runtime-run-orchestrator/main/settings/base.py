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
HTTP_REGISTRY_HOST = get_str("HTTP_REGISTRY_HOST", "scene-management-backend")
HTTP_REGISTRY_PORT = get_int("HTTP_REGISTRY_PORT", 8000)
HTTP_UE_DRIVER_HOST = get_str("HTTP_UE_DRIVER_HOST", "ue")
HTTP_UE_DRIVER_PORT = get_int("HTTP_UE_DRIVER_PORT", 8000)
HTTP_CU_HOST = get_str("HTTP_CU_HOST", "cu")
HTTP_CU_PORT = get_int("HTTP_CU_PORT", 8000)
HTTP_E2ADAPTER_HOST = get_str("HTTP_E2ADAPTER_HOST", "host.docker.internal")   # e2adapter 走 host network
HTTP_E2ADAPTER_PORT = get_int("HTTP_E2ADAPTER_PORT", 8201)

# P4-1 per-run 容器(docker SDK;需掛 /var/run/docker.sock)
PER_RUN_ENABLED = get_bool("PER_RUN_ENABLED", False)
PER_RUN_NETWORK = get_str("PER_RUN_NETWORK", "ransim-net")
PER_RUN_PG_ADMIN_DB = get_str("PER_RUN_PG_ADMIN_DB", "ransim_root")
PER_RUN_HEALTH_SEC = get_int("PER_RUN_HEALTH_SEC", 5)
# 自動復原(2026-09-15):任一角色連續不健康超過 AUTO_RESTART_SEC 秒 → 先 dump CU/DU 堆疊再 stop/start 整個 run;0 = 關閉。兩次重啟至少隔 COOLDOWN 秒。
PER_RUN_AUTO_RESTART_SEC = get_int("PER_RUN_AUTO_RESTART_SEC", 120)
PER_RUN_AUTO_STOP_ON_FINISH = get_bool("PER_RUN_AUTO_STOP_ON_FINISH", True)   # UE 劇本跑完(模擬時間 ≥ duration_sec)自動停 run
PER_RUN_AUTO_RESTART_COOLDOWN_SEC = get_int("PER_RUN_AUTO_RESTART_COOLDOWN_SEC", 600)
# 場景停止後通知 RIC 端清 R-NIB 殘留(m-release 不支援 E2 Removal;收尾第 4 步)。空 = 只記 log
RIC_STOP_WEBHOOK_URL = get_str("RIC_STOP_WEBHOOK_URL", "")
PRECOMPUTE_LOG_DIR = get_str("PRECOMPUTE_LOG_DIR", "/data/channel_cache")   # precompute 容器的 log / npz 目錄(唯讀 mount)
# RIC 場景閘道(ric-scenario-gw,RIC 端 2026-09-14):場景註冊 / R-NIB 清理 / meid 反查。空 = 只記 log
RIC_GATEWAY_URL = get_str("RIC_GATEWAY_URL", "")
RIC_GATEWAY_PROFILE = get_str("RIC_GATEWAY_PROFILE", "anr")
# 宣告場景時開放的控制類型(閘道 controlPolicy.allowedStyles);名稱由 RIC 閘道定義,逗號分隔
RIC_GATEWAY_ALLOWED_STYLES = get_list("RIC_GATEWAY_ALLOWED_STYLES", default=["rc-reportcgi", "anr-add"])
# 註冊後是否部署專屬 xApp pod(POST /v1/scenarios/{id}/xapp)。RIC 端 dt-anr 尚未參數化(XAPP_NAME 寫死),先關;他們好了改 on
RIC_GATEWAY_DEPLOY_XAPP = get_bool("RIC_GATEWAY_DEPLOY_XAPP", False)
