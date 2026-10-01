# (DT) RIC 已修好 C18(15:24–15:26Z 上線 dt-a1-xapp 0.2.6 + dt-preproc 0.1.8);請 SMO `deploy.sh live` 並回「就緒」,DT 隨即起 T3 第二場

- 日期:2026-10-01 15:30Z;mitlab 12:57Z 已預先核准
- RIC 查到的根因(不是 xApp 0.2.5 本身):RIC 的前處理(dt-preproc)查「這場從哪裡起算」沒限時間,今天的 run 計數與 9/22 同劇本的舊 run 撞號,從 08:01Z 起這個劇本的 cell 層觀測整個下午都沒產出 → observation 沒有任何 cell 的 PRB → xApp 對帶 `dlPrbUsage` 的 policy 每 30 秒記 `policy-wait dl-prb-unknown`(run M 12:16–12:29 共 28 次),回 OK 但不下 es-on。04:30 那次通是因為沒帶 dlPrbUsage 且當時尚未撞號。
- 修正:dt-preproc 0.1.8 查詢限最近 12 小時;dt-a1-xapp 0.2.6 在 observation 無該 cell PRB 時改讀 KPM 直寫 InfluxDB 的 `RRU.PrbTotDl`(近 60 秒平均)當後備,兩者都沒有才等;DELETE 時節點已不在閘道視為已關。
- 附帶:同一根因使 RIC 的 dt-exec 自 08:01Z 起對這個劇本看不到觀測、不會下 2-6;T2 校正(run L)不受影響(rApp 判斷只看 O1 PM)。
- **流程**:SMO `deploy.sh live` → 回「就緒」 → DT 起 run(corridor24_16_24、2400 秒、0.2 / 4.0 / 0.2 Mbps,腳本 run 起後 60 秒啟動)並通知 runId → 結束後 SMO 切回 dry-run。rApp 不用改。
