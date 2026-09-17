#!/usr/bin/env bash
# RU container entrypoint: 安裝 protocol（editable）+ 自動 migrate + exec 原 CMD。
set -euo pipefail

# protocol package：bind-mount 到 /opt/ran-sim-protocol，editable install
# 讓 host 端改 protocol/*.py 後 restart container 即生效（免 rebuild）。
if [ -d /opt/ran-sim-protocol ]; then
    # 2026-09-17:先複製到容器私有目錄再裝。多個容器共用這個掛載目錄,重開機時同時啟動會在
    # 共用的 build/ 互相衝突(Errno 17 File exists)→ 安裝失敗、容器無限重啟。
    _proto=$(mktemp -d)
    cp -r /opt/ran-sim-protocol/pyproject.toml /opt/ran-sim-protocol/ran_sim_protocol "$_proto"/
    cp /opt/ran-sim-protocol/README.md "$_proto"/ 2>/dev/null || true
    pip install --no-deps "$_proto" --quiet --force-reinstall
    rm -rf "$_proto"
fi

if [ "${SKIP_AUTO_MIGRATE:-0}" != "1" ]; then
    echo "[entrypoint] python manage.py migrate --noinput"
    python manage.py migrate --noinput
fi

exec "$@"
