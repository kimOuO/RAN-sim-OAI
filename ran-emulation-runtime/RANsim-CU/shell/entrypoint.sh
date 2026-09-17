#!/usr/bin/env bash
set -euo pipefail

# 1. 安裝 sibling protocol package（每次 entrypoint 從 bind-mount 重灌）
#    /opt mount 是 :ro，無法 editable，改用一般 install（複製到 site-packages）。
#    Workflow：host 改 protocol/*.py → docker compose restart <svc> → 新 code 生效。
if [ -d /opt/ran-sim-protocol ]; then
    # 2026-09-17:先複製到容器私有目錄再裝。多個容器共用這個掛載目錄,重開機時同時啟動會在
    # 共用的 build/ 互相衝突(Errno 17 File exists)→ 安裝失敗、容器無限重啟。
    _proto=$(mktemp -d)
    cp -r /opt/ran-sim-protocol/pyproject.toml /opt/ran-sim-protocol/ran_sim_protocol "$_proto"/
    cp /opt/ran-sim-protocol/README.md "$_proto"/ 2>/dev/null || true
    pip install --no-deps "$_proto" --quiet --force-reinstall
    rm -rf "$_proto"
elif [ -d /tmp/ran-sim-protocol ]; then
    pip install --no-deps /tmp/ran-sim-protocol --quiet --force-reinstall
fi

# 2. 跑 migrate（要 SKIP_AUTO_MIGRATE=1 才跳過）
if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
