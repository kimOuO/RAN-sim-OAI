#!/bin/bash
# 對接輪之間的標準重置。順序是本體:
#   1. 先停 sim —— UE 停止移動與掉線,世界靜止
#   2. 才清狀態 —— 包含解 barred。第八輪作廢的原因就是順序反了:
#      解 barred 時舊場還在動,UE 立刻重建進剛解禁的 cell,
#      殘率灌進 60 秒聚合窗,下一輪的供料窗 assert 要多等一輪排空,
#      而排空期間的世界又不是靜止的。
#   3. 殺時間軸行程、清鎖與進度
#   4. (由呼叫者)上傳劇本、起場 —— 佈病由時間軸自動
# 用法:bash scripts/round_reset.sh <scenario_id>
set -u
SID="$1"
cd /home/mitlab/XAPP_DT

# 1. 停 sim(先讓世界靜止)
curl -s -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/stop \
     -H 'Content-Type: application/json' -d '{}' >/dev/null
sleep 3   # tick 停穩

# 2. 清狀態(世界已靜止,解 barred 不會觸發重建)
docker exec ransim-cu python3 /app/manage.py shell -c "
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation
from main.apps.cu_cp.models.handover_event import HandoverEvent
from main.apps.cu_cp.models.rlf_event import RlfEvent
from main.apps.cu_cp.models.nr_relation_change_event import NrRelationChangeEvent
from main.apps.cu_cp.models.ue_context import UeContext
from main.apps.cu_cp.models.cell_config import CellConfig
for m in (NrCellRelation,HandoverEvent,RlfEvent,NrRelationChangeEvent,UeContext):
    m.objects.all().delete()
CellConfig.objects.update(is_barred=False)
" >/dev/null 2>&1

# 3. 殺時間軸 + 清鎖
docker exec ransim-cu python3 -c "
import os,glob,signal
me=os.getpid()
for p in glob.glob('/proc/[0-9]*/cmdline'):
    try:
        pid=int(p.split('/')[2])
        if pid==me: continue
        if 'anr_fixture' in open(p,'rb').read().decode(errors='ignore'):
            os.kill(pid,signal.SIGKILL)
    except (OSError,ValueError): pass" 2>/dev/null
docker exec ransim-cu sh -c "rm -f /app/tmp/fixture_barred.json /app/tmp/anr_fixture.lock /app/tmp/anr_fixture.progress.json /app/tmp/anr_fixture.current /app/tmp/anr_fixture.heartbeat /app/tmp/fixture_${SID}.log /app/tmp/ho_force_fail.txt"

