#!/usr/bin/env bash
set -euo pipefail

# 本機初始化:建 venv、裝 deps、產 .env(若沒)、跑 migrate。
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.sample .env
  echo "[init] created .env from .env.sample (please edit secrets)"
fi

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements/local.txt

python manage.py migrate
echo "[init] done"
