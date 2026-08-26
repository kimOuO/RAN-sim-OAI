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
| 7 | succ 塌 + failCause 累積 | ~~MRO(B/C)~~ | ✅ **已重驗(2026-08-19 04:16)**,見 §3c |
| 8 | 缺頻率層 + 跨頻強 PCI | MRO(B/C);PRB 已真實(61%) | 低 |
| 9 | `used==limit` + `ADD_REJECTED` | ~~MRO 不成立、PRB=0~~ | ✅ **已重驗(2026-08-19 03:46)**,見 §3b |
| 10 | `CellNotAvailable` 集中 + 新 PCI 同 NCGI | ~~MRO(B)~~ | ✅ **已重驗(2026-08-19 04:3x)**,見 §3d |
| 11 | `relationAgeSec` 大 + att=0 | PRB(A) | 低 |
| 12 | `cum` 空 vs 有值 | — | 無 |

### 三題另有「非環境」的既有折扣

| 題 | 折扣內容 | 嚴重度 |
|---|---|---|
| **3** | ① 卷面 0.6/min 的**絕對稀疏做不到**(sim 每 tick 每 UE 都記錄)→ 改用**相對稀疏**;② **`gap<0` 未達成**(UE 會被較強的未建關係 cell 吸附);③ 卷面「高斷線、過半無法重建」外顯**沒重現**,按「不掉線型」交付 | 中 |
| **4** | 驗收數字達標,但 guard 166 秒就修好,**沒觀察到真正的止血衰減曲線**(病沒發作就治好) | 低 |
| **7** | 「訊號 OK 但接入失敗」sim 做不出,靠 `HO_FORCE_FAIL_TARGET` **注入**才重現 | 低 |
| **9** | RIC 端有自環寫入 bug(已修),其中 **n60 的一條關係是手動補的、非 guard 自主**(他們有標記) | 中 |

### 3b. 第9題重驗結果(2026-08-19 03:46,無保留通過)

修完 MRO / PRB / A3 / Xn 容量後以**同一場景、同一支 guard** 重跑:

```
ADD_REJECTED n60/n62/n61 → n77_c0   by=E2NodeAnrFunction     ← 前置證據
n61: REMOVE n61_c0→x24_c0 (xapp) → ADD n61_c0→n77_c0 (xapp) → ADD n77_c0→n61_c0 (gnb-xn)
n62: REMOVE n62_c0→x24_c0 (xapp) → ADD n62_c0→n77_c0 (xapp) → ADD n77_c0→n62_c0 (gnb-xn)
```

| 項目 | 首輪 | 重驗 |
|---|---|---|
| 來源方向 | ❌ `ADD n77_c0→n62_c0 by=xapp`(來源設成待發現的 cell) | ✅ `n62_c0→n77_c0`,反向由 `gnb-xn` 自動 |
| NRT 容量 | ❌ n62 變 **9/8** | ✅ 三 cell 全 **8/8**(剪一補一) |
| PRB 排除條件 | ❌ 恆 0 | ✅ **5.5 / 16.3 / 8.4%** 真值 |
| MRO 排除條件 | ❌ 污染(RIC 放寬才過) | ✅ **ToWrongCell 全 0、TooEarly ≤0.6** |
| 保護條目 | ✅ | ✅ `x25_c0` 未被碰 |

重驗過程另修一個 sim bug:**Xn 自動反向關係未受容量約束**(首輪造成 n62 9/8)。已修 —— 超限時不建並落
`ADD_REJECTED / NRT_CAPACITY_REACHED`(`by="gnb-xn"`)。

### 3c. 第7題重驗結果(2026-08-19 04:16,無保留通過)

第一輪 guard 週期即完成:
```
DETECT harmful: src_c0→nbr_c0 succ=0.0 att=1.0/min causes={RandomAccessProblem:1.0}
       exclusions REAL: MRO TooEarly=0.0 / ToWrongCell=0.0 flat;PRB src=2.4% dst=48.8% 未飽和
04:16:26  FLAG hoBlocklist SET by=xapp  ack rtt=30ms
```
sim 端:`src_c0→nbr_c0 hoBlocklist=True v1→2`;反向 `False/v1` 零觸碰;
`RandomAccessProblem` 累計凍結在 10(近2分零增長);A3 停止嘗試(att 1.0→0.0)。

