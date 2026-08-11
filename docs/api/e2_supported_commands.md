# DT 平台 E2 支援命令清單(單一真相來源)

> **這份文件是 DT E2 node 對 RIC/xApp 支援命令的權威清單。**
> 任何 E2 命令的新增 / 修改 / 移除,都必須同步更新本文件。
> 對接細節另見:[`e2sm_ccc_cell_control.md`](./e2sm_ccc_cell_control.md)(CCC 格式)、[`e2sm_fullkpm.md`](./e2sm_fullkpm.md)(FULLKPM 欄位)、[`rc_observation_api.md`](./rc_observation_api.md)(RC 觀測 API)。

最後更新:2026-08-11

---

## 0. 節點識別
| 項目 | 值 |
|---|---|
| PLMN | MCC=208 / MNC=95 |
| gNB ID | `gnbDT`(`gnb_208_095_000e00`,gNB-ID hex `0x000e00`, len 22) |
| RMR types | 12040 CONTROL_REQ · 12041 CONTROL_ACK · 12042 CONTROL_FAILURE |
| CCC 編碼 | JSON(非 ASN.1),包在 E2AP OCTET STRING |

---

## 1. E2 Setup 廣播的 RAN Function（xApp 可發現）

| RAN Func ID | Service Model | OID | 版本/說明 | 狀態 |
|---|---|---|---|---|
| **2** | **KPM** | `1.3.6.1.4.1.53148.1.2.2.2` | E2SM-KPM v2.0.03 | ✅ 常開 |
| **3** | **RC** | `1.3.6.1.4.1.53148.1.1.2.3` | E2SM-RC v01.03 | ✅ 常開 |
| **4** | **CCC** | `1.3.6.1.4.1.53148.1.1.2.4` | E2SM-CCC(cell 開關/節能) | ✅ 開，受 env `E2SM_CCC_ENABLE` gate |
| **5** | **FULLKPM** | `1.3.6.1.4.1.53148.1.1.2.100` | sim 擴充：190 欄完整 KPM | ✅ |

> 定義位置：`RANsim-CU/main/apps/cu_cp/services/optional/e2/global_e2_node_id.py`
> Adapter 廣播 gate：`RANsim-E2Adapter/.../codec/e2ap_codec.py`（CCC 由 `E2SM_CCC_ENABLE` 控制）

---

## 2. 支援的 E2 程序（procedure）

| 程序 | 支援 | 用於 |
|---|---|---|
| E2 Setup | ✅ | 廣播上表 4 個 RAN function |
| RIC Subscription（create / delete / list） | ✅ | KPM（量測訂閱） |
| RIC Indication（polling 取代 SCTP push） | ✅ | KPM / FULLKPM 上報 |
| RIC Control（Request → ACK / FAILURE） | ✅ | RC / CCC |
| RIC Control（CCC Indication 狀態回報） | ⏳ 未接 | CCC 節能完成回報（需 xApp 先訂閱 CCC） |

---

## 3. KPM（id=2）— 量測上報

- Report **Style 1**（E2 Node Measurement）。
- 支援 metrics（9）：

| Metric | 單位 |
|---|---|
| DRB.UEThpDl / DRB.UEThpUl | bps |
| DRB.PdcpSduVolumeDL / DRB.PdcpSduVolumeUL | kbit |
| DRB.RlcSduDelayDl | μs |
| RRU.PrbTotDl / RRU.PrbTotUl | PPM |
| RSRP | dBm（sim 擴充） |
| SINR | dB（sim 擴充） |

> 定義位置：`RANsim-E2Adapter/.../codec/e2sm_kpm_codec.py`

---

## 4. RC（id=3）— 控制（RIC Control）

| Style / Action | 命令 | 用途 | 粒度 | 狀態 |
|---|---|---|---|---|
| **Style 1 / Action 2** | QoS flow mapping | 改 UE QoS flow 對應 | per-UE | ✅ |
| **Style 2 / Action 6** | Slice-level PRB Quota（min/max/dedicated） | IM / ES | per-cell / gNB | ✅ |
| **Style 3 / Action 1** | **Handover** | CCO / ES 趕人 | per-UE | ✅ 已端到端驗證 |
| Style 2 / Action 7 | cell on/off（**非標準 legacy**） | 舊版開關 cell | per-cell | ⚠️ 保留但已被 CCC 取代 |

> Decode：`RANsim-E2Adapter/.../codec/e2sm_rc_codec.py`
> 落地：`RANsim-CU/.../actors/e2_control_actor.py` → `request()` 分支

---

## 5. CCC（id=4）— cell 配置與控制 / 節能（JSON）

透過 `listOfCellsControlled[].listOfConfigurationStructures[].newValuesOfAttributes`：

| 屬性（結構） | 值 | 效果 | 狀態 |
|---|---|---|---|
| **administrativeState**（NRCellDU） | LOCKED / UNLOCKED | 硬開關，即時，不趕人 | ✅ |
| **cellState**（NRCellDU） | INACTIVE / ACTIVE | 硬開關 | ✅ |
| **energySavingControl**（O-CESManagementFunction） | toBeEnergySaving / toBeNotEnergySaving | **兩階段節能**：趕人(HO) → 清空 → 關 cell | ✅ 已端到端驗證 |

