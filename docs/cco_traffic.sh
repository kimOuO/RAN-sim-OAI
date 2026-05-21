#!/usr/bin/env bash
# cco_traffic.sh — CCO 劇本流量產生
#
# 對應 SCENARIO_PLAN.md §4.2
# 目的：造 DU0 PRB ≈ 30~50%、DU1 PRB = 0，差距 ≥ 300,000 PPM
#
# 單 UE 環境下差距天然成立（DU1 沒掛 UE），本劇本只需要把 DU0 的 PRB 拉起來。
# 不需動通道。
#
# Usage: bash cco_traffic.sh {start|stop|status}

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SCENARIO_ID="cco"
LOG_FILE="$STATE_DIR/$SCENARIO_ID.log"

# CCO 劇本參數
DL_RATE="1.5M"        # 1.5 Mbps DL → 預期 PRB ≈ 30~50%（不太極端，留 xApp HO 後反向觀察空間）
DURATION_S="120"      # 撐 2 分鐘，HO 觸發後仍有時間繼續觀察反向

start_scenario() {
  acquire_lock "$SCENARIO_ID"

  if ! precheck; then
    write_status "$SCENARIO_ID" "failed"
    release_lock
    exit 1
  fi

  log "=== CCO 劇本啟動 ==="
  log "  DL: iperf3 -R -b $DL_RATE -t ${DURATION_S}s"
  log "  Log: $LOG_FILE"

  write_status "$SCENARIO_ID" "running"
  : > "$LOG_FILE"

  (
    set -uo pipefail
    iperf3 -c "$EXT_DN_IP" -p "$IPERF_PORT" \
           --bind-dev "$UE_IFACE" \
           -R -b "$DL_RATE" -t "$DURATION_S" -i 10 \
      >> "$LOG_FILE" 2>&1
    iperf_exit=$?
    if [[ $iperf_exit -eq 0 ]]; then
      write_status "$SCENARIO_ID" "done"
      echo "[$(date '+%H:%M:%S')] === CCO 劇本正常結束 ===" >> "$LOG_FILE"
    else
      write_status "$SCENARIO_ID" "failed"
      echo "[$(date '+%H:%M:%S')] === CCO iperf3 退出碼 $iperf_exit ===" >> "$LOG_FILE"
    fi
    clear_state "$SCENARIO_ID"
    release_lock
  ) &
  IPERF_PID=$!
  write_pid "$SCENARIO_ID" "$IPERF_PID"

  log "已啟動，PID=$IPERF_PID"
  log "監看：tail -f $LOG_FILE"
  log "停止：bash $0 stop"
}

stop_scenario() {
  local pid
  pid=$(read_pid "$SCENARIO_ID")
  log "停止 CCO 劇本（PID=$pid）..."
  killall_traffic
  if [[ -n "$pid" ]]; then
    kill_pid_tree "$pid"
  fi
  write_status "$SCENARIO_ID" "stopped"
  clear_state "$SCENARIO_ID"
  release_lock
  log "Stopped"
}

status_scenario() {
  echo "scenario=$SCENARIO_ID"
  echo "status=$(read_status "$SCENARIO_ID")"
  echo "pid=$(read_pid "$SCENARIO_ID")"
  if [[ -f "$STATE_DIR/active.lock" ]]; then
    echo "active_lock=$(cat "$STATE_DIR/active.lock")"
  else
    echo "active_lock=none"
  fi
}

case "${1:-}" in
  start)  start_scenario ;;
  stop)   stop_scenario ;;
  status) status_scenario ;;
  *)
    echo "Usage: $0 {start|stop|status}"
    exit 2
    ;;
esac
