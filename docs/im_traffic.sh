#!/usr/bin/env bash
# im_traffic.sh — IM 劇本流量產生
#
# 對應 SCENARIO_PLAN.md §4.1
# 目的：造 PrbTotDl ≥ 500,000 PPM、UEThpDl ≤ 1 Mbps、RlcSduDelayDl ≥ 50 ms（30s 持續）
#
# 本腳本只負責流量；通道惡化（noise_power_dB +12 dB）由 RAN_controller backend 在
# scenario start 前透過 ChannelController.set_noise_power 下達。
#
# Usage: bash im_traffic.sh {start|stop|status}

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SCENARIO_ID="im"
LOG_FILE="$STATE_DIR/$SCENARIO_ID.log"

# IM 劇本參數
DL_RATE="3M"          # iperf3 -b 3 Mbps DL（超過預期 channel capacity，讓 PRB 滿載）
DURATION_S="90"       # 撐 90s 給 xApp 偵測 + (2,6) cap + 觀察
UL_PING_PARALLEL="3"  # 3 條並行 ping 上行
UL_PING_PAYLOAD="1400"
UL_PING_INTERVAL="0.05"  # 0.05s = 20 pps × 1400 B = 28 KB/s × 3 = 84 KB/s UL

start_scenario() {
  acquire_lock "$SCENARIO_ID"

  if ! precheck; then
    write_status "$SCENARIO_ID" "failed"
    release_lock
    exit 1
  fi

  log "=== IM 劇本啟動 ==="
  log "  DL: iperf3 -R -b $DL_RATE -t ${DURATION_S}s"
  log "  UL: $UL_PING_PARALLEL × ping ($UL_PING_PAYLOAD B / $UL_PING_INTERVAL s)"
  log "  Log: $LOG_FILE"

  write_status "$SCENARIO_ID" "running"
  : > "$LOG_FILE"

  # 啟動背景 iperf3 client（reverse mode = DL）
  (
    set -uo pipefail
    iperf3 -c "$EXT_DN_IP" -p "$IPERF_PORT" \
           --bind-dev "$UE_IFACE" \
           -R -b "$DL_RATE" -t "$DURATION_S" -i 5 \
      >> "$LOG_FILE" 2>&1
    iperf_exit=$?
    # iperf 結束後 kill 所有 UL ping
    killall_traffic
    if [[ $iperf_exit -eq 0 ]]; then
      write_status "$SCENARIO_ID" "done"
      echo "[$(date '+%H:%M:%S')] === IM 劇本正常結束 ===" >> "$LOG_FILE"
    else
      write_status "$SCENARIO_ID" "failed"
      echo "[$(date '+%H:%M:%S')] === IM iperf3 退出碼 $iperf_exit ===" >> "$LOG_FILE"
    fi
    clear_state "$SCENARIO_ID"
    release_lock
  ) &
  IPERF_PID=$!
  write_pid "$SCENARIO_ID" "$IPERF_PID"

  # 啟動背景 UL ping 噪聲（3 條並行）
  for i in $(seq 1 "$UL_PING_PARALLEL"); do
    ping -I "$UE_IFACE" -i "$UL_PING_INTERVAL" -s "$UL_PING_PAYLOAD" \
         "$EXT_DN_IP" >> "$LOG_FILE" 2>&1 &
  done

  log "已啟動，PID=$IPERF_PID"
  log "監看：tail -f $LOG_FILE"
  log "停止：bash $0 stop"
}

stop_scenario() {
  local pid
  pid=$(read_pid "$SCENARIO_ID")
  log "停止 IM 劇本（PID=$pid）..."
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
