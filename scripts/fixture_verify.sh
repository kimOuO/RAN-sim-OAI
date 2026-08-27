#!/bin/bash
# 逐題實跑驗收:起場景 → 等一個量測窗 → 檢查病徵是否真的出現在觀測面上。
#
# 為什麼需要:--dry-run 只證明步驟解析得出來,不證明它們產生了病徵。
# 2026-08-27 第 6 題第二輪就是「時間軸跑完但病徵是空的」——
# 劇本看起來完全正確,只有實際觀察指標才會發現。
#
# 用法:bash scripts/fixture_verify.sh <scenario_id> [等待秒數]
set -u
SID="$1"; WAIT="${2:-150}"
cd /home/mitlab/XAPP_DT

curl -s -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/stop \
     -H 'Content-Type: application/json' -d '{}' >/dev/null
docker exec ransim-cu python3 /app/manage.py shell -c "
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.measurement_log import MeasurementLog
from main.apps.cu_cp.models.rlf_event import RlfEvent
for m in (UeContext,HandoverEvent,MeasurementLog,RlfEvent): m.objects.all().delete()
" >/dev/null 2>&1
docker exec ransim-cu rm -f "/app/tmp/fixture_${SID}.log"
curl -s -X POST http://localhost:8001/api/v0.1/RAN/Scenario/ScenarioController/upload \
     -H 'Content-Type: application/json' --data-binary "@docs/scenarios/${SID}.json" >/dev/null
curl -s -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/start \
     -H 'Content-Type: application/json' \
     -d "{\"source\":\"scenario\",\"scenario_id\":\"${SID}\",\"speed_x\":1.0,\"sim_dt_ms\":500}" >/dev/null
echo "=== ${SID} 起場,等 ${WAIT}s ==="
sleep "$WAIT"

echo "--- 時間軸執行紀錄(是否自動觸發)---"
docker exec ransim-cu sh -c "grep -a '\[fixture\]' /app/tmp/fixture_${SID}.log 2>/dev/null | head -12" \
  || echo "  ⚠️ 沒有時間軸日誌 —— 自動觸發沒生效"

echo "--- 關係變更事件(佈病 → xApp 反應的證據)---"
docker exec ransim-cu python3 /app/manage.py shell -c "
from django.utils import timezone
from datetime import timedelta
from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent as CE
w=timezone.now()-timedelta(minutes=6)
rows=list(CE.objects.filter(at__gte=w).order_by('id'))
if not rows: print('    (無 —— xApp 尚未反應,或這題不需要它建關係)')
for e in rows[:12]:
    print('    %s %-16s %s→%s by=%s %s'%(e.at.strftime('%H:%M:%S'),e.action,
      e.source_cell_id,e.target_cgi,e.by,e.detail or ''))
" 2>&1 | grep -E "^    "

echo "--- 觀測面(注意:單段題的病徵會被 xApp 修掉,這裡看到的可能是修復後)---"
curl -s -X POST http://localhost:8101/api/v0.1/CU/E2/Anr/indication \
     -H 'Content-Type: application/json' -d '{"window_min":5}' | python3 -c "
import sys,json
d=json.load(sys.stdin)['data']
k=d['kpmIndication']
print('  UE 分布(依量測來源):')
srcs={}
for r in k['perNeighbourRelation']:
    srcs[r['sourceCellNcgi']]=srcs.get(r['sourceCellNcgi'],0)+ (r.get('measSampleRatePerMin') or 0)
print('   ',{a:round(b,1) for a,b in srcs.items()})
print('  關係:')
print('   %-22s %8s %8s %9s %s'%('關係','嘗試/min','成功率','量測/min','累計失敗'))
for r in sorted(k['perNeighbourRelation'],key=lambda x:(x['sourceCellNcgi'],x['targetCellGlobalId'])):
    print('   %-22s %8.1f %8s %9.1f %s'%(
      r['sourceCellNcgi']+'→'+r['targetCellGlobalId'],r['MM.HoExeAttRatePerMin'],
      r.get('MM.HoExeSuccRatio_last50'),r.get('measSampleRatePerMin') or 0,
      dict(r.get('MM.HoFailCumulativeSinceCreation') or {}) or '{}'))
cl=k['cellLevel']
rlf={a.split('.')[-1]:b.get('currentPerMin') for a,b in cl.items() if 'RRC.ReEstab' in a or 'Rlf' in a}
if rlf: print('  重建/斷線:',rlf)
cap=d['e2NodeInformation'].get('nrtCapacity')
if cap: print('  鄰區表容量:',{'limit':cap.get('limit'),'used':cap.get('used')})
print('  頻率清單:',[f['arfcn'] for f in d['e2NodeInformation'].get('frequencyRelations') or []])
"