**RIC 誠實交代的重點**:harmful 是 08-12 的初代分支,**當時 MRO/PRB 欄位根本不存在,
排除表一直是用「關係健康 + 防抖」代替**。所以那條排除表不只是「因 sim bug 空轉」,
而是**在該分支從未被實作**。0.0.30 補上兩道硬條件:
`max(TooEarly, ToWrongCell) ≤ 1.0`(TooLate 不計 —— 它是本病的果不是因)、
來源與目標 PRB 皆 <85%,並把閘門實際讀值寫進 alarm 的 `exclusions` 欄位供稽核。

### 建議的再確認順序

1. ~~第9題~~ **已完成**(§3b,無保留通過)。
2. ~~第7題~~ **已完成**(§3c,無保留通過)。
3. ~~第10題~~ **已完成**(§3d,無保留通過)。

### 3d. 第10題重驗結果(2026-08-19 04:3x,無保留通過)

```
changeEvents: REMOVE s15_c0→b07_c0 (xapp) → ADD s15_c0→b07_c0 (xapp) → ADD b07_c0→s15_c0 (gnb-xn)
storedPci: 205 → 233(過期對應已修復)
```
| 項目 | 首輪 | 重驗 |
|---|---|---|
| MRO 排除條件 | ❌ 被本病污染 | ✅ `TooEarly=0.0` / `ToWrongCell=0.0` |
| PRB 排除條件 | ❌ 恆 0 | ✅ s15=4.8% / b07=47.7% 真值 |
| 決定性簽名 | ✅ | ✅ `succ=0.0` / `CellNotAvailable=0.5`;`REPORTCGI(205)` 解不到、`(233)→b07_c0 unique` |

---

## ✅ 稽核結論(2026-08-19 收尾)

**三個曾有環境保留的題目(第7、9、10)全部重驗完畢,無保留通過。**
其餘題目的決定性簽名皆不依賴受影響欄位,結論成立。
**Campaign 至此無未結項目。**

剩餘的是**非環境**的既有折扣(重跑也解不掉,屬 sim 能力邊界):
第3題(絕對稀疏 / `gap<0` / 服務終止型外顯)、第4題(未觀察到止血衰減曲線)、
第7題(靠 `HO_FORCE_FAIL_TARGET` 注入)、第9題(RIC 首輪有一條手動補的關係)。
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

---

## 7. 交叉分支測試戰役(2026-08-19)—— 全分支常駐 × 有病場景

十二題原本**全部在隔離模式下驗**;共存煙霧測試只證明「健康網路不誤報」(false positive),
**未證明「有病時正確的那支會贏」**(true positive under cross-branch interference)。
本戰役補這個缺口:**十二支 guard 全分支常駐**,依序跑五個有病場景。

| 輪 | 場景 | 判定 | 附帶產出 |
|---|---|---|---|
| 1 | Q6 Xn 探索 | ✅ | harmful 讓路 15 分鐘實證(repeatCount 85,持續偵測、持續不動手) |
| 2 | Q7 有害鄰居 | ✅ | **sim 兩處 MRO 歸因修復** + RIC 主導原因讓路(0.0.32) |
| 3 | Q9 容量修剪 | ✅ | **barred 語意根源修復** + 「對 bug 訊號正確開槍」雙層判定 |
| 4 | Q10 過期對應 | ✅ | 36 秒閉環 + **0 秒基準流程確立** |
| 5 | Q12 屬性稽核 | v1 ❌ → v2 ✅ | **aging/adminlock 仲裁**(0.0.33)+ **cum 切片 bug** + veto 本質認清 |

**核心命題「有病時正確的那支會贏、別支不搭便車」,在五種病 × 十二支常駐下驗證完成。**

### 7a. 本戰役挖出的 sim 側問題(6 個,全部已修)

| # | 問題 | 影響 | 發現於 |
|---|---|---|---|
| 1 | MRO 把 RLF 歸給不相干的成功換手 | 換手失敗型疾病自我污染 MRO,鎖死正確診斷 | 輪 2 |
| 2 | 「重建回 target 自己」誤判 TooEarly | TooEarly 虛高(64 筆中 45 筆) | 輪 2 |
| 3 | `cellBarred` 與「ADD 後成為合法換手目標」衝突 | 剛修好的關係立刻看起來像有害鄰居 | 輪 3 |
| 4 | Xn 自動反向繞過容量檢查 | NRT 被推成 9/8 | 第9題重驗 |
| 5 | **`cumulativeSinceCreation` 是 2000 筆切片** | 名不副實;舊證據被擠掉 → 正當封鎖被誤判成異常 | 輪 5 |
| 6 | 「前置數據」晚於 guard 動作才收 | 基準與動作分不開,誤列驗收條件 | 輪 4 |

