#!/bin/sh
# 分段跑 precompute:每段結束就換一個新行程,把記憶體歸零。
#
# 為什麼要分段:compute_paths 有 flush 回收不掉的殘留,而且愈積愈快
# (實測每 2000 tick 從 +74MB 漲到 +548MB 還在加速)。單一行程跑不完
# 24 小時的量就會撞 mem_limit —— 2026-09-08 就是這樣在 46.9% 被 OOM
# killer 砍掉,五個多小時的計算全部歸零。
#
# 用法:
#   docker exec -d ransim-physics sh /app/precompute/run_precompute_segmented.sh <scenario_id> [segment_ticks]
set -u
SCENARIO="${1:?需要 scenario_id}"
SEG="${2:-10000}"
LOG="/app/data/channel_cache/${SCENARIO}.precompute.log"

# 每段開頭確認 CUDA 還在。這個容器會**靜默**掉失 CUDA(cuInit -> 100),
# Mitsuba 直接退回 llvm_ad_*(CPU),不報錯只是慢 12 倍 —— 2026-09-09 因此
# 白跑了好幾個小時才發現。容器內 nvidia-smi 不可用(NVML 錯誤),要問 drjit。
# 已知觸發之一:對執行中的容器下 docker update(會改寫 cgroup,而 NVIDIA 的
# 裝置白名單掛在上面)。修法是重啟容器。
CUDA_PROBE='import drjit as dr; print("CUDA" if dr.has_backend(dr.JitBackend.CUDA) else "CPU-FALLBACK")'

echo "[runner] 分段執行 ${SCENARIO},每段 ${SEG} ticks" >> "$LOG"
while : ; do
    backend=$(python3 -c "$CUDA_PROBE" 2>/dev/null || echo PROBE-FAILED)
    echo "[runner] backend=${backend}" >> "$LOG"
    if [ "$backend" != "CUDA" ]; then
        echo "[runner] CUDA 不見了 —— 現在是 CPU 光追,慢 12 倍。" >> "$LOG"
        echo "[runner]   修法: docker restart ransim-physics,再重跑本腳本(會從 checkpoint 續)。" >> "$LOG"
    fi

    python3 /app/precompute/run_precompute.py "$SCENARIO" --resume --segment-ticks "$SEG" >> "$LOG" 2>&1
    rc=$?
    if [ "$rc" -eq 75 ]; then
        echo "[runner] 換行程接續(記憶體歸零)" >> "$LOG"
        continue
    fi
    echo "[runner] 結束,exit=${rc}" >> "$LOG"
    exit "$rc"
done
