#!/bin/bash
# RAN-side soak monitor — 對齊 RIC team 的 12.5h cadence (25 × 30min sample)
# 用法:
#   nohup ./ran-side-soak-monitor.sh > /home/mitlab/XAPP_DT/plan/soak-ran.log 2>&1 &
#   disown
#
# 輸出:
#   /home/mitlab/XAPP_DT/plan/soak-ran.csv  — 每 30 min 一筆 sample
#   stdout 也印一份，方便 tail 看
#
# 對應 RIC 端 InfluxDB 監控的 columns，方便明早交接對齊。

set -u
cd /home/mitlab/XAPP_DT/plan

CSV=/home/mitlab/XAPP_DT/plan/soak-ran.csv
INTERVAL_SEC=1800        # 30 min, 跟 RIC 團隊對齊
TOTAL_SAMPLES=26         # 13 hours, 比 RIC 多半小時涵蓋他們的範圍

# CSV header (only write if file doesn't exist)
if [ ! -f "$CSV" ]; then
  echo "ts_utc,sample_n,sctp_connected,e2_setup_ok,accepted_rfs,pdu_sent,pdu_recv,last_disc_age_min,last_error,app_log_bytes,json_log_bytes,du_tick_running,e2adapter_cpu_pct,e2adapter_mem_mb" > "$CSV"
fi

sample_n=0
while [ $sample_n -lt $TOTAL_SAMPLES ]; do
  sample_n=$((sample_n + 1))
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

  # adapter status (POST endpoint)
  adapter=$(curl -sS -m 5 -X POST http://localhost:8201/api/v0.1/E2Adapter/Status/AdapterStatusReader/read 2>/dev/null)
  if [ -z "$adapter" ]; then
    sctp_connected=ERR
    e2_setup_ok=ERR
    accepted_rfs=""
    pdu_sent=0
    pdu_recv=0
    last_disc_age_min=ERR
    last_error=adapter_unreachable
  else
    sctp_connected=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('sctp_link',{}).get('connected'))" 2>/dev/null || echo ERR)
    e2_setup_ok=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('e2_setup',{}).get('completed'))" 2>/dev/null || echo ERR)
    accepted_rfs=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print('|'.join(map(str,d.get('data',{}).get('e2_setup',{}).get('accepted_ran_function_ids',[]))))" 2>/dev/null || echo "")
    pdu_sent=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('sctp_link',{}).get('pdu_sent_count',0))" 2>/dev/null || echo 0)
    pdu_recv=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('sctp_link',{}).get('pdu_recv_count',0))" 2>/dev/null || echo 0)
    last_disc_age_min=$(echo "$adapter" | python3 -c "
import sys,json,time
d=json.load(sys.stdin)
ld=d.get('data',{}).get('sctp_link',{}).get('last_disconnect_at_ms',0)
print('never' if not ld else f'{(int(time.time()*1000)-ld)/60000:.1f}')
" 2>/dev/null || echo ERR)
    last_error=$(echo "$adapter" | python3 -c "import sys,json;d=json.load(sys.stdin);print(repr(d.get('data',{}).get('sctp_link',{}).get('last_error','')))" 2>/dev/null || echo "")
  fi

  # log sizes
  app_log_bytes=$(docker exec ransim-e2adapter sh -c "stat -c %s /app/logs/ransim-e2adapter.log 2>/dev/null || echo 0" 2>/dev/null || echo 0)
  json_log_bytes=$(docker inspect ransim-e2adapter --format '{{.LogPath}}' 2>/dev/null | xargs -I{} sudo stat -c %s {} 2>/dev/null || echo 0)
  # json_log 拿不到也沒關係 (sudo 無 cred), 0 表示不可量

  # DU tick state
  du_tick_running=$(curl -sS -m 5 -X POST http://localhost:8102/api/v0.1/DU/Tick/TickController/read -H "Content-Type: application/json" -d '{}' 2>/dev/null \
    | python3 -c "import sys,json;d=json.load(sys.stdin);print(d.get('data',{}).get('is_running'))" 2>/dev/null || echo ERR)

  # adapter CPU/Mem (一次性)
  stats=$(docker stats ransim-e2adapter --no-stream --format "{{.CPUPerc}}|{{.MemUsage}}" 2>/dev/null || echo "ERR|ERR")
  cpu=$(echo "$stats" | cut -d'|' -f1 | tr -d '%')
  mem_str=$(echo "$stats" | cut -d'|' -f2 | awk '{print $1}')

  # 寫 CSV
  echo "$ts,$sample_n,$sctp_connected,$e2_setup_ok,$accepted_rfs,$pdu_sent,$pdu_recv,$last_disc_age_min,$last_error,$app_log_bytes,$json_log_bytes,$du_tick_running,$cpu,$mem_str" >> "$CSV"

  # stdout 顯示一行
  echo "[$ts] #$sample_n connected=$sctp_connected e2=$e2_setup_ok rfs=$accepted_rfs sent=$pdu_sent recv=$pdu_recv last_disc=$last_disc_age_min app_log=${app_log_bytes}B cpu=${cpu}% mem=$mem_str du_tick=$du_tick_running"

  # 最後一筆 sample 不要 sleep
  if [ $sample_n -lt $TOTAL_SAMPLES ]; then
    sleep $INTERVAL_SEC
  fi
done

echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] soak monitor done — $TOTAL_SAMPLES samples written to $CSV"
