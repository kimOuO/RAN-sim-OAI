# ANR 驗測 Campaign 總結(`ANR情境_v8.docx` 十二題)

> DT sim ↔ OSC Near-RT RIC 雙邊驗測。目標:**每題做劇本 → RIC 建 xApp guard 用 ANR API
> 自動診斷並處置 → 雙邊驗證結果**。真實度要求 = A(命令真實改變模擬行為)。
> 期間:2026-08-12 ~ 2026-08-19。RIC 端版本:`dt-anr-xapp 0.0.17 → 0.0.28-attraudit`、
> `rc-probe 0.0.10-threaded`。

---

## 1. 十二題結果一覽

| 題 | 問題型 | 正解類型 | 使用 API | 狀態 |
|---|---|---|---|---|
| 1 | 缺漏鄰區(重建統計反推) | 修 | REPORTCGI + ADD | ✅ |
| 2 | 缺漏鄰區(量測側偵測) | 修 | REPORTCGI + ADD + `anrIntraEnabled` 前置檢查 | ✅ 啟用/停用雙分支 |
| 3 | 缺漏鄰區(深邊緣稀疏) | 修 | REPORTCGI + ADD | ✅ 有折扣(見 §3) |
| 4 | 未知 cell 偵測 | 修 | REPORTCGI(新 NCGI)+ ADD | ✅ 有折扣 |
| 5 | PCI 撞號 | **擋** | REPORTCGI(confusion)→ 抑制 ADD | ✅ |
| 6 | Xn-C TNL 探索失敗 | **不動手** | 觀測 + SMO_NOTIFY(零 E2 動作) | ✅ |
| 7 | 有害鄰居 | 修 | FLAG hoBlocklist | ✅ 靠注入(見 §3) |
| 8 | 跨頻鄰區啟用 | 修 | REPORTCGI(帶 arfcn)+ ADD ×3 | ✅ 一次通過 |
| 9 | NRT 容量修剪 | 修 | REMOVE(剪)→ ADD(補) | ✅ 有保留(見 §3) |
| 10 | 過期對應(同站換 PCI) | 修 | REPORTCGI → REMOVE → ADD | ✅ 第二輪乾淨驗證 |
| 11 | 老化 / 自動刪除 | 修 | REMOVE + 保護條目拒絕 | ✅ |
| 12 | NRT 屬性稽核 | **不動手** | 觀測 + SMO_NOTIFY(零 E2 動作) | ✅ |

**三類正解全覆蓋**:修(1/2/3/4/7/8/9/10/11)、擋(5)、不動手(6/12)。
另:**E2 控制命令總測 10/10**(ReportCGI / ADD / FLAG / REMOVE / HO / PRB / CCC / 三種訂閱)。

**共存煙霧測試**(2026-08-19):十二支 guard 全分支常駐 × 中性健康場景 × 21 分鐘 —
`changeEvents` 0、`by=xapp` 0、關係 version 全為 1、adapter ANR control 0、HO 15/min(場景是活的)。
→ 十二支可常駐,不會在健康網路上誤報。

---

## 2. sim 這輪補的能力(10 項,皆對齊規範)

| # | 能力 | 規範依據 | 為什麼需要 |
|---|---|---|---|
| 1 | `anrIntraEnabled` + ADD 拒絕 | 卷面前置檢查 | 停用時只得 SMO_NOTIFY,不得自動寫 NRT |
| 2 | `nrtCapacity {limit, used}` | 卷面(容量為實作限制) | 第3題排除容量因素、第9題判滿載 |
| 3 | `ADD_REJECTED` / `NRT_CAPACITY_REACHED` | 卷面定義之可觀測事件 | 證明「阻斷點在容量、非偵測失效」 |
| 4 | `sourceCellNcgi` / `bySourceCell` | 鄰區關係是 per source cell | 沒有它 xApp 無從決定 ADD 的 `sourceCellId` |
| 5 | **量測回報門檻** `MEAS_REPORT_MIN_RSRP_DBM` | TS 38.331 `reportConfig` | sim 原本把所有 cell 照報(不真實),稀疏樣本情境做不出來 |
| 6 | **`cellBarred`** + 重建選 suitable cell | TS 38.331 / 38.304 | 「量得到但不收 UE」的鄰居;否則必然把 UE 吸走、情境瓦解 |
| 7 | **Xn 反向關係自動建立**(延遲 2s) | TS 38.300 §15.3.3.2 步驟 4c | 卷面禁止 xApp 寫反向;gNB 自建,審計標 `by="gnb-xn"` |
| 8 | `TXnRELOCprepExpiry` 失敗原因 | TS 38.423 | Xn 未建立 → 換手準備必然逾時(第6題決定性簽名) |
| 9 | `RRU.PrbTotDl/Ul` 進 func6 | 卷面 `kpmIndication.cellLevel` | 壅塞判定 / 排除 MLB 型 |
| 10 | `perNeighbourRelation` 列出**零活動關係** | 卷面第9/12題範例 | 修剪候選與封鎖稽核的判斷對象都是零活動關係 |

