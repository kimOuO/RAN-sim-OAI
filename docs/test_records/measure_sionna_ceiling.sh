#!/usr/bin/env bash
# Phase A 量測工具 — 找 Sionna 在當前場景的 tick_ms 真實上限。
#
# 原理:對每個 tick_ms,讓 DU 跑 SAMPLE_SEC 秒,量「實際 tick rate / 理論 tick rate」。
# 比值 < 0.95 代表該檔位 Sionna 卡 critical path,跟不上。最後一個 ≥ 0.95 的檔位即上限。
#
# 用法:
#   ./measure_sionna_ceiling.sh             # default port 8102, 10 sec per step
#   DU_PORT=8000 SAMPLE_SEC=30 ./measure_sionna_ceiling.sh
#   TICK_MS_LIST="500 250 125 50 30 20" ./measure_sionna_ceiling.sh
#
# 前置條件:已 Start Sim、有 UE 註冊、scene 已 build。
set -euo pipefail

DU_PORT="${DU_PORT:-8102}"
SAMPLE_SEC="${SAMPLE_SEC:-10}"
TICK_MS_LIST="${TICK_MS_LIST:-500 250 125 50 30 20 10}"
DU="http://localhost:${DU_PORT}/api/v0.1/DU/Tick/TickController"
OUT="$(dirname "$0")/sionna_ceiling_$(date +%Y%m%d_%H%M%S).csv"

# 確認 sim 已在跑
STATE=$(curl -s -XPOST "$DU/read")
RUNNING=$(echo "$STATE" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['is_running'])")
if [ "$RUNNING" != "True" ]; then
  echo "ERROR: sim 沒在跑。請先 Start Sim (確保有 UE) 再執行此腳本。"
  echo "current state: $STATE"
  exit 1
fi

echo "tick_ms,target_rate,actual_rate,ratio,verdict" > "$OUT"
echo ""
printf "%-10s %-15s %-15s %-10s %s\n" "tick_ms" "target_t/s" "actual_t/s" "ratio" "verdict"
printf "%-10s %-15s %-15s %-10s %s\n" "-------" "----------" "----------" "-----" "-------"

for TICK_MS in $TICK_MS_LIST; do
  # 設目標 tick_ms
  curl -s -XPOST "$DU/set_speed" -H 'Content-Type: application/json' \
    -d "{\"tick_ms\":$TICK_MS}" > /dev/null
  sleep 1  # 讓變更生效並穩定

  C0=$(curl -s -XPOST "$DU/read" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['tick_count'])")
  T0=$(date +%s%3N)
  sleep "$SAMPLE_SEC"
  C1=$(curl -s -XPOST "$DU/read" | python3 -c "import sys,json;print(json.load(sys.stdin)['data']['tick_count'])")
  T1=$(date +%s%3N)

  DT=$(echo "$T1 $T0" | awk '{print ($1-$2)/1000.0}')
  TICKS=$((C1 - C0))
  ACTUAL=$(echo "$TICKS $DT" | awk '{printf "%.2f", $1/$2}')
  TARGET=$(echo "$TICK_MS" | awk '{printf "%.2f", 1000.0/$1}')
  RATIO=$(echo "$ACTUAL $TARGET" | awk '{printf "%.3f", $1/$2}')
  VERDICT=$(echo "$RATIO" | awk '{if ($1 >= 0.95) print "OK"; else if ($1 >= 0.80) print "MARGINAL"; else print "OVERLOAD"}')

  printf "%-10s %-15s %-15s %-10s %s\n" "$TICK_MS" "$TARGET" "$ACTUAL" "$RATIO" "$VERDICT"
  echo "$TICK_MS,$TARGET,$ACTUAL,$RATIO,$VERDICT" >> "$OUT"
done

echo ""
echo "結果存到: $OUT"
echo ""
echo "解讀:"
echo "  OK       (ratio ≥ 0.95) → 跑得動,可選"
echo "  MARGINAL (0.80~0.95)   → 邊緣,長時間跑可能漂移"
echo "  OVERLOAD (< 0.80)      → Sionna 已飽和,該檔位不可用"
echo ""
echo "Phase B 30x 目標 = tick_ms ≈ 17ms。如果上面 20ms 仍 OK,Phase B 可行。"
echo "如果 50ms 已 OVERLOAD,代表必須走 cached Sionna(precompute)才能再壓縮。"
