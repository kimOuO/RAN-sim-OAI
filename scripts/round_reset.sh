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
docker exec ransim-cu sh -c "rm -f /app/tmp/fixture_barred.json /app/tmp/anr_fixture.lock /app/tmp/anr_fixture.progress.json /app/tmp/fixture_${SID}.log /app/tmp/ho_force_fail.txt"

# 4. 上傳 + 起場
curl -s -X POST http://localhost:8001/api/v0.1/RAN/Scenario/ScenarioController/upload \
     -H 'Content-Type: application/json' --data-binary "@docs/scenarios/${SID}.json" >/dev/null
curl -s -X POST http://localhost:8105/api/v0.1/UE/Sim/SimController/start \
     -H 'Content-Type: application/json' \
     -d "{\"source\":\"scenario\",\"scenario_id\":\"${SID}\",\"speed_x\":1.0,\"sim_dt_ms\":500}" >/dev/null
date -u +"${SID} T0 = %H:%M:%S(round_reset:停→清→殺→起)"
