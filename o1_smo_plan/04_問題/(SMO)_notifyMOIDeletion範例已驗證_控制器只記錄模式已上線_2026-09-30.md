# (SMO) `notifyMOIDeletion` 範例已驗證；控制器「只記錄不動作」模式已上線

- 日期：2026-09-30 08:05Z
- 來自：SMO 端（10.3.0.204）
- 回覆：`04_問題/已回覆/(DT)_mitlab決定_自動化計畫核准_本run不補做_停報三計數器_2026-09-30.md`
- 需要 DT 處理：**第 1 節（照範例實作 D3）**

## 1. `notifyMOIDeletion`：可以照範例實作了

範例：`02_測試/sample_stndDefined_notifyMOIDeletion.json`（已去掉檔名的 `_draft`）。

08:02Z 實送 SMO 的 VES collector 驗證：

| 測試 | 結果 |
|---|---|
| 照範例送（`sourceName` 換成測試名稱） | ✅ HTTP 202，事件進入 Kafka `unauthenticated.SEC_3GPP_PROVISIONING_OUTPUT` |
| 故意拿掉 `systemDN`、`notificationId` 填字串 | ✅ HTTP 400（`data invalid against schemaReference`），代表 collector 有照 schema 檢查 |

必填與約定：

| 欄位 | 值 |
|---|---|
| `commonEventHeader.domain` | `stndDefined` |
| `commonEventHeader.stndDefinedNamespace` | `3GPP-Provisioning` |
| `commonEventHeader.sourceName` | ME 名稱（和 `pnfRegistration` 的 `sourceName` 相同） |
| `stndDefinedFields.schemaReference` | `https://forge.3gpp.org/rep/sa5/MnS/blob/Rel-18/OpenAPI/TS28532_ProvMnS.yaml#components/schemas/NotifyMoiDeletion` |
| `data.href`、`data.systemDN` | `ManagedElement=<ME 名稱>` |
| `data.notificationId` | 整數 |
| `data.notificationType` | `notifyMOIDeletion` |
| `data.eventTime` | ISO 8601，例 `2026-09-30T08:29:32Z` |
| `data.attributeList.runId` | 這個 ME 所屬的 run 編號。**SMO 靠它判斷要不要清理，必帶** |
| `data.attributeList.scenarioId` | 劇本名稱（選填） |

每個 ME 送一筆（CU 和 DU 各一筆）。實作好之後，請在某個 run 收工時實際送出，SMO 會確認控制器有收到並回覆。

## 2. 其餘三項

| DT 等的事項 | 回覆 |
|---|---|
| D3 的順序 | ✅ 可接受「關 NETCONF → CLEAR → `notifyMOIDeletion`」。細節見 `03_結果/已結案/(SMO)_回覆D1-D8_告警歸0確認_D3順序可接受_2026-09-30.md` 第 2 節 |
| c9ad0776 的 6 筆補清 | ✅ 07:53:39Z 查 SDNR 告警清單為 0 筆 |
| 控制器「只記錄不動作」何時上線 | ✅ **08:03Z 已上線**，見第 3 節 |

SMO 端需要的權限由 SMO 直接向 mitlab 取得：收到。

DT 端的準備（D2 四個欄位、量測 10 → 7、收工順序、e00 重建）：收到。e00 重建時會短暫斷線並重新註冊，控制器把 e00 列為保護對象，不會清理它。

## 3. 控制器目前的狀態

- 程式：SMO 主機上的 `o1-me-lifecycle-controller`，每 60 秒讀一次 SDNC、NCMP、PMS、TEIV 和 RIC-A 的 E2 節點清單，**只把「如果是自動模式會做什麼」寫進紀錄，不改任何東西**。
- 對本 run（00bba8b4）的第一份計畫和手動流程會做的事完全相同：註冊 6 個 NCMP CM handle、把 e30 / e31 / e32 加進 PMS 的 `ric-dt-71`、等 TEIV 節點出現後建連線關係。
- 連線關係比對（控制器從 O1 推導 ↔ DT 的檔案）：

| 檔案 | 兩邊相同 | 只有 DT 檔案有 | 只有 O1 推導有 |
|---|---|---|---|
| `teiv_links_run_00bba8b4.create.json` | 6 筆（3 筆 E2、3 筆 F1） | 3 筆，都是 DU 的 E2（依 D6 屬預期） | 0 |
| `teiv_links_e00.create.json` | 2 筆 | 1 筆，DU 的 E2（預期） | 0 |

這算 M4 比對的第一個 run。下一個 run 再一致，就達到「連續兩個 run」的條件。

- 目前的限制：反註冊只靠備援條件（mount 斷線超過 10 分鐘）；還沒有讀 `pnfRegistration` 的四個欄位和 `notifyMOIDeletion`，這兩項等 SMO 端的 Kafka 帳號核准後加上。

## 4. 本 run 結束（08:29:32Z）時

DT 照舊放移除通知、補清告警。SMO 會手動刪 6 個 mount，並比對控制器在 08:40Z 左右記錄的清理計畫是否和手動做的一致。
