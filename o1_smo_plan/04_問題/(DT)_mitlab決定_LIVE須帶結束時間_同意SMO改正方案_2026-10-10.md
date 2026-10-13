# (DT) mitlab 決定:同意 SMO 改正方案 —— LIVE 必須帶結束時間

- 日期:2026-10-10
- 回覆:`03_結果/(SMO)_T3第二場補時刻_未及時切回dry-run事件說明_C20意見_2026-10-10.md` 第 2 節「SMO 的改正」

## 決定

mitlab 同意 SMO 的兩項改正,請 SMO 實作:

1. `deploy.sh live` 必須帶結束時間(例如 `deploy.sh live 45m`);超過時間 rApp 自行刪除 policy 並回到 dry-run,不依賴 SMO 工作階段是否在線。
2. 每次切 LIVE 後,在 `03_結果/` 寫明預定切回時間;DT 若在該時間後仍看到 PMS 有 `smo-n3-es-rapp` 的 service,會提醒 SMO 或 mitlab。

## 尚未決定

- C20(rApp 高負載退出門檻改 ≥ 45%,或加吞吐量條件)與 G14(高負載退出不受 5 分鐘冷卻限制):mitlab 尚在了解中,另行通知。
- A6 / I2 / C19 的 T0:RIC 前提已滿足(磁碟 77%),待 mitlab 定 T0 後,DT 提前 10 分鐘通知。
