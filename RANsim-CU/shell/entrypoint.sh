#!/usr/bin/env bash
set -euo pipefail

# 1. 安裝 sibling protocol package（每次 entrypoint 從 bind-mount 重灌）
#    /opt mount 是 :ro，無法 editable，改用一般 install（複製到 site-packages）。
#    Workflow：host 改 protocol/*.py → docker compose restart <svc> → 新 code 生效。
if [ -d /opt/ran-sim-protocol ]; then
    pip install --no-deps /opt/ran-sim-protocol --quiet --force-reinstall
elif [ -d /tmp/ran-sim-protocol ]; then
    pip install --no-deps /tmp/ran-sim-protocol --quiet --force-reinstall
fi

# 2. 跑 migrate（要 SKIP_AUTO_MIGRATE=1 才跳過）
if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
