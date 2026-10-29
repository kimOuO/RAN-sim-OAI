#!/usr/bin/env bash
# P0 資料面 PoC:對一個測試場景依序跑 UDP 與 TCP 下行 iperf3,每組測試期間 shaper 同時運作。
#
# 前提:
#   1. 已執行 sudo ./setup_netns.sh
#   2. DT 測試 run 已啟動、1x 速度,且 UE_ID 的 traffic profile 是 full-buffer(CBR 高於容量)
#
# 用法:sudo UE_ID=<UE> SCENARIO=s1_center ./run_poc.sh
# 產出:out/<SCENARIO>_<時間>/{shaper_udp.csv, iperf_udp.json, shaper_tcp.csv, iperf_tcp.json}
set -euo pipefail

: "${UE_ID:?需要 UE_ID(DT 裡被鏡像的 UE)}"
SCENARIO=${SCENARIO:-adhoc}
DURATION=${DURATION:-60}
UDP_BW=${UDP_BW:-1G}            # UDP 送出速率,必須高於 DT 容量,才量得到上限
AIR_DELAY_MS=${AIR_DELAY_MS:-0}
CU_URL=${CU_URL:-http://localhost:8101}
SHAPE_UL=${SHAPE_UL:-0}         # 1 = 上行也依 DT 整形(劇本上行需求須 > 0,否則 ACK 會被擋)
UE_NS=${UE_NS:-dtpoc-ue1}
DN_NS=${DN_NS:-dtpoc-dn}
DN_ADDR=${DN_ADDR:-10.250.0.2}

HERE=$(cd "$(dirname "$0")" && pwd)
OUT="$HERE/out/${SCENARIO}_$(date +%Y%m%d_%H%M%S)"

if [[ $EUID -ne 0 ]]; then echo "需要 root:sudo $0" >&2; exit 1; fi
command -v iperf3 >/dev/null || { echo "缺少 iperf3:sudo apt install iperf3" >&2; exit 1; }
for ns in "$UE_NS" "$DN_NS"; do
  ip netns list | grep -qw "$ns" || { echo "netns $ns 不存在,先執行 setup_netns.sh" >&2; exit 1; }
done
mkdir -p "$OUT"

SERVER_PID=""; SHAPER_PID=""
cleanup() {
  [[ -n "$SHAPER_PID" ]] && kill "$SHAPER_PID" 2>/dev/null && wait "$SHAPER_PID" 2>/dev/null || true
  [[ -n "$SERVER_PID" ]] && kill "$SERVER_PID" 2>/dev/null || true
  # 測完把連線恢復成不限速,不留 DT 最後一次的整形值
  ip netns exec "$DN_NS" tc class change dev veth-dn parent 1: classid 1:10 htb rate 1000mbit ceil 1000mbit 2>/dev/null || true
  ip netns exec "$UE_NS" tc class change dev veth-ue parent 1: classid 1:10 htb rate 1000mbit ceil 1000mbit 2>/dev/null || true
  # 產出檔案交回呼叫 sudo 的使用者
  [[ -n "${SUDO_USER:-}" ]] && chown -R "$SUDO_USER": "$HERE/out" || true
}
trap cleanup EXIT

ip netns exec "$DN_NS" iperf3 -s -B "$DN_ADDR" >/dev/null 2>&1 &
SERVER_PID=$!
sleep 1

run_one() {   # $1 = udp | tcp
  local kind=$1
  python3 "$HERE/shaper.py" --ue-id "$UE_ID" --cu-url "$CU_URL" --air-delay-ms "$AIR_DELAY_MS" \
    --ue-ns "$UE_NS" --dn-ns "$DN_NS" --csv "$OUT/shaper_${kind}.csv" \
    $([[ $SHAPE_UL == 1 ]] && echo --shape-ul) &
  SHAPER_PID=$!
  sleep 3   # 等 shaper 拿到第一筆量測並套上整形
  local opts=(-c "$DN_ADDR" -R -t "$DURATION" --interval 0.1 -J)
  [[ $kind == udp ]] && opts+=(-u -b "$UDP_BW")
  echo "[$SCENARIO] $kind 下行 ${DURATION}s ..."
  date +%s.%N > "$OUT/iperf_${kind}.start"   # iperf3 JSON 的 timesecs 只到整秒,另存精確起點給 compare.py
  ip netns exec "$UE_NS" iperf3 "${opts[@]}" > "$OUT/iperf_${kind}.json" || echo "iperf3 $kind 失敗" >&2
  kill "$SHAPER_PID"; wait "$SHAPER_PID" 2>/dev/null || true; SHAPER_PID=""
  sleep 5   # 讓佇列排空,兩組測試互不影響
}

run_one udp
run_one tcp
echo "完成:$OUT"
echo "比對:python3 $HERE/compare.py $OUT"
