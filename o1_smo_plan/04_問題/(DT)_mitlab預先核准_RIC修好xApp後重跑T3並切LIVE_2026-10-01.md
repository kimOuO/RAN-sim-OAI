# (DT) mitlab 預先核准:RIC 修好 dt-a1-xapp 後重跑一場 T3,SMO 屆時可直接 `deploy.sh live`

- 日期:2026-10-01 12:58Z(mitlab 12:57Z 核准)
- 流程:RIC 回報 xApp 修好(含對「有 dlPrbUsage 時 es-on」的驗證)→ DT 通知 SMO 時間 → SMO `deploy.sh live` 並回「就緒」→ DT 起 run(corridor24_16_24、2400 秒、0.2 / 4.0 / 0.2 Mbps)並通知 runId → 結束後 SMO 切回 dry-run。
- 不需要再向 mitlab 請示 LIVE;若 RIC 的修正改變了 policy 內容需求(例如 dlPrbUsage),DT 會先通知。
- RIC session 目前離線,訊息已排隊;DT 收到回覆後立即安排。
