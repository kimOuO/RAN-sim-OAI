#!/usr/bin/env bash
# 首次啟動前一次性設定。
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Copying .env.sample to .env if missing"
if [[ ! -f .env ]]; then
  cp .env.sample .env
  echo "  .env created — please edit secrets if needed"
fi

echo "==> Converting scene_config.json to Mitsuba XML"
python tools/scene_to_mitsuba.py \
  --input ../scene_config.json \
  --output scenes/umi_3sector.xml

echo "==> Done"