## 2b. 過程中修掉的真 bug(4 個)

| bug | 影響 | 發現方式 |
|---|---|---|
| **ANR ACK 缺 `RICcontrolOutcome`** | ADD/REMOVE/FLAG 的 ACK 只有 22 bytes,xApp 無法從 ACK 分辨結果 | RIC 實測指出 |
| **MRO 誤採失敗換手** | 失敗的 HO 被當「近期有 HO」→ 後續 RLF 歸成 TooEarly/ToWrongCell。**換手失敗型題目自我污染 MRO**,使「MRO 平坦」永遠不成立 | RIC 於第6題指出 |
| **8 個劇本 traffic 綁錯 UE 名** | 綁在基底劇本的 `ru0~ru4`,各劇本 UE 名不同 → **整個 campaign 沒有流量、PRB 恆 0** | 補 PRB 欄位後才發現 |
| **`freq_relations` 語意錯** | 列「所有 cell 的頻率」而非「已建立關係的頻率層」→ 第8題核心信號直接穿幫 | 做第8題時查證 TS 28.541 |

---

## 3. ⚠️ 逐題稽核 —— 哪些題有環境因素、需要再確認

三個系統性環境問題**在 campaign 進行中才被發現並修復**,先前完成的題目在當時是帶著這些缺陷通過的:

- **(A) PRB 恆 0**(traffic 綁錯,修於第8題之後)→ 所有「PRB 平坦 → 排除 MLB 型」的排除條件**當時是空的**(永遠成立)。
- **(B) MRO 污染**(失敗換手誤計,修於第6題之後)→ 所有「MRO 三類平坦」的排除條件在**換手失敗型**題目上**當時不成立**。
- **(C) A3 過激進**(1.5dB/80ms 必然乒乓,修為 3dB/300ms)→ 同樣污染「MRO 平坦」。

| 題 | 決定性簽名 | 受影響的排除條件 | 需要再確認? |
|---|---|---|---|
| 1 | 重建統計 `reestabInboundByPreviousPci` | PRB(A) | 低 — 簽名獨立 |
| 2 | 量測 gap ≤ MARGIN_HO | PRB(A)、MRO(C) | 低 — 簽名獨立 |
| 3 | 稀疏樣本 + NRT 查無 | PRB(A)、MRO(C) | 低 — 但本題另有折扣,見下 |
| 4 | 量測強 + 新 NCGI | PRB(A)、MRO(C) | 低 — 簽名獨立 |
| 5 | `confusion=true` | — | 無 |
| 6 | `xnX2Established=false` + cause 主導 | MRO(B,本病自我污染) | **已在該題當場處理**(RIC 降為佐證,我隨後修根因) |
| 7 | succ 塌 + failCause 累積 | MRO(B/C) | **中** — 換手失敗型,自我污染最嚴重 |
| 8 | 缺頻率層 + 跨頻強 PCI | MRO(B/C);PRB 已真實(61%) | 低 |
| 9 | `used==limit` + `ADD_REJECTED` | **MRO 條件明確不成立,RIC 放寬才通過**;PRB(A) | **高** — 見下 |
| 10 | `CellNotAvailable` 集中 + 新 PCI 同 NCGI | MRO(B,本病自我污染) | 中 |
| 11 | `relationAgeSec` 大 + att=0 | PRB(A) | 低 |
| 12 | `cum` 空 vs 有值 | — | 無 |

### 三題另有「非環境」的既有折扣

