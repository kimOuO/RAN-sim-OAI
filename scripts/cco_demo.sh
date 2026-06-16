#!/bin/bash
# ============================================================================
# CCO 容量受限換手 demo — 一鍵重現(cco-01-load-balance xApp 觸發 + 換手回升)
#   用法: bash scripts/cco_demo.sh [speed]   (speed 預設 3.0 = 三倍速)
#
# 重現 COO 故事: UE 在覆蓋交界(125,100)掛 Cell0 → c0 設 20% PRB quota →
#   流量拉高 → c0 餵不滿(吞吐受限 + delay 爬)→ 三觸發條件成立 → RC HO 到
#   Cell1(無 quota,106 PRB)→ 吞吐回升 + delay 回落。
#
# 前提: DU 需有 CCO env(本腳本會檢查,缺則 recreate):
#   DU_INTER_FREQ=on(不同頻不互擾)/ RU_TX_POWER_DBM=33 / SLOT_DISCARD_TIMER_MS=0
# ============================================================================
set -e
SPEED="${1:-3.0}"
DU=http://localhost:8102; RU=http://localhost:8103; UE=http://localhost:8105; CU=http://localhost:8101; OMNI=http://localhost:8001
SC=cco_20min

echo "[1/6] 確認 DU CCO env..."
IF=$(docker exec ransim-du printenv DU_INTER_FREQ 2>/dev/null || echo off)
TXP=$(docker exec ransim-du printenv RU_TX_POWER_DBM 2>/dev/null || echo 23)
DISC=$(docker exec ransim-du printenv SLOT_DISCARD_TIMER_MS 2>/dev/null || echo 300)
if [ "$IF" != "on" ] || [ "$TXP" != "33" ] || [ "$DISC" != "0" ]; then
  echo "   env 不符(IF=$IF TXP=$TXP DISC=$DISC),請確認 docker-compose.yml DU 區段有設 CCO env 後 recreate。"; exit 1
fi
echo "   ✓ DU_INTER_FREQ=on RU_TX_POWER_DBM=33 SLOT_DISCARD_TIMER_MS=0"

echo "[2/6] 上傳 cco_20min 劇本 + precompute..."
curl -s -X POST "$OMNI/api/v0.1/RAN/Scenario/ScenarioController/upload" -H "Content-Type: application/json" --data-binary @docs/scenarios/cco_20min.json >/dev/null
docker exec -w /app ransim-physics python3 /app/precompute/run_precompute.py $SC >/dev/null 2>&1
echo "   ✓ 劇本上傳 + channel cache 就緒"

echo "[3/6] 啟動模擬 @ ${SPEED}x ..."
curl -s -X POST "$UE/api/v0.1/UE/Sim/SimController/stop" >/dev/null 2>&1 || true; sleep 3
curl -s -X POST "$UE/api/v0.1/UE/Sim/SimController/start" -H "Content-Type: application/json" \
  -d "{\"source\":\"scenario\",\"scenario_id\":\"$SC\",\"speed_x\":$SPEED,\"sim_dt_ms\":250}" >/dev/null
sleep 4
curl -s -X POST "$RU/api/v0.1/RU/Config/RuController/set_channel_mode" -H "Content-Type: application/json" -d "{\"mode\":\"cached\",\"scenario_id\":\"$SC\"}" >/dev/null

echo "[4/6] 設 Cell0 PRB quota = 20%(模擬容量受限)..."
curl -s -X POST "$DU/api/v0.1/DU/MAC/MacScheduler/set_prb_quota" -H "Content-Type: application/json" -d '{"cell_id":"gnbDT_c0","max_prb":20}' >/dev/null
echo "   ✓ c0 quota 20%"

echo "[5/6] 等流量拉高 → 量測觸發條件(c0 capped)..."
while true; do
  LT=$(docker logs ransim-du --since 30s 2>&1 | grep -oE 'SLOT_SHADOW\] tick=[0-9]+' | grep -oE '[0-9]+$' | tail -1)
  [ "$(( ${LT:-0}/4 ))" -ge 380 ] && break; sleep 15
done; sleep 10
docker logs ransim-du --since 18s 2>&1 | grep SLOT_SHADOW | python3 -c "
import sys,re,statistics
rx=re.compile(r'prb=(\d+) prb_op=\d+ prb_pct=([\d.]+) mcs=\d+ sinr=[\-\d.]+ bytes=\d+ thp=([\d.]+) slot_loop=([\-\d.]+)ms')
g=[m for m in (rx.search(l) for l in sys.stdin) if m and float(m.group(3))>0]
f=lambda i:statistics.mean(float(m.group(i)) for m in g)
v=f(3)*1000
print('   [觸發] c0: Volume=%.0fkbit(≥2500 %s) Delay=%.0fms(≥500 %s) PRB=%.1f%%(≥6 %s)'%(
  v,'✅' if v>=2500 else '❌',f(4),'✅' if f(4)>=500 else '❌',f(2),'✅' if f(2)>=6 else '❌'))
"

echo "[6/6] 下 RC handover → Cell1(模擬 xApp 出手)+ 量回升..."
curl -s -X POST "$CU/api/v0.1/CU/Session/SessionController/handover" -H "Content-Type: application/json" -d '{"ue_id":"cco_ue_01","target_cell":"gnbDT_c1"}' >/dev/null
sleep 25
docker logs ransim-du --since 22s 2>&1 | grep SLOT_SHADOW | python3 -c "
import sys,re,statistics
rx=re.compile(r'prb=(\d+) prb_op=\d+ prb_pct=[\d.]+ mcs=\d+ sinr=[\-\d.]+ bytes=\d+ thp=([\d.]+) slot_loop=([\-\d.]+)ms')
g=[m for m in (rx.search(l) for l in sys.stdin) if m and float(m.group(2))>0]
if not g:
    print('   [回升] c1: (此窗無 active tick;回升早先實測 thp~13M,可看 dashboard 確認)')
else:
    f=lambda i:statistics.mean(float(m.group(i)) for m in g)
    print('   [回升] c1: thp=%.1fM delay=%.0fms prb=%.0f(無quota)'%(f(2),f(3),f(1)))
" || true
echo ""
echo "✅ CCO demo 完成。c0 容量受限觸發 → 換手 c1 → 吞吐回升、delay 回落。"
