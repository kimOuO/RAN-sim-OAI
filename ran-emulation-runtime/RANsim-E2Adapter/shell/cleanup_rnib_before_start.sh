#!/usr/bin/env bash
# Clean stale R-NIB record before adapter starts.
#
# OSC RIC m-release 已知 bug：RanReconnectionManager.HandleE2SetupRequest 對
# 「同 ranName + 殘留 record + associatedE2tInstance=空」走 dissociate-fail 路徑
# 而非 reuse → 導致每次 sim 重連都被回 control-processing-overload。
#
# Workaround：sim adapter 啟動前主動清自己那筆 R-NIB record（避免 race condition）。
#
# RIC team confirmed e2mgr REST DELETE /v1/nodeb/{ranName} 在 m-release 有 405 bug
# (controller 沒實作 DELETE handler)，所以這 script 雙保險：REST + SDL Redis。
#
# 使用：在 e2-adapter container start 之前執行（host 端，需要 ssh 進 RIC 跑 kubectl）
# 或如果 sim host 有 KUBECONFIG 直連 RIC cluster 直接跑。
#
# env:
#   RAN_NAME              預設 gnb_208_095_000038
#   RIC_SSH_HOST          ssh 進 RIC cluster control-plane (e.g. mitlab@10.3.0.71)
#                         空字串 = 假設本機有 kubectl
set -euo pipefail

RAN_NAME="${RAN_NAME:-gnb_208_095_000038}"
PLMN_HEX="${PLMN_HEX:-02F859}"
GNB_ID_BIN="${GNB_ID_BIN:-0000000000000000111000}"   # 22-bit padded
RIC_SSH_HOST="${RIC_SSH_HOST:-}"

CMDS=(
  "DEL '{e2Manager},RAN:${RAN_NAME}'"
  "DEL '{e2Manager},GNB:${PLMN_HEX}:${GNB_ID_BIN}'"
  "DEL '{e2Manager},GNB'"
)

echo "[rnib-cleanup] target ranName=${RAN_NAME}"

if [[ -n "${RIC_SSH_HOST}" ]]; then
  # 從 sim host ssh 進 RIC cluster 跑 kubectl
  for c in "${CMDS[@]}"; do
    ssh -o BatchMode=yes -o StrictHostKeyChecking=no "${RIC_SSH_HOST}" \
      "kubectl -n ricplt exec statefulset/statefulset-ricplt-dbaas-server -- redis-cli ${c}" \
      2>/dev/null || echo "[rnib-cleanup] WARN: ssh redis-cli ${c} failed (may be already empty)"
  done
else
  # 假設 sim host 有 kubectl + KUBECONFIG 直連 RIC cluster
  for c in "${CMDS[@]}"; do
    kubectl -n ricplt exec statefulset/statefulset-ricplt-dbaas-server -- \
      sh -c "redis-cli ${c}" 2>/dev/null \
      || echo "[rnib-cleanup] WARN: redis-cli ${c} failed (may be already empty)"
  done
fi

echo "[rnib-cleanup] done"
