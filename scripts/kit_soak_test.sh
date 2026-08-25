#!/usr/bin/env bash
# Kit HTTP 穩定性驗收 — 每 30s 探測 scene/status,共 N 次。
# 用法: nohup setsid bash kit_soak_test.sh [次數] > /home/mitlab/kit_soak.log 2>&1 &
N=${1:-17}
echo "=== Kit soak test:每 30s 探測,共 $N 次($(date '+%F %T') 開始)==="
FAIL=0
for i in $(seq 1 "$N"); do
  T=$(curl -s -o /dev/null -w "%{http_code}|%{time_total}s" --max-time 6 http://localhost:8080/scene/status 2>/dev/null)
  echo "$T" | grep -q "^200" || FAIL=$((FAIL+1))
  CPU=$(timeout 10 docker stats --no-stream --format "{{.CPUPerc}}" omniver_kit 2>/dev/null)
  printf "  %2d) %s  HTTP %s  CPU %s\n" "$i" "$(date '+%T')" "$T" "$CPU"
  sleep 22
done
echo ""
echo "★ 結束($(date '+%F %T'))— 失敗次數: $FAIL / $N"
[ "$FAIL" -eq 0 ] && echo "✅ 通過(對照基線 0/17)" || echo "❌ 有失敗 → labels 可能仍太重,需改低頻更新"