| 題 | 折扣內容 | 嚴重度 |
|---|---|---|
| **3** | ① 卷面 0.6/min 的**絕對稀疏做不到**(sim 每 tick 每 UE 都記錄)→ 改用**相對稀疏**;② **`gap<0` 未達成**(UE 會被較強的未建關係 cell 吸附);③ 卷面「高斷線、過半無法重建」外顯**沒重現**,按「不掉線型」交付 | 中 |
| **4** | 驗收數字達標,但 guard 166 秒就修好,**沒觀察到真正的止血衰減曲線**(病沒發作就治好) | 低 |
| **7** | 「訊號 OK 但接入失敗」sim 做不出,靠 `HO_FORCE_FAIL_TARGET` **注入**才重現 | 低 |
| **9** | RIC 端有自環寫入 bug(已修),其中 **n60 的一條關係是手動補的、非 guard 自主**(他們有標記) | 中 |

### 建議的再確認順序

1. **第9題(高)** — MRO 排除條件當時明確不成立、RIC 放寬才過;PRB 當時為 0。現在 MRO 與 PRB 都修好了,**重跑一輪可讓該題不帶保留**。
2. **第7題(中)** — 換手失敗型,MRO 自我污染最嚴重。修完 MRO 後重跑可驗證「MRO 平坦」這條真的成立。
3. **第10題(中)** — 同為換手失敗型,同理。
4. 第1/2/3/4/11題(低) — 決定性簽名皆與 PRB/MRO 無關,結論穩固;若要求排除表逐條有效,可低優先補跑。

> **結論**:十二題的**診斷結論全部成立**(決定性簽名都不依賴受影響的欄位),但**部分題目的「排除條件」在當時並未真正被驗證**。這不是判錯,是驗證覆蓋度的缺口。

---

## 4. 已知 sim 限制(劇本設計前必讀)

1. **場景地面僅 1000×1000m(±500m)** — 超出範圍 RSRP 凍結、距離失效。
2. **絕對稀疏 <1/min 做不到** — 每 tick 每 UE 都記錄量測;只能做相對稀疏。
3. **`gap<0`(serving 遠弱於鄰區)難以維持** — UE 會 RLF 後重建到較強的 cell。
4. **`cellBarred` 三條操作規則**:
   - 標 barred 時 UE 若正駐留其上 → 釋放成 IDLE 且不自動重附著,**須重啟劇本**。
   - **不可讓一個 cell 的所有鄰居都 barred** → UE 一 RLF 就找不到合格落點 → DROP → 永久 IDLE。
   - barred 只管**閒置態選網/重建**;**連線態換手**歸 `isHoAllowed`/`hoBlocklist`。
5. **CU 重啟 / 重建後必須連帶重啟劇本** — 否則 UE 脫鉤停推量測(RIC 端症狀:`rowsScanned=0` 全空)。
6. **改 Python 用 `docker restart`;改 env 才用 `docker compose up -d`** — compose 無變更時不會重建容器,程式碼改動不生效。
7. **劇本 duration 要開足**(≥7200s,建議 86400s)— 波形跑完 UE 靜止會造成「假性平靜」。
8. **劇本一律以已驗證劇本為基底改寫** — 手寫從零會漏欄位(`traffic`/`_metadata`),driver 不推位置。
9. **cell 間距需 ≥300m** — 150m 時 A3 delta 僅約 1.6dB,換手執行不出來。
10. **`inject_call_count` 是死計數器** — 判斷流量要看 `MeasurementLog.throughput` / `CellMeasurementLog.prb`。

---

## 5. 判讀陷阱(止血曲線)

1. **UE 靜止假歸零** — 劇本跑完 UE 不動,RLF 自然歸零,不是止血。先確認 HO 流量 >0。
2. **環境地板不是 0** — 走廊邊緣、UE 高速跨 cell 都會產生 ANR 修不掉的 RLF。baseline 要用**完整 NRT 下的實測值**。
3. **空窗填充 ≠ 衰減** — 清空記錄後滑動窗由 0 往上填,方向與止血相反。
4. **被疾病污染的指標不能當排除閘門** — 換手失敗型疾病會自己把 MRO 打高(此為 sim bug,已修;但原則通用)。
5. **交接給 RIC 後鎖定場景、全程唯讀** — 中途 re-arm 會打斷對方的滑動窗驗收。

---

## 6. 各題詳細報告

`case1_missing_neighbor.md`、`case2_harmful_neighbor.md`(第7題)、`case3_pci_confusion.md`(第5題)、
`case4_stale_relation.md`(第11題)、`case_q2_missing_meas.md`、`case_q3_sparse_edge.md`、
`case_q4_unknown_cell.md`。第6/8/9/10/12 題的閉環證據見 git log 與 RIC 端 `logs/`。
