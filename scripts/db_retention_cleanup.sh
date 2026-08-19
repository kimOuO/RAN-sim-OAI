#!/usr/bin/env bash
# CU 量測日誌保留策略 — 每週自動清理,留最近 N 天。
#
# 背景:CU 用「流水帳追加 + 查最新一筆」實作現況查詢,歷史筆數無人讀取
# 但無限成長(曾累積 370 萬筆/2.7GB,拖垮 KPM 端點)。此腳本只清 CU 流水帳;
# Omniverse 的回放歷史(signal/position_history)是功能資料,不在此清理。
#
# 安裝(cron,每週日 04:00):
#   crontab -e 加入:
#   0 4 * * * /home/mitlab/XAPP_DT/scripts/db_retention_cleanup.sh >> /home/mitlab/db_cleanup.log 2>&1
#
# 2026-08-19:週期由「每週日」改「每日」。ANR 驗測期間一週會累積到 100 萬筆
# (cell_measurement_log),且 anr_kpm._cum_by_relation() 改用全表 group-by 之後
# 表越大越慢。每日清理可把常態壓在 ~5 天量。
set -u
RETAIN_DAYS=5

echo "=== DB retention cleanup $(date '+%F %T')(保留 ${RETAIN_DAYS} 天)==="

if ! docker ps --format '{{.Names}}' | grep -q '^ransim-postgres$'; then
    echo "ransim-postgres 未運行,略過"
    exit 0
fi

for TBL in cu_cp_measurement_log cu_cp_cell_measurement_log; do
    N=$(docker exec ransim-postgres psql -U ransim -d cu_db -t -A -c \
        "DELETE FROM ${TBL} WHERE recorded_at <= now()-interval '${RETAIN_DAYS} days';" 2>&1)
    echo "  ${TBL}: ${N}"
done

# 一般 VACUUM(不鎖表,空間標記可重用)。
# 注意:反覆 re-arm(整表 DELETE)會留下大量死 tuple —— 2026-08-19 實測
# measurement_log 只剩 6449 筆卻佔 478 MB。一般 VACUUM 不縮檔案,需 VACUUM FULL:
#   docker exec ransim-postgres psql -U ransim -d cu_db -c "VACUUM FULL cu_cp_measurement_log;"
# (會鎖表數秒,測試空檔執行;實測 478MB→3.5MB、DB 總量 715MB→108MB)
docker exec ransim-postgres psql -U ransim -d cu_db -c \
    "VACUUM ANALYZE cu_cp_measurement_log, cu_cp_cell_measurement_log;" >/dev/null 2>&1
echo "  VACUUM 完成"

docker exec ransim-postgres psql -U ransim -d cu_db -t -c "
SELECT relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid))
FROM pg_stat_user_tables WHERE relname LIKE '%measurement%';" 2>/dev/null
echo "=== 結束 $(date '+%F %T') ==="
