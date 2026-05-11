#!/usr/bin/env bash
# RU container entrypoint: 安裝 protocol（editable）+ 自動 migrate + exec 原 CMD。
set -euo pipefail

# protocol package：bind-mount 到 /opt/ran-sim-protocol，editable install
# 讓 host 端改 protocol/*.py 後 restart container 即生效（免 rebuild）。
if [ -d /opt/ran-sim-protocol ]; then
    pip install --no-deps /opt/ran-sim-protocol --quiet --force-reinstall
fi

if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
