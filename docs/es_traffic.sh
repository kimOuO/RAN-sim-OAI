#!/usr/bin/env bash
# es_traffic.sh — ES 劇本流量產生
#
# 對應 SCENARIO_PLAN.md §4.3
# 目的：
#   trigger 階段（start）：停所有人工流量，等 120s，造 PrbTotDl ≤ 50,000 PPM 持續 120s
#   recover 階段（recover）：iperf3 -b 2M × 60s，模擬流量回升以驗證 xApp 解除 cap
#
# Usage: bash es_traffic.sh {start|recover|stop|status}

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

SCENARIO_ID="es"
LOG_FILE="$STATE_DIR/$SCENARIO_ID.log"

# ES 劇本參數
TRIGGER_WAIT_S="120"     # 低載持續時間（KPM 門檻）
RECOVERY_RATE="2M"       # recovery 階段 iperf3 流量
RECOVERY_DURATION_S="60"

start_scenario() {
  acquire_lock "$SCENARIO_ID"

  log "=== ES 劇本 trigger 階段啟動 ==="
  log "  Step 1: 停所有現有 iperf3 / ping 流量"
  log "  Step 2: 等 ${TRIGGER_WAIT_S}s，期間維持低載"
  log "  Log: $LOG_FILE"

  write_status "$SCENARIO_ID" "running"
  : > "$LOG_FILE"

  # ES 不需要完整 precheck（UE 沒 attached 也算「節能」狀態的一種），但仍提示
  if ! check_ue_iface; then
    warn "UE 介面異常，仍繼續（ES 對 UE 連線無強依賴）"
  fi

  # Step 1: 殺光現有流量
  killall_traffic
  log "已殺光現有 iperf3 / ping process"

  # Step 2: 背景跑等待
  (
    set -uo pipefail
    echo "[$(date '+%H:%M:%S')] trigger 等待 ${TRIGGER_WAIT_S}s ..." >> "$LOG_FILE"
    sleep "$TRIGGER_WAIT_S"
    echo "[$(date '+%H:%M:%S')] trigger 完成，KPM 應達低載門檻" >> "$LOG_FILE"
    write_status "$SCENARIO_ID" "trigger_complete"
    clear_state "$SCENARIO_ID"
    # lock 此時不釋放，等 recover 跑完 / stop 才釋放
    # 若 backend 不跑 recover，要主動 stop 釋放
  ) &
  WAIT_PID=$!
  write_pid "$SCENARIO_ID" "$WAIT_PID"

  log "已啟動，PID=$WAIT_PID"
  log "${TRIGGER_WAIT_S}s 後 status 變 trigger_complete"
  log "Recovery：bash $0 recover"
  log "結束：bash $0 stop"
}

recover_scenario() {
  # 不需要再 acquire_lock，但需要驗證 lock 已是 es
  if [[ ! -f "$LOCK_FILE" ]] || [[ "$(cat "$LOCK_FILE")" != "$SCENARIO_ID" ]]; then
    err "Recovery 前必須先 start trigger（沒有 ES lock）"
    exit 1
  fi

  if ! precheck; then
    write_status "$SCENARIO_ID" "failed"
    release_lock
    exit 1
  fi

  log "=== ES 劇本 recovery 階段啟動 ==="
  log "  iperf3 -R -b $RECOVERY_RATE -t ${RECOVERY_DURATION_S}s"

  write_status "$SCENARIO_ID" "recovering"

  (
    set -uo pipefail
    iperf3 -c "$EXT_DN_IP" -p "$IPERF_PORT" \
           --bind-dev "$UE_IFACE" \
           -R -b "$RECOVERY_RATE" -t "$RECOVERY_DURATION_S" -i 10 \
      >> "$LOG_FILE" 2>&1
    iperf_exit=$?
    if [[ $iperf_exit -eq 0 ]]; then
      write_status "$SCENARIO_ID" "done"
      echo "[$(date '+%H:%M:%S')] === ES recovery 正常結束 ===" >> "$LOG_FILE"
    else
      write_status "$SCENARIO_ID" "failed"
      echo "[$(date '+%H:%M:%S')] === ES recovery iperf3 退出碼 $iperf_exit ===" >> "$LOG_FILE"
    fi
    clear_state "$SCENARIO_ID"
    release_lock
  ) &
  IPERF_PID=$!
  write_pid "$SCENARIO_ID" "$IPERF_PID"

  log "Recovery 已啟動，PID=$IPERF_PID"
}

stop_scenario() {
  local pid
  pid=$(read_pid "$SCENARIO_ID")
  log "停止 ES 劇本（PID=$pid）..."
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
  start)   start_scenario ;;
  recover) recover_scenario ;;
  stop)    stop_scenario ;;
  status)  status_scenario ;;
  *)
    echo "Usage: $0 {start|recover|stop|status}"
    exit 2
    ;;
esac