### 7b. 兩條進入方法論的教訓

1. **「量測中」veto 是時間賽跑,不是結構保障。**
   輪 5 實測:`targetSampleRatePerMin` 衰減到 0.8/min 跌破門檻,veto 失效,aging 隨即刪光稽核場景。
   **屬性判斷(`isHoAllowed=false` = O&M 刻意封鎖)才是結構性的。**
   延伸論據:ANR 自動建立的關係初始一律 `true`(CON-01),看到 `false` 就代表有人動過手;
   而「age 大 + att=0」在封鎖關係上**恆真**(封鎖本來就讓 att=0)——
   **用「沒人用」當理由刪掉「被禁止使用」的關係,是循環論證**。

2. **連 sim 自己的輸出欄位都可能名不副實。**
   `cumulativeSinceCreation` 叫 since-creation,實際只涵蓋最近 2000 筆。
   對帳要以 wire 為準,**而且要質疑欄位語意**,不能因為名字寫著什麼就信什麼。

3. **re-arm 後必須在 0 秒收基準。** 輪 4 的爭點本質是基準晚於動作(guard 36 秒就完成三步,
   而我 3 分鐘後才收「前置數據」)。基準與動作必須分離。

### 7c. mobility 仲裁變體(2026-08-20)—— 雙向實證完結

0.0.32/0.0.33 的兩條 mobility 讓路原本只有離線驗證。以**事件層注入**補驗
(注入標準樣態的 HandoverEvent + RlfEvent,`mro_kpm` 照正常邏輯計算 = fault injection;
**wire 層代碼路徑已驗證,物理可重現性為已知限制**——見下)。

| 變體 | 主導 cause | MRO 讀值 | 正解 | 結果 |
|---|---|---|---|---|
| ① **該讓** | `CellNotAvailable` 100% | TooEarly **3.0**(>門檻 1.0) | 讓路 → 照常 REMOVE+ADD | ✅ 30 秒閉環;alarm `exclusions.mroTooEarly: 3.0` 併 `action: REMOVE_THEN_ADD` = bypass 鐵證 |
| ② **不該讓** | `HandoverToWrongCell` 100% | 0(見下) | **不動手** + SMO_NOTIFY | ✅ 2 秒收手;`changeEvents=0`、6 條關係全 `v=1`、`mobility_failure_smo_notify` 一筆 |

**同樣是「cause 主導」,結論相反** —— ①證明會讓,②證明不會亂讓。

**②比原設計更嚴**:`mroToWrongCell` 讀值是 0(見下),MRO 閘門全放行,
harmful 收手**純靠「cause 是 MRO 語意」的主動判斷**,沒有任何外力兜底。

#### ⚠️ `mroKpm.*Rate` 是自我抹除的 —— 不可當閘門

```
1. mro_kpm 判定某 RLF 為 ToWrongCell
2. backfill 把對應的成功換手改寫成 status=FAIL / cause=HandoverToWrongCell
3. 下次查詢時該筆已是 FAIL → 命中「更近的失敗嘗試優先 → 不做 MRO 歸因」(輪2 修正)
4. → 該 RLF 從此被跳過,mroToWrongCell 歸零
```

**`mroKpm.*Rate` 是一次性的**(分類完就把自己的依據改掉);
**關係層的 `handoverFailureCauseRatePerMin` 才是持續可靠的訊號**。

判「這是 MRO 型病」請用 `handoverFailureCauseRatePerMin` 的 `HandoverToWrongCell` 佔比,
**不要用 `mroKpm.ToWrongCellRate`**。雙方同意此為分類的合理副作用、非 bug ——
改成獨立欄位會牽動輪 2 的歸因鏈,風險大於收益。

### 7d. 已知限制:mobility 仲裁無法用物理自然重現

