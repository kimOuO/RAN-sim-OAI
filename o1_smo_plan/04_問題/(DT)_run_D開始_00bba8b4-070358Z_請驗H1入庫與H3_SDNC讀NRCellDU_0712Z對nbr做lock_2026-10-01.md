# (DT) run D 開始:`00bba8b4-20261001T070358Z`;請驗 H1(入庫)與 H3(SDNC 讀 NRCellDU);07:12–07:15Z DT 對 e31 nbr 做一次 lock

- 日期:2026-10-01 07:08Z
- run:corridor24_16_24,seed 16,07:03:43Z 起 900 秒 → 約 07:19Z 停;PM 60 秒;adapter 映像含 H1 定稿 + H3(patch 0009)
- H1 定稿:`fileDataType="Performance"`、`jobId="1"`、省略 `fileCompression`、`fileFormat="32.435 V10.0"`、`href=/ManagedElement=<me>/PerfMetricJob=ManagedElement=<me>`

## H3 預期值(SDNC RESTCONF 讀 `NRCellDU` attributes,`content=all`;operationalState / cellState 在 operational datastore)
| 時段 | nRTAC | administrativeState | operationalState | cellState |
|---|---|---|---|---|
| 07:05–07:12(正常) | 40960 | UNLOCKED | ENABLED | ACTIVE |
| **07:12:00–07:15:00(DT 對 e31 nbr 硬鎖:DU cell disable)** | 40960 | **LOCKED** | **DISABLED** | **INACTIVE** |
| 07:15 之後(解鎖) | 40960 | UNLOCKED | ENABLED | ACTIVE |
e30 / e32 全程 UNLOCKED / ENABLED / ACTIVE。狀態變化由 facade 每秒輪詢 → adapter 偵測到變更即 `netconf_data_update_nrcelldu` 重寫,延遲 ≤ 數秒。
(節能 es-on 的情況 administrativeState 會維持 UNLOCKED、只有 operationalState=DISABLED,這場不測。)

請把 SDNC 讀到的值與時間放 `03_結果/`。
