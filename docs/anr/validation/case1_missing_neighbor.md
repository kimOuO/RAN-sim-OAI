# ANR 驗測 Case #1:缺漏鄰區(Missing Neighbor)— 端到端閉環報告

> 目標:驗證 `ANR情境_v8.docx` 定義的「缺漏鄰區」問題,能被 RIC xApp 用文件的 ANR API
> **自動診斷 + 解決 + 觀察止血**。對應題型:第 1-4 題。
> 日期:2026-08-12。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

---

## 1. 問題(Problem)

**缺漏鄰區**:兩個不同 gNB 的相鄰 cell,NRT 裡沒有彼此的鄰區關係。UE 從一個 cell 移動到
另一個的覆蓋區時,**無關係可換手 → 撐到 RLF(掉線)→ 靠 RRC 重建才勉強接上**。

| 拓樸 | 值 |
|---|---|
| `src_c0` | gnb=src, pci=20, arfcn=633333 |
| `nbr_c0` | gnb=nbr, pci=30, arfcn=633333 |
| NRT 初始 | **空**(不同 gNB,intra-gNB 種子不會建關係)= 缺漏 |
| UE | ru0-4,在 src_c0/nbr_c0 之間移動 |

**症狀(觀測)**：
- `rlfKpm.cellLevel.src_c0.RLF.DetectedRate` ≈ **1.0-1.3/min**
- `rlfKpm.reestablishmentInboundByPreviousPci`:`nbr_c0 ← previousPhysicalCellId=20 @ 1.0/min`
- RLF outcome：全 `REESTAB_WITHOUT_CTX → nbr_c0`(無 context 硬重建,比乾淨換手差)
- `neighbourCellRelations`：`[]`(無 src_c0→nbr_c0)

---

## 2. 劇本(Scenario)：`anr_missing_neighbor`

- 5 個 UE(ru0-4)在 src_c0 ↔ nbr_c0 之間**連續震盪穿越**(40 waypoints,duration 1200s,每 ~30s 穿一次邊界)。
- 連續穿越 → RLF 連續產生 → `rlfKpm` 持續 ≥ 門檻(見下方 bug #2)。

---

## 3. xApp 閉環(RIC:dt-anr-xapp 0.0.7-guard + rc-probe 0.0.9-syncack)

anr_guard 背景迴圈(10s poll)自動:

| 步驟 | 動作 |
|---|---|
| ① 觀測 | 讀最新 func6 indication 的 `rlfKpm` |
| ② 診斷 | `reestablishmentInboundByPreviousPci` 有 cell X 收到 prevPci=P 的重建 ≥ 0.2/min,且 NRT 無 src(P)→X → missing neighbor |
| ③ 解析 | `RC_MEASCONFIG_REPORTCGI(pci=P, arfcn)` → outcome.cgi 確認全域識別 |
| ④ 修復 | `SONTRIG_ANR_ADD_REQUEST(src, {cgi, pci, arfcn, NR, 20895})` |
| ⑤ 驗證 | 後續 indication:relation 出現 + RLF 降 |
| 防護 | 同 (src,dst) 5 分鐘 cooldown |

---

## 4. 閉環時間軸(2026-08-12 07:08:02 UTC)

```
[ADAPTER] ReportCGI control decode: pci=20 arfcn=633333 rat=NR
[ADAPTER] RIC_CONTROL_REQ recv style=9 action=1 → control_reportcgi
[ADAPTER] ReportCGI outcome → pci=20 cgi=src_c0                              ← ③ 解析成功
[ADAPTER] ANR control → sim CU: {ADD, nbr_c0 → {cgi:src_c0, pci:20, ...}}    ← ④ 修復
NRT: [nbr_c0→src_c0 v1, src_c0→nbr_c0 v1]                                    ← 從空變成有關係
```

---

## 5. 止血驗證(Result)

| 時間 | rlfKpm | 近1分 RLF | HO 成功率 |
|---|---|---|---|
| ADD 前 | 1.0-1.3/min | ≥1 持續 | — (無關係,靠 RLF+重建) |
| ADD 後 07:09:20+ | 0.8/min（窗餘波）| **0** | src→nbr **100%**、nbr→src 68→73%↗ |

- **近1分 RLF = 0**：UE 改走**乾淨換手**,不再掉線 → **止血成功**。
- rlfKpm=0.8 是 10 分滑動窗殘留(ADD 前舊事件),隨窗滑出歸零 —— 正常行為。
- 雙邊確認:sim 端 RLF 停 + RIC 端 HO succ 爬升。

---

## 6. 過程中修的 2 個真 bug（已固化）

1. **scenario_driver 位置格式容錯**（`scenario_loader._normalize_positions`）
   - anr 劇本 UE positions 是 3 值 `[x,y,z]`（無時間軸),loader 的 `interpolate_position`
     期望 4 值 `[t,x,y,z]` → `not enough values to unpack (expected 4, got 3)` crash。
   - 修:3 值 positions 依 `duration_sec` 自動補時間軸 → 4 值。所有 anr 劇本可起、UE 會動。

2. **劇本 RLF 連續性**（劇本設計）
   - 原 2-waypoint 單次穿越 → RLF 陣發稀疏 → `rlfKpm` 10 分窗常清空 → RIC 採樣落空檔看到空。
   - **對帳確認非 producer bug**:sim (a)CU rlf_kpm、(a2)indication endpoint、(b)adapter fetch
     三層都有 rlfKpm，`build_indication_payloads` 整包 zlib 壓縮 rlfKpm 一定在 wire。
   - 修:UE 連續震盪穿越 → RLF 連續 → rlfKpm 持續有值。

---

## 7. 結論

**「發現問題（缺漏鄰區,UE RLF）→ 用文件的 ANR API 診斷（rlfKpm）+ 解析（REPORTCGI）+ 解決（ADD）
→ 觀察止血（RLF→0、HO 100%）」整條由真的 RIC xApp 自動跑通。**

Case #1 是 ANR 驗測 campaign 的第一個 use-case,達成。API 涵蓋:`REPORTCGI`（Style 9)+ `ADD`。

版本:dt-anr-xapp 0.0.7-guard、rc-probe 0.0.9-syncack。