嘗試過「4 cell、120m 間距、快速穿梭 UE、A3 拉回 1.5dB/80ms」造真 TooEarly,失敗:
**兩個條件互斥** —— 真 TooEarly 需要「換手成功 → 立刻 RLF → 退回 source」,
但近距離邊界訊號良好**不會 RLF**;要 RLF 就得挖覆蓋洞,UE 隨即掉光成 IDLE。
加上 sim 修好 MRO 歸因後連誤報來源都消失,**「真實且持續的 MRO 不平坦」與「非 MRO cause 主導」
在目前物理模型下無法自然並存**。故改用事件層注入,並在此標明。

### 7f. Q1 / Q11 劇本 bug 重驗(2026-08-20)

劇本的 UE 位置若是 3 元素 `[x,y,z]`(無時戳),sim 端 `_normalize_positions`
會把時戳**平均攤在 `duration_sec` 上**。8/20 把 `anr_missing_neighbor`(Q1)與
`anr_stale_relation`(Q11)的 duration 由 1200s 拉到 86400s **卻沒等比例加位置點**
→ 每段 30s 變 2215s,**UE 速度 10.7 → 0.15 m/s**,兩題等於不會觸發換手。
位置點 40 → 2880 修復(11.3 m/s),重驗:

| 題 | 佈病 | xApp 動作 | 結果 |
|---|---|---|---|
| Q1 | 刪 src↔nbr | `04:08:00 ADD src_c0→nbr_c0` instId=183 → `ADDED`;`04:08:02` 反向 `by=gnb-xn` | ✅ RLF 1.2/min、重建 inbound `prevPci=20` 1.2/min;修後 HO 1.8/min succ 100% |
| Q11 | 老化 30 天零活動 + noRemove 保護 | `04:44:32 REMOVE main_c0→old_c0 reason=aging` instId=189 → `REMOVED` | ✅ 關係 3→2;保護條目零觸碰;HO 3.0/min succ 100% |

**Q11 拒絕路徑補驗(RIC 主動加測,04:53:50 instId=190)**:對受保護條目刻意送 REMOVE
→ `REJECTED_PROTECTED`,rtt 18ms。關係完好的證明用**年齡連續性**:649s → 34 秒後 682s
(= 649+33),若曾被刪再補回 age 會歸零 —— 故為「從未被移除」,不是「刪掉又救回」。

RIC 補充:受保護條目零觸碰是**結構保障不是運氣** —— aging 分支送 REMOVE 前先看
`flags.noRemove` / `isRemoveAllowed`,命中就跳過並記 `stale_protected`,control 根本不發出。
拒絕路徑是打「防禦縱深」用的:萬一屬性判斷漏了,sim 端攔不攔得住。

#### 這輪雙方各驗出一個對稱的洞

| 端 | 洞 | 後果 |
|---|---|---|
| RIC | `_guard_stale_remove()` **不分辨 outcome 的 result** —— 回 `REMOVED` 或 `REJECTED_PROTECTED` 都記成 `stale_removed / REMOVE_SENT` | 稽核會宣稱刪掉了、其實沒刪(0.0.32 修掉的 ADD 側「靜默 REJECTED」在 REMOVE 側的孿生) |
| sim | REMOVE 被拒**不落審計事件**(ADD 被拒有 `ADD_REJECTED`,REMOVE 沒有) | 「送了但被擋」與「根本沒送」在稽核面無法區分 |

兩者疊加時,一筆被拒的 REMOVE 在兩邊同時隱形。
sim 側已修:落 `REMOVE_REJECTED / PROTECTED_ENTRY`,`reason` 欄位擴及所有 `*_REJECTED`。
自測(直打 CU 不經 RIC):`REJECTED_PROTECTED` + 稽核事件 `REMOVE_REJECTED`,關係 v=1 未變。
RIC 側列入下版批次(共三項:Case#1 不寫 alarms、REMOVE 側 result 檢查、MRO flat 措辭),
不為此單獨動 0.0.33 驗收基準,併下次功能改動一起出版並重跑共存煙霧測試。

#### 操作規則(新增)

**佈病一律在 sim 啟動 75 秒之後** —— 啟動後頭一分鐘關係表會被清場重建,
該期間的 `changeEvents` 是雜訊(Q1 的 instId=185、Q11 的 instId=188 都是這樣來的:
xApp 量測發現分支正確地把被清掉的關係補了回來)。

### 7e. 收官

**交叉分支測試(五輪 + 兩變體)全部完結,無未結項目。**
mobility 讓路兩條路徑(該讓 / 不該讓)已於 7c 雙向實證;
真實物理場景之不可重現性已於 7d 標為已知限制。
