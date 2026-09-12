#!/bin/bash
# RANsim-UE 啟動腳本 — 單純 Django HTTP server（無 DB）
set -e

cd /app
echo "[entrypoint] Starting RANsim-UE..."
echo "[entrypoint] CU URL: ${SIM_CU_URL:-http://cu:8000}"
echo "[entrypoint] DU URL: ${SIM_DU_URL:-http://du:8000}"
echo "[entrypoint] RU URL: ${SIM_RU_URL:-http://ru:8000}"

# UeLifecycleManager 在 AppConfig.ready() 起背景 thread
exec python manage.py runserver 0.0.0.0:8000 --noreload
