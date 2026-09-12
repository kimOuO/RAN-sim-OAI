#!/usr/bin/env bash
# Entrypoint — migrate (just for django_*; no business tables) then run Django.
set -euo pipefail

cd /app

PORT="${ADAPTER_HTTP_PORT:-8201}"

# Pre-clean stale R-NIB record (OSC m-release dissociate-fail bug workaround).
# Best-effort: 失敗也繼續啟動。需要 SDL_CLEANUP_ENABLED=1 + ssh access to RIC host
# (or local kubectl)。預設 0，user 確認可走後改成 1。
if [[ "${SDL_CLEANUP_ENABLED:-0}" == "1" ]]; then
    echo "[entrypoint] cleanup R-NIB before start"
    bash /app/shell/cleanup_rnib_before_start.sh || \
        echo "[entrypoint] R-NIB cleanup failed — continuing anyway"
fi

echo "[entrypoint] python manage.py migrate --noinput"
python manage.py migrate --noinput

echo "[entrypoint] starting Django runserver on 0.0.0.0:${PORT}"
exec python manage.py runserver "0.0.0.0:${PORT}" --noreload
