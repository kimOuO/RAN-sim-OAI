# (DT) 轉達 RIC:rtmgr mit5 驗證通過(同劇本連跑兩場);vespamgr 補丁 mitlab 已核准、建置中

- 日期:2026-10-01 06:48Z

## 1. mit5 驗證(DT 連跑兩場 corridor24_16_24)
| 場 | runId | 時間 | 劇本 xApp a6 / k5 ClusterIP | 推送 |
|---|---|---|---|---|
| A | `00bba8b4-20261001T061609Z` | 06:15:55–06:29:41Z | 10.100.76.165 / 10.110.195.130 | 40/40、42/42 成功 |
| B | `00bba8b4-20261001T063157Z` | 06:31:41–06:45:14Z | **10.100.151.228 / 10.105.185.139(同名重建、IP 已換)** | 首次 successful 06:31:45(AddEndpoint 後 1 秒);30/30、30/30 成功、0 重開、0 失敗;**8101 未舉** |
對照 run 13(今日 05:10 那場):0 成功 / 108 次重開 / 8101 ×2。結論:同名 Service 重建的情況 mit5 已涵蓋;現役 rtmgr 0.9.7-mit5。兩場三 node 的 E2 indication 1/s 正常;O1 PM 照常。

## 2. 8101 clear
RIC 06:31:57Z 補送兩筆 NORMAL(collector 202 ×2);SMO 第 5 節已確認 SDNR 歸 0 ✅。

## 3. 根治
vespamgr 0.7.5-mit2(xApp 通知後設定不變就不重啟 ves-agent)**mitlab 已核准,RIC 建置中**;換版那一刻 ves-agent 會重啟一次(eventId 序號再重算一次),之後穩定。換版時 RIC 會通知,請 SMO 屆時留意一次心跳序號歸 1。

## 4. 接下來
DT 06:47Z 起一場 15 分鐘 run(seed 15)實測 H1(notifyFileReady 新值)與 H3(NRCellDU nRTAC / administrativeState / operationalState / cellState);runId 另檔通知,並請 SMO 從 SDNC 讀 NRCellDU 核對。
