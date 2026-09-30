# (DT) mitlab 的三項決定:自動化計畫可開始、本 run 不手動補做、三個計數器停止上報

- 日期:2026-09-30 08:15Z
- 來自:DT 端(10.3.0.217),轉述 mitlab 在 DT 這邊的指示
- 接續:`04_問題/(DT)_回覆PM-V1通過_殘留告警已補清_與D1-D8_2026-09-30.md`

## 1. mitlab 的決定

| # | 事項 | 決定 |
|---|---|---|
| 1 | `01_計畫/(SMO)_ME生命週期自動化計畫_2026-09-30.md` | **可以開始做** |
| 2 | 本 run(00bba8b4)的 PMS 歸屬、NCMP 登記、TEIV 連線關係 | **不手動補做** |
| 3 | 三個固定為 0 的計數器(`DRB.UeUnresVolDl`、`DRB.UeUnresVolUl`、`DRB.RlcPacketDropRateDl`) | **停止上報** |

說明:以上是 mitlab 對 DT 端下的指示,DT 據此開始做自己這一側的工作。計畫第 5 節 SMO 端需要的權限(Kafka 帳號、讀 SDNC 帳密的 secret、呼叫 SDNC / NCMP / PMS),仍請 SMO 端直接向 mitlab 取得,DT 不代為授權。

## 2. DT 端已完成的準備(下一個 run 起生效)

以下程式都已改好,**在本 run 結束(08:29:32Z)並重啟編排服務後生效**,本 run 不受影響。

| 項目 | 內容 |
|---|---|
| D2 四個欄位 | 每個 run 起的 ME,`pnfRegistration` 的 `additionalFields` 會多帶 `scenarioId`(例 `corridor24_16_24`)、`runId`(例 `00bba8b4`)、`role`(`CU-CP` / `DU`)、`lifecycle`(`ephemeral`)。常駐的 e00 不帶這四個欄位。 |
| 預設量測 10 → 7 | 預設 PerfMetricJob 只剩 `DRB.MeanActiveUeDl/Ul`、`DRB.MaxActiveUeDl/Ul`、`DRB.UEThpDl/Ul`、`RRU.PrbTotDl`。下一個 run 的 XML 每個 measValue 是 7 個值,InfluxDB 會少三個欄位,屬預期。這三個仍留在 SupportedPerfMetricGroups,經 CM 寫入還是選得到(值為 0)。 |
| 收工順序 | 先停 o1-adapter → 送 CLEAR → 停其餘容器,避免再留下 `internalConnectionLoss`。 |

常駐的 e00 目前仍是舊映像(10 個計數器)。它重建時 NETCONF 會短暫中斷並重新註冊,DT 會在下一個 run 開始前一併重建,屆時另行通知。

## 3. 等 SMO 提供

| # | 事項 |
|---|---|
| 1 | D3 `notifyMOIDeletion` 的 `schemaReference` 寫法與範例(SMO 說會先測 VES collector 再放 `02_測試/`)。收到後 DT 加進收工流程。 |
| 2 | D3 的順序問題:DT 的順序會是「關 NETCONF → CLEAR → `notifyMOIDeletion`」,請確認控制器可接受。 |
| 3 | c9ad0776 的 6 筆補清(07:52Z)後,告警清單是否歸 0。 |
| 4 | 控制器「只記錄不動作」模式何時上線,DT 好安排對應的 run。 |
