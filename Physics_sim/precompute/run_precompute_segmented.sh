#!/bin/sh
# 分段跑 precompute:每段結束就換一個新行程,把記憶體歸零。
#
# 為什麼要這樣:compute_paths 有 flush 回收不掉的殘留,而且愈積愈快
# (實測每 2000 tick 從 +74MB 漲到 +548MB 還在加速)。單一行程跑不完
# 24 小時的量就會撞 mem_limit —— 2026-09-08 就是這樣在 46.9% 被 OOM
# killer 砍掉,五個多小時的計算全部歸零。
#
# 用法: docker exec -d ransim-physics sh /app/precompute/run_precompute_segmented.sh <scenario_id> [segment_ticks]
set -u
SCENARIO="${1:?需要 scenario_id}"
SEG="${2:-10000}"
LOG="/app/data/channel_cache/${SCENARIO}.precompute.log"

echo "[runner] 分段執行 ${SCENARIO},每段 ${SEG} ticks" >> "$LOG"
while : ; do
    python3 /app/precompute/run_precompute.py "$SCENARIO" --resume --segment-ticks "$SEG" >> "$LOG" 2>&1
    rc=$?
    if [ "$rc" -eq 75 ]; then
        echo "[runner] 換行程接續(記憶體歸零)" >> "$LOG"
        continue
    fi
    echo "[runner] 結束,exit=${rc}" >> "$LOG"
    exit "$rc"
done
