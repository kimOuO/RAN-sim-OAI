#!/bin/bash
# 用法:make_run_teiv.sh <field_id> <rid> [create|delete]
# 讀 run_logs/<rid>/o1/me_map.json(或最新 notify_added)取得 DU id,產生該 run 的 TEIV 事件檔到 run_logs/<rid>/o1/。
set -e
FIELD=$1; RID=$2; MODE=${3:-create}
D=/home/mitlab/XAPP_DT/ran-emulation-runtime/run_logs/$RID/o1
MAP=$D/me_map.json; [ -f "$MAP" ] || MAP=$(ls -t $D/notify_added_*.md | head -1)
python3 "$(dirname "$0")/gen_teiv_events.py" --field-id "$FIELD" --me-map "$MAP" --mode "$MODE" --out "$D/teiv_${RID}.${MODE}.json"
echo "$D/teiv_${RID}.${MODE}.json"