- 上行回 **RIC_CONTROL_ACK**（成功）/ **FAILURE**。
- cell 識別：xApp 送 **`nRCellIdentity` 字串**（`gnbDT_c0` / `gnbDT_c1`）；數字 NR Cell Identity 需另加映射。
- **CCC Indication（狀態回報）producer 尚未接**，需 xApp 先訂閱 CCC。

> Codec：`RANsim-E2Adapter/.../codec/e2sm_ccc_codec.py`
> 狀態機：`RANsim-CU/.../actors/e2_control_actor.py` → `_cell_energy_saving()`
> 詳細格式：[`e2sm_ccc_cell_control.md`](./e2sm_ccc_cell_control.md)

---

## 5b. ANR / E2SM-ANR（ran_func=6，JSON 承載，受 `E2SM_ANR_ENABLE` gate）

> 目標：xApp 由組態書寫者 → gNB SON 觸發者（`docs/ANR情境_v8.docx`）。真實度 = A（命令真實改變模擬行為）。分階段見 `docs/plan/anr_xapp_commands_plan.md`。OID `1.3.6.1.4.1.53148.1.1.2.6`，ricStyleType=1。

**觀測（M0 完成）：**
| 端點 | 對應 xApp 命令 | 說明 |
|---|---|---|
| `POST /CU/E2/NodeInfo/read {cell_id?}` | `RC_E2NODEINFO_QUERY` | 回 §9.3.38 neighbourCellRelations（+卷面延伸、flags、version）|
| `POST /CU/E2/Anr/reseed` | —（內部）| 從 CellConfig 重種 NRT + CGI 解析 |

**SON 觸發控制（M1 廣播 + M2 命令完成）：** E2 Setup `accepted=[2,3,4,6,5]`（含 6）。
xApp 送 RIC Control（ran_func=6，JSON `controlMessageFormat.sonTriggerRequest`）→ adapter 解碼 → `POST /CU/E2/Anr/control`：
| requestType | 參數 | 效果 | 對應 xApp 命令 |
|---|---|---|---|
| `ADD` | sourceCellId, target{cgi,pci,arfcn[,rat,plmn]} | 新增/更新鄰區關係，version+1 | `SONTRIG_ANR_ADD_REQUEST` |
| `REMOVE` | sourceCellId, targetCgi, reason | 移除；保護條目(is_remove_allowed=False/no_remove)→拒絕 | `SONTRIG_ANR_REMOVE_REQUEST` |
| `FLAG` | sourceCellId, targetCgi, flag∈{hoBlocklist,noRemove,xnBlocklist}, op∈{set,clear} | 設/清旗標，version+1 | `SONTRIG_ANR_FLAG_REQUEST` |

- 受控物件：`NrCellRelation`、`CgiResolution`；種子：F1 Setup 後自動建 intra-gNB 鄰區（冪等）。
- confirm 慣用式：以 `version` 變化 / 條目出現消失判定（xApp 輪詢 NodeInfo/read）。

**M4（A 級行為）已完成並驗證：** A3 換手決策 `evaluate()` 讀 `ho_blocklist`（env `ANR_ENFORCE_HO_BLOCKLIST` 可停用）→ 被封鎖的鄰區直接略過。決定性測試:未封鎖→HO 觸發;FLAG set→不觸發;clear→恢復。→ 真實「封鎖止血」行為。

**待做（M3）：** 關係變更事件訂閱（RC_E2NODEINFO_SUBSCRIBE，關係變更主動推 xApp）。目前 confirm 走 NodeInfo/read 輪詢已可用。

---

## 6. FULLKPM（id=5）— 完整 PM

- KPM 擴充版，一次輸出 **190 欄完整 pm 欄位**（對齊 `E2_data_example.md`）。
- 給需要完整 PM 的 xApp。

> 詳見 [`e2sm_fullkpm.md`](./e2sm_fullkpm.md)

---

## 7. 變更紀錄（每次擴充/修改 E2 命令都在此追加一行）

| 日期 | 變更 | 影響 SM / Style-Action |
|---|---|---|
| 2026-08-11 | 建立本清單（現況盤點） | KPM / RC / CCC / FULLKPM 全部 |
| 2026-08-11 | ANR M0：NrCellRelation/CgiResolution 模型 + 種子 + `E2/NodeInfo/read`（RC_E2NODEINFO_QUERY）| 新增 §5b ANR |
| 2026-08-11 | ANR M1：E2SM-ANR ran_func=6 廣播（E2SM_ANR_ENABLE gate）+ codec；E2 Setup accepted=[2,3,4,6,5] | §5b |
| 2026-08-11 | ANR M2：ADD/REMOVE/FLAG → `E2/Anr/control` 落地 NrCellRelation + version;adapter SCTP 路由 | §5b |
| 2026-08-11 | ANR M4（A 級）：A3 換手 evaluate() 讀 ho_blocklist skip target;決定性驗證通過 | §5b |
