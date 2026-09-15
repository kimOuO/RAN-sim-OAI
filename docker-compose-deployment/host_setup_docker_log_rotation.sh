#!/usr/bin/env bash
# Docker 容器日誌輪替(2026-09-15,postgres 因磁碟滿掛掉事故後補)。
# 需要 sudo。做的事:
#   1. 備份 /etc/docker/daemon.json,合併 log-driver=json-file + log-opts(max-size 200m × max-file 3 → 每容器上限 600 MB)
#   2. systemctl restart docker(所有容器會停再起)
#   3. 把 ransim-platform 這個 compose 專案的服務 --force-recreate,讓新設定生效(舊容器的 log 檔不受新設定約束)
# per-run 容器(cu-/du-/ru-/ue-/e2adapter-<rid>)不在這裡重建:docker 重啟後 DU tick 不會自己恢復,
# orchestrator 的健康監控會在約 2 分鐘後判 degraded 並自動 stop/start 整個 run,重建時就套用新設定。
#
# 用法: sudo bash docker-compose-deployment/host_setup_docker_log_rotation.sh [max-size] [max-file]
set -euo pipefail
MAX_SIZE="${1:-200m}"
MAX_FILE="${2:-3}"
DAEMON=/etc/docker/daemon.json
REPO="$(cd "$(dirname "$0")/.." && pwd)"

[ "$(id -u)" -eq 0 ] || { echo "請用 sudo 執行"; exit 1; }

echo "== 1/3 設定 $DAEMON(max-size=$MAX_SIZE, max-file=$MAX_FILE)"
if [ -f "$DAEMON" ]; then
  cp -a "$DAEMON" "$DAEMON.bak.$(date +%Y%m%d%H%M%S)"
fi
python3 - "$DAEMON" "$MAX_SIZE" "$MAX_FILE" <<'PY'
import json, os, sys
path, size, files = sys.argv[1], sys.argv[2], sys.argv[3]
cfg = {}
if os.path.exists(path) and os.path.getsize(path) > 0:
    with open(path) as f:
        cfg = json.load(f)
cfg["log-driver"] = "json-file"
cfg["log-opts"] = {"max-size": size, "max-file": files}
with open(path, "w") as f:
    json.dump(cfg, f, indent=4, ensure_ascii=False); f.write("\n")
print(json.dumps(cfg, indent=4, ensure_ascii=False))
PY

echo "== 2/3 重啟 docker daemon(所有容器會停再起)"
systemctl restart docker
for i in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
docker info --format 'Logging Driver: {{.LoggingDriver}}'

echo "== 3/3 重建 ransim-platform 的 compose 服務,讓新 log 設定生效"
cd "$REPO"
docker compose up -d --force-recreate --no-build

echo
echo "== 驗證:新容器的 log 設定"
docker inspect ransim-postgres --format 'ransim-postgres: {{.HostConfig.LogConfig.Type}} {{json .HostConfig.LogConfig.Config}}'
echo
echo "完成。per-run 容器會由 orchestrator 健康監控在約 2 分鐘內自動重建(套用新設定)。"
echo "之後可用下面指令看各容器 log 佔用:"
echo "  sudo du -sh /var/lib/docker/containers/*/ | sort -h | tail"
