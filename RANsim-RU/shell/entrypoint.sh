#!/usr/bin/env bash
# RU container entrypoint: 自動 migrate 後再 exec 原 CMD。
set -euo pipefail

if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
