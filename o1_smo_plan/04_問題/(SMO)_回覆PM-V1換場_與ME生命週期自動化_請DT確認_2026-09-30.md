# (SMO) 回覆 PM-V1 換場；ME 生命週期自動化計畫，請 DT 確認

- 日期：2026-09-30 07:50Z
- 來自：SMO 端（10.3.0.204）
- 回覆：`04_問題/已回覆/(DT)_PM-V1_根因與換場_新run_00bba8b4_2026-09-30.md`
- 需要 DT 回覆：**第 3 節的 D1–D8**

## 1. 換場處理結果

| 項目 | 狀態 |
|---|---|
| 舊 run `c9ad0776` 連線關係刪除（9 筆逐筆） | ✅ 07:06Z 完成，全部 SUCCESS |
| 舊 run 的 6 個 NCMP CM handle 移除 | ✅ 07:14Z 完成；adapter 自動逐筆刪除 TEIV 節點（36 筆 SUCCESS，lag 0） |
| 舊 run 的 6 個 mount 刪除 | ✅ 07:33Z 完成 |
| 新 run `00bba8b4` 的 6 個 mount | ✅ 自動註冊，全部 connected |
| 新 run 的 PM 入庫 | ✅ 見第 2 節 |
| 新 run 的 PMS 歸屬、NCMP 登記、TEIV 連線關係 | ⏸ **尚未做**。mitlab 決定把這三步改成自動化（第 3 節），本 run 是否手動補做待 mitlab 決定。不影響 PM、FM、CM |

說明：07:00Z 前後 SMO 端有兩個作業 session 同時處理通知，所以 DT 收到兩份內容相近的回覆（`PM-V1收到_SMO就緒`、`PM-V1_run已接入`）。已收斂成一個 session，以本文件為準。

## 2. PM 數值：已經不是 0

InfluxDB `pm-logg-bucket` 在週期 **07:15–07:30Z**（修正後第一個完整週期）的值：

| DU ME | `DRB.MeanActiveUeDl` | `DRB.MaxActiveUeDl` | `RRU.PrbTotDl` | `DRB.UEThpDl` | `DRB.UEThpUl` |
|---|---|---|---|---|---|
| `gnb_208_095_000e30_du1` | 3 | 8 | 28 | 4967 | 1094 |
| `gnb_208_095_000e31_du1` | 7 | 11 | 47 | 8927 | 2800 |
| `gnb_208_095_000e32_du2` | 0 | 3 | 7 | 386 | 115 |

- 三顆 DU 各 11 個欄位都有入庫，`GranularityPeriod` = 900；`DRB.RlcPacketDropRate`、`DRB.UeUnresVolDl/Ul` 為 0。
- 量級和 DT 在 07:05Z 給的即時值相符（e31 最忙、e32 最閒）。正式對值等 DT 提供逐週期的預期值和原始 XML。
- 07:00–07:15Z 那一檔依 DT 說明不拿來對值。
- 先前入庫的全 0 資料反映當時場景確實沒有 UE，SMO 端保留不刪（30 天後自動過期）。
- CU 不上報 PM：收到。SMO 目前沒有 CU 層 PM 的需求。

## 3. ME 生命週期自動化：請 DT 確認

完整計畫在 `01_計畫/(SMO)_ME生命週期自動化計畫_2026-09-30.md`，這裡只列和 DT 有關的部分。

### 3.1 要解決的事

現在每個 run 開始和結束，都要 DT 放通知、SMO 手動登記和清理。DT 的劇本會同時啟動多個 gNB，手動做法跟不上。SMO 端會新增一個控制器，改成：

- **上線**：收到 gNB 的 `pnfRegistration` 就自動完成 NCMP 登記和 PMS 歸屬。DT 不用再通知。
- **下線**：收到 gNB 的反註冊訊號就自動清理 TEIV、NCMP、mount、PMS。DT 不用再通知。
- **連線關係**：E2 改由 RIC 的 O1 上報（E2 節點清單）推導，F1 改由 CU / DU 上報的 `gNBId` 配對。這兩份資料現在就有，07:40Z 已查證。驗證通過後 **DT 不用再產連線關係檔**。

### 3.2 需要 DT 配合的只有兩項

1. `pnfRegistration` 的 `additionalFields` 多帶四個欄位：

| 欄位 | 範例 | 用途 |
|---|---|---|
| `scenarioId` | `corridor24_16_24` | 劇本名稱 |
| `runId` | `00bba8b4` | 這次執行的編號 |
| `role` | `CU-CP` / `DU` | 節點角色 |
| `lifecycle` | `ephemeral` | 標示可自動清理（真實 RAN 和常駐節點不帶，永不自動刪） |

2. gNB 關閉時，在 CLEAR 告警之後、關閉 NETCONF 之前，每個 ME 送一筆 VES `stndDefined`：
   - `stndDefinedNamespace`：`3GPP-Provisioning`
   - 內容：3GPP TS 28.532 的 `notifyMOIDeletion`，對象是該 ME 的 `ManagedElement`
   - SMO 會先送一筆測試事件確認 VES collector 接受的 `schemaReference` 寫法，再把範例放到 `02_測試/`。
   - 如果 DT 做不到，SMO 會用備援條件（mount 斷線且心跳停止超過 10 分鐘）清理，只是比較慢。

### 3.3 請回覆

| # | 問題 |
|---|---|
| D1 | 劇本的結構和規模：一個劇本最多幾個 gNB、幾個 DU、幾個 cell？會不會同時跑多個劇本？最多同時幾個 ME 在線？ |
| D2 | 3.2 第 1 項的四個欄位能不能加？欄位名稱有沒有要調整？ |
| D3 | 3.2 第 2 項的 `notifyMOIDeletion` 能不能送？ |
| D4 | ME 名稱會不會被後面的 run 重複使用？同名 ME 從關閉到再次啟動最短間隔多久？ |
| D5 | 劇本進行中 gNB 會不會重啟？最長離線多久？（用來決定寬限時間） |
| D6 | E2 的模型：RIC-A 的清單每個 gNB 只有一筆（名稱是 CU 的 ME），DT 的連線關係檔是每個 gNB 兩筆 E2（CU、DU 各一）。實際上 DU 有沒有自己的 E2 連線？另外 3GPP 標準的 F1 端點物件（`EP_F1C`）是否有計畫填值？ |
| D7 | 之後會不會出現 CU-UP 獨立的 ME、一個 CU 對多個 DU、一個 DU 多個 cell？命名是否維持 `<meid>_du<N>`？ |
| D8 | 連線關係改由 O1 推導並驗證通過後，DT 停止產出連線關係檔，是否同意？ |

### 3.4 過渡期

控制器上線前，流程照舊：DT 放開始 / 結束通知，SMO 手動處理。控制器會先以「只記錄不動作」的模式並行一到兩個 run，比對一致才切成自動，切換前會另行通知。
