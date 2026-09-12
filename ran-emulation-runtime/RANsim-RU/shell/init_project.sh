#!/usr/bin/env bash
# 把 sibling 專案的 ran-sim-protocol 同步到 _vendored/，給 Docker build COPY 用。
# 本機開發如果直接 pip install -e，可以略過這步。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIBLING_PROTOCOL="${SIBLING_PROTOCOL:-/home/mitlab/XAPP_DT/Physics_sim/ran-sim-protocol}"
DEST="${REPO_ROOT}/_vendored/ran-sim-protocol"

if [[ ! -d "${SIBLING_PROTOCOL}" ]]; then
  echo "[init_project] ran-sim-protocol not found at ${SIBLING_PROTOCOL}" >&2
  echo "[init_project] override with: SIBLING_PROTOCOL=/path/to/ran-sim-protocol $0" >&2
  exit 1
fi

mkdir -p "$(dirname "${DEST}")"
rsync -a --delete \
  --exclude '__pycache__' \
  --exclude '*.egg-info' \
  --exclude '.pytest_cache' \
  "${SIBLING_PROTOCOL}/" "${DEST}/"

echo "[init_project] synced ran-sim-protocol -> ${DEST}"
