# (DT) mitlab 核准:① 部署 rApp 最新版;② `deploy.sh live` 做 T3;請 SMO 回覆 LIVE 就緒時間,DT 隨即起 run

- 日期:2026-10-01 10:27Z(mitlab 10:26Z 核准)
1. 請 SMO 部署 rApp 最新版(逐 cell、O1 狀態退出、UE 流失、RRC 重建相對基準),先 dry-run 確認啟動正常。
2. 接著 `deploy.sh live`,並在 `03_結果/` 回覆版本、時間與「LIVE 就緒」。
3. DT 收到就緒後起 T3 run:corridor24_16_24、2400 秒、PM 60 秒;run 起後 60 秒啟動 `t3_load.py '[[0,0.2],[900,4.0],[1800,0.2]]'`;runId 與各階段時刻另檔通知,RIC 同步。
4. T3 結束(run 自動停、rApp 因 ME 斷線撤除)後,請 SMO 切回 dry-run 並回報 policy 的 PUT / DELETE 時刻。
5. 驗收點照 `01_計畫/(DT)_N3_T3劇本草案_…` 第 3 節。若 LIVE 中出現非預期(例如 policy 一直不撤、告警殘留),DT 會停 run 並通知,SMO 可隨時 `deploy.sh dry-run` 止損。
