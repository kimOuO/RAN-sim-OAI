# (SMO) N3 rApp **LIVE 就緒**(2026-10-01 12:10:39Z),DT 可以起 T3 run

- 日期:2026-10-01 12:11Z
- 回覆:`04_問題/已回覆/(DT)_mitlab核准_部署rApp最新版並切LIVE_T3時間請SMO回覆_2026-10-01.md`
- 依據:mitlab 10:26Z 核准(經 DT 轉達):部署最新版並切 LIVE 做 T3
- 請 DT 轉達 RIC 團隊

## 1. 版本與時間

| 項目 | 內容 |
|---|---|
| 最新版部署(dry-run 確認) | 12:09:38Z(mitlab 執行);DME 工作已含 NRCellCU / `RRC.ReEstabAtt`,pm-producer 已接受 |
| **切 LIVE** | **12:10:39Z**(SMO 執行 `deploy.sh live`),pod `n3-es-rapp-59b5647f4d-fvg4m`,`LIVE=true` |
| 程式版本 | `rapp.py` cc07cf8a598b、`rapp_logic.py` 18affb511cc3 |
| PMS service | `smo-n3-es-rapp` 註冊 HTTP 201,keep-alive 120 秒(rApp 每 40 秒送一次) |
| policy | ID `smo-n3-corridor`(corridor 劇本)、`smo-n3-livetest`(livetest 劇本),type 30001,ric `ric-dt-71`,`dlPrbUsage` 60、`esPercentage` 30 |

## 2. 切 LIVE 前的檢查(12:10Z)

- PMS:`ric-dt-71` AVAILABLE,有 type 30001 ✅
- PMS 與 RIC-A 上 type 30001 都沒有任何 policy(沒有殘留)✅
- corridor 的 ME 都還沒上線,rApp 是空狀態 ✅

## 3. T3 期間 SMO 會記錄

- rApp:每期的 PRB / UE / 重建次數、CREATE / DELETE 的時刻與原因、PMS 回應碼。
- PMS:policy 狀態(ENFORCED 的時刻),每 30 秒記一次;RIC-A 的 policy 清單。
- O1:e30 / e31 / e32 的 NRCellDU `operationalState`,每 15 秒記一次(預期 e32 進入節能時變 DISABLED)。
- PM:逐分鐘三個 cell 的 UE / PRB,以及 CU-CP 的重建次數。
- SDNR 告警。

## 4. 止損

- 非預期時(例如 policy 一直不撤),SMO 或 mitlab 執行 `deploy.sh dry-run`。rApp 停止時會先刪掉自己的 policy;就算 rApp 異常停止,PMS 也會在 keep-alive 120 秒逾時後自動刪除。
- T3 結束(run 自動停止、rApp 因 ME 斷線撤除)後,SMO 切回 dry-run,並回報 PUT / DELETE 的時刻。

**請 DT 起 T3 run,並通知 runId。**
