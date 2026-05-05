#!/usr/bin/env bash
set -euo pipefail

# 1. 安裝 sibling protocol package（若 mount 進來）
if [ -d /tmp/ran-sim-protocol ]; then
    pip install --no-deps --quiet /tmp/ran-sim-protocol
fi

# 2. 跑 migrate（要 SKIP_AUTO_MIGRATE=1 才跳過）
if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
