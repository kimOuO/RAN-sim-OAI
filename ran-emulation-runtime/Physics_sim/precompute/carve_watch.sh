#!/bin/sh
# 盯著 corridor_24h 的進度,算到哪就把對應的 8 小時切片切出來。
# 跟 chat 無關,自己跑到三段都好為止。
set -u
LOG=/app/data/channel_cache/carve_watch.log
echo "[watch] 啟動 $(date -u)" >> "$LOG"
for spec in "corridor_08_16 28800 57600" "corridor_16_24 57600 86400"; do
    set -- $spec
    sid=$1; t0=$2; t1=$3
    echo "[watch] 等 ${sid}(需要算到 $((t1 * 2)) tick)" >> "$LOG"
    while : ; do
        if python3 /tmp/carve.py "$sid" "$t0" "$t1" >> "$LOG" 2>&1; then
            echo "[watch] ${sid} 完成" >> "$LOG"
            break
        fi
        sleep 300
    done
done
echo "[watch] 三段全部完成 $(date -u)" >> "$LOG"
