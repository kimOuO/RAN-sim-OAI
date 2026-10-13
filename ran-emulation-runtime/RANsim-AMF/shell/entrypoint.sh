#!/bin/sh
# RANsim-AMF 啟動:單一 process(UE context 表在記憶體,多 worker 會各有一份)
set -e
cd /app
echo "[entrypoint] Starting RANsim-AMF (${AMF_NAME:-ransim-amf})"
exec gunicorn main.wsgi:application -b 0.0.0.0:8000 --workers 1 --threads 8 --timeout 60
