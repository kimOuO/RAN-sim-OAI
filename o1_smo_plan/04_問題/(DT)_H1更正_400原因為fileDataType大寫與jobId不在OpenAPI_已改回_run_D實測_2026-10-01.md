# (DT) H1 更正:400 的原因是 `fileDataType` 大寫與 `jobId` 不在 Rel-18 OpenAPI;已改回,run C 結束後起 run D 實測

- 日期:2026-10-01 06:57Z
- 原因(已對照 `TS28532_FileDataReportingMnS.yaml` Rel-18):FileInfo 的 `fileDataType` enum 是 **`Performance` / Trace / Analytics / Proprietary**(stage-2 文字寫 PERFORMANCE,OpenAPI 用首字大寫);FileInfo **沒有 `jobId`**。collector 依 OpenAPI 驗 stndDefined,所以回 400。DT 盤點時以 stage-2 文字為準,是 DT 的錯。
- 修正:`fileDataType` 改回 `Performance`、移除 `jobId`;保留 `fileCompression` 省略、`fileFormat="32.435 V10.0"`、`href` 指 PerfMetricJob(這三項都在 OpenAPI 允許範圍)。
- run C(`00bba8b4-20261001T064643Z`)約 07:01Z 自動停;PM 檔有產出但通知全部 400,**這場的 PM 不會入庫,請 SMO 忽略**。之後立即起 run D(seed 16,15 分鐘)實測 H1 + H3,runId 另檔通知。
- 若 SMO 已抓到 collector 400 原文,仍請放 `03_結果/` 供對照。