# 3.5 清後靜默驗證(RIC 第九十輪選項):relations=0 且量測聚合排空才起新場。
#     停 sim 後舊 UE 的最後幾筆量測還在管線/聚合窗裡 —— 過渡窗會讓對方的
#     unknown 候選在「清步」就開錶(合法但錨飄)。靜默確認後,錨穩定在新場首快照。
#     第九十一輪追加:光「等」不夠 —— xApp 拿上一輪 60s 聚合窗的餘料會在清後
#     持續回寫 ADD(06:55 實錄:清完 8 條又長回來,含 n03→unk,新輪出生即死)。
#     改成「掃 + 等」:每輪把關係掃掉,要求連續 90s(> 60s 窗)無新關係且量測
#     排空,對手的記憶確定吐完才起場。
echo "靜默驗證中…(掃+等,需連續 90s 乾淨)"
STREAK=0
for i in $(seq 1 40); do
  QUIET=$(docker exec ransim-cu python3 /app/manage.py shell -c "
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as NR
n=NR.objects.count(); NR.objects.all().delete()
import json,urllib.request
req=urllib.request.Request('http://localhost:8000/api/v0.1/CU/E2/Anr/indication',
    data=json.dumps({'window_min':1}).encode(),headers={'Content-Type':'application/json'})
try:
    d=json.load(urllib.request.urlopen(req,timeout=8))['data']
    meas=sum((a.get('sampleRatePerMin') or 0) for a in d['e2MessageCopyAggregate']['measurementReportAggregate'])
except Exception: meas=0
print('CLEAN' if n==0 and meas<1 else 'DIRTY rels=%d meas=%.0f'%(n,meas))" 2>/dev/null | grep -E "CLEAN|DIRTY" | tail -1)
  if [ "$QUIET" = "CLEAN" ]; then STREAK=$((STREAK+1)); else STREAK=0; fi
  [ "$STREAK" -ge 6 ] && break
  sleep 15
done
echo "靜默:$QUIET(嘗試 $i 次,連續乾淨 ${STREAK}×15s)"

# 3.7 barred 與場同生:起場前預埋 fixture barred 檔(來源=劇本 enforce.barred)。
#     第九十一輪教訓:barred 由時間軸在 T0+數十秒才設,T0→④ 的空窗一筆合法
#     reestab→unk 就把考點資格永久取消(missing ADD 讓 pci 進 related_pa)。
#     禁閉屬性必須在場出生前就在,病(關係/斷鏈)仍由時間軸在 ④ 佈。
BARRED=$(python3 -c "
import json;d=json.load(open('docs/scenarios/${SID}.json'))
print(json.dumps((d.get('anr_fixture') or {}).get('enforce',{}).get('barred',[])))" 2>/dev/null)
if [ -n "$BARRED" ] && [ "$BARRED" != "[]" ]; then
  docker exec ransim-cu sh -c "printf '%s' '$BARRED' > /app/tmp/fixture_barred.json"
  echo "預埋 barred 檔:$BARRED(與場同生)"
fi

# 3.8 結構與場同生(Q9 四輪教訓,泛化 Q4 的 barred 同生原則):
#     劇本 anr_fixture.pre = {env:{...}, relations:[{src,tgt,age_sec,set{}}...]}
#     在起場前寫進 env_override 與 NRT —— 量測流起點晚於一切結構,
#     對方任何 watch 無從在 ④ 前開錶(「不跟 persist 賽跑,直接不給賽道」)。
#     env 每輪 replace(空則清),殘留覆寫不跨輪。
PRE=$(python3 -c "
import json;d=json.load(open('docs/scenarios/${SID}.json'))
pre=(d.get('anr_fixture') or {}).get('pre') or {}
if pre:
    # cells 自動從劇本 gnbs 導出 —— CellConfig 與場同生(見下方註解)
    pre['cells']=[{'cell_id':c['cell_id'],'pci':c['pci'],
                   'frequency_ghz':g.get('frequency_ghz',3.5),
                   'bandwidth_mhz':g.get('bandwidth_mhz',40.0)}
                  for g in d.get('gnbs',[]) for c in g.get('cells',[])]
print(json.dumps(pre))")
docker exec ransim-cu python3 /app/manage.py shell -c "
import json
pre=json.loads('''${PRE}''')
from main.utils.env_loader import set_overrides
set_overrides(dict(pre.get('env') or {}), replace=True)
from main.apps.cu_cp.models.nr_cell_relation import NrCellRelation as NR
from main.apps.cu_cp.services.common.timestamp_service import TimestampService
from datetime import timedelta
now=TimestampService.now()
# CellConfig 也與場同生:pre 關係若指向「DU 尚未註冊」的 cell,scene-apply 的
# ANR seed stale 清掃會把它們當殭屍掃掉(Q9 五輪實錄:pads 註冊最晚→關係被掃
# →不滿載→unknown T0+31s 合法打穿)。起場前把劇本所有 cell 先 upsert 進
# CellConfig,清掃從第一刻起就認得全員。
cells=pre.get('cells') or []
from main.apps.cu_cp.models.cell_config import CellConfig as CC
from main.apps.cu_cp.services.common.uuid_service import UUIDService
for c in cells:
    row=CC.objects.filter(cell_id=c['cell_id']).first()
    if row is None:
        CC.objects.create(cell_id=c['cell_id'],cell_uuid=UUIDService.random_uuid(),
            pci=int(c['pci']),frequency_ghz=float(c.get('frequency_ghz') or 3.5),
            bandwidth_mhz=float(c.get('bandwidth_mhz') or 40.0),is_active=True)
    else:
        CC.objects.filter(pk=row.pk).update(pci=int(c['pci']),is_active=True)
print('cells pre',len(cells))
for r in (pre.get('relations') or []):
    age=float(r.get('age_sec') or 0)
    f=dict(r.get('set') or {})
    NR.objects.get_or_create(source_cell_id=r['src'],target_cgi=r['tgt'],
        defaults=dict(target_pci=int(r.get('pci') or 0),target_arfcn=int(r.get('arfcn') or 633333),
            target_rat='NR',xn_x2_established=True,
            created_at=now-timedelta(seconds=age),updated_at=now,**f))
print('pre applied', len(pre.get('relations') or []))
" 2>/dev/null | grep -a "pre applied" || true

# 4. 上傳 + 起場
curl -s -X POST http://localhost:8001/api/v0.1/RAN/Scenario/ScenarioController/upload \
     -H 'Content-Type: application/json' --data-binary "@docs/scenarios/${SID}.json" >/dev/null
curl -s -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/start \
     -H 'Content-Type: application/json' \
     -d "{\"source\":\"scenario\",\"scenario_id\":\"${SID}\",\"speed_x\":1.0,\"sim_dt_ms\":500}" >/dev/null
date -u +"${SID} T0 = %H:%M:%S(round_reset:停→清→殺→起)"
