#!/bin/bash
# B2 從嚴判準的那一刀:在時間軸進到第 4 步(300 秒維運等待)之後重啟 CU。
# 上一輪沒做到,是因為我打算「找空檔手動做」,而那 300 秒在我做別的事時就過完了。
# 這支先掛好、由條件觸發,不靠人盯著。
set -u
echo "[b2] 等待時間軸進入第 4 步…"
while true; do
  STEP=$(docker exec ransim-cu sh -c 'cat /app/tmp/anr_fixture.progress.json 2>/dev/null' \
         | python3 -c 'import sys,json;print(json.load(sys.stdin).get("step",0))' 2>/dev/null || echo 0)
  AGE=$(docker exec ransim-cu sh -c 'cat /app/tmp/anr_fixture.progress.json 2>/dev/null' \
         | python3 -c 'import sys,json,time;print(int(time.time()-json.load(sys.stdin).get("step_started",0)))' 2>/dev/null || echo 0)
  if [ "$STEP" = "5" ] && [ "$AGE" -ge 60 ]; then break; fi
  sleep 5
done
echo "[b2] 第 4 步已過 ${AGE}s → 重啟 CU(這是刻意的一刀)"
date -u +"[b2] 重啟時刻 %H:%M:%S"
docker restart ransim-cu >/dev/null
until docker exec ransim-cu python3 /app/manage.py anr_fixture --status >/dev/null 2>&1; do sleep 3; done
sleep 8
echo "[b2] 重啟後心跳:"
docker exec ransim-cu python3 /app/manage.py anr_fixture --status 2>&1 | grep -E "第 |心跳"
docker exec ransim-cu sh -c 'grep -a "續跑" /app/tmp/fixture_resume.log | tail -2'
