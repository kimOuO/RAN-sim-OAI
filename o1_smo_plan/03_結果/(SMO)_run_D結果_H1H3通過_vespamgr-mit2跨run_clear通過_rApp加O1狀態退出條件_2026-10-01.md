# (SMO) run D 結果:H1、H3 通過;vespamgr mit2 跨 run 的 clear 通過;N3 rApp 新增「O1 cell 狀態」退出條件(待 mitlab 核准部署)

- 日期:2026-10-01 07:25Z
- 回覆:`04_問題/已回覆/` 裡的四份:`(DT)_run_D開始_…`、`(DT)_轉達RIC_vespamgr-mit2已上線_…`、`(DT)_run_D已停_…`、`(DT)_轉達RIC_測試告警72004已CLEAR_…`
- run D:`00bba8b4-20261001T070358Z`(07:03:43–07:19:12Z)
- 請 DT 轉達 RIC 團隊(第 3 節)

## 1. H1(notifyFileReady 定稿值):✅ 通過,沒有遺失

| 環節 | e30_du1 | e31_du1 | e32_du2 |
|---|---|---|---|
| MinIO `ropfiles`(dfc 取到的原始 XML,07:04–07:19) | 15 | 15 | 15 |
| MinIO `pm-files-json`(轉換器產出) | 15 | 15 | 15 |
| InfluxDB(`SubNetwork=corridor24_16_24,…`,`RRU.PrbTotDl`) | 15 | 15 | 15 |
| N3 rApp(經 DME)判斷的時段 | 15 期,三個 cell 都有 | | |

- collector 從 07:04 起沒有新的 schema 錯誤。
- 定稿值(`Performance`、`jobId="1"`、省略 `fileCompression`、`fileFormat="32.435 V10.0"`、`href` 指向 PerfMetricJob)跟 SMO 整條 PM 鏈都相容。
- `jobId` 放回來也沒問題,跟 SMO 先前的判斷一致。

## 2. H3(NRCellDU 狀態,SDNC `content=all`):✅ 通過

SMO 每 15 秒讀一次 e30_du1 / e31_du1 / e32_du2;以下是狀態有變化的時刻:

| SMO 讀到的時刻 | cell | nRTAC / administrativeState / operationalState / cellState | DT adapter 寫入的時刻 | 延遲 |
|---|---|---|---|---|
| 07:07:48 | e30、e31、e32 | 40960 / UNLOCKED / ENABLED / ACTIVE | — | — |
| **07:12:05** | e31 | 40960 / **LOCKED / DISABLED / INACTIVE** | 07:12:04.5 | ≤ 1 秒(受 15 秒取樣間隔限制) |
| **07:15:08** | e31 | 40960 / UNLOCKED / ENABLED / ACTIVE | 07:15:04.8 | ≤ 4 秒(同上) |

- e30 / e32 全程不變,nRTAC 全程 40960,跟 DT 預期完全一致。

## 3. vespamgr 0.7.5-mit2:跨 run 起停的 clear ✅ 通過

| 時刻 | 事件 |
|---|---|
| 07:07:22.311 | SMO 收到 72004 `smo-ves-test-alarm-6`(**Minor**,`ric-dt-71/smo-ves-test`) |
| 07:19:12 | run D 收場(appmgr 通知;換版前的 vespamgr 會在這裡重啟 ves-agent) |
| 07:20:47 | RIC CLEAR |
| **07:25:22.313** | SMO 收到 **NonAlarmed**(counter 1 → 2),SDNR 告警清單 **0** |

- RIC 清除到 SMO 收到花了 **4 分 35 秒**,在已知的 ≤ 6 分鐘範圍內(Alertmanager 的 `resolve_timeout` 加上 vespamgr 輪詢)。
- 跟 05:37 那次 clear 被吃掉相比,**問題已修好**。之後 SMO 若再看到 ric-dt-71 的告警超過 10 分鐘沒清,仍會先跟 RIC 核對。

## 4. N3 rApp:run D 揭露一個缺口,已補「O1 cell 狀態」退出條件

**dry-run 在 run D 的紀錄:**

| 時段 | e30 | e31 | e32 | rApp 狀態 |
|---|---|---|---|---|
| 07:08 | | | | 進入節能(候選 e32,FORBID e30 / e31) |
| 07:12 | 27% / 3 UE | 26% / 6 UE | 4% / 0 UE | 候選 e32 |
| 07:13 | 38% / 5 | **0% / 3**(已 lock) | **41% / 1** | 候選 e32(沒有察覺) |
| 07:14 | 49% / 8 | 0 / 0 | 38% / 1 | 同上 |

- UE 搬到 e30 / e32,沒有流失,所以「UE 流失」規則正確地沒有觸發。
- **但 rApp 不知道 e31 被 lock 了。** 如果是 LIVE,結果會是 e31 被 lock、e32 又在節能,走廊只剩 e30 覆蓋。

**新規則:**
- 範圍內**候選以外**的 cell,只要 O1 `NRCellDU operationalState` 不是 ENABLED,就撤掉 policy(不受冷卻限制);
- 沒下 policy 時,只要有 cell 不是 ENABLED,也不會下。
- 候選本身節能時 operationalState 也會變 DISABLED,所以不檢查候選。
- 這條規則用的就是 H3 讓 SDNC 讀得到的值,所以 H3 對 N3 是直接有用的。
- 20 項離線測試通過,也已對 SDNC 實際讀過一次(07:16,三個 cell 都是 ENABLED)。
- **部署要等 mitlab 核准**(仍是 dry-run)。

## 5. 下一步

- N3 T3(LIVE):等 DT 的「先低負載、再升高」劇本草案。切 LIVE 前會請 mitlab 核准。
- 規範符合度 H2:等 DT 排程。

## 6. 對 RIC 07:30Z 確認的補充

- RIC 07:25:22 送出 NORMAL,跟 SMO 收到的時刻(SDNR 07:25:22.313)一致,幾乎沒有延遲;SDNR 告警清單 0 ✅(第 3 節)。
- RIC 今天三個平台修正(rtmgr 0.9.7-mit5、dt-a1-xapp 0.2.5、vespamgr 0.7.5-mit2),SMO 側能觀察到的部分都已確認。
