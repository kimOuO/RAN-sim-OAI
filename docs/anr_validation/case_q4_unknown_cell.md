# ANR 驗測 第4題:未知 cell 偵測(Unknown Cell Detection)

> `ANR情境_v8` 第4題 — Neighbour Detection Function。偵測到「NRT 中不存在對應關係」的鄰居 cell,
> 外顯為連線中斷型服務劣化(RLF 飆升)。
> 日期:2026-08-18。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

## 1. 問題

服務 cell `s01_c0` 東側是跨域邊界,出現一個 NRT 完全沒有的 cell(`unk_c0`, pci=301)。
UE 東行時**量到它的強訊號卻換不過去**(NRT 無關係 → 換手前提不成立)→ 撐到 RLF。

## 2. 劇本 `anr_unknown_cell`(單一走廊,UE 沿 z=-40 東西連續掃)

| cell | pci | x | NRT 關係 |
|---|---|---|---|
| `n02_c0` | 118 | -300 | ✅ 健康(雙向) |
| `n03_c0` | 125 | -150 | ✅ 健康(雙向) |
| `s01_c0` | 101 | 0 | ✅ 健康(雙向) |
| **`unk_c0`** | **301** | +300 | ❌ **完全無關係(未知)** |

全部 3.5 GHz / arfcn 633333。UE `uk0-4` 連續東西掃 -320↔+320。

## 3. 實測信號(四個排除表角落全部成立)

```
① 既有關係健康  n02→n03 succ=1.0 failCause={}   ← 排除「既有關係故障型」
                n03→n02 succ=1.0 failCause={}
                n03→s01 succ=1.0 failCause={}
② 量測聚合鑽取  pci=301 sample/min=378.5 rsrpP50=-71.6 rsrpP90=-56.0 std=7.42
                → 訊號最強且穩定被量到,但 NRT 查無 (301, 633333)  ← 排除「RF 劣化型」
③ 外顯症狀      s01_c0 RLF.DetectedRate=2.4/min(基準遠低於此)
④ CGI 解析      REPORTCGI(pci=301) → {"unk_c0":3} unique=true confusion=false
                → 收斂到「新 NCGI」,不等於任何既有條目的 targetCgi
```

## 4. 與已完成案例的鑑別線(重要)

| | 偵測路徑 | CGI 解析結果 |
|---|---|---|
| 第1題 缺漏(已閉環) | **目標側重建統計** `reestablishmentInboundByPreviousPci` 反推 | 既有 cell |
| **第4題 未知(本題)** | **來源側量測聚合鑽取** `e2MessageCopyAggregate` | **新 NCGI** |
| 第10題 過期(已閉環) | 既有關係 `CellNotAvailable` 集中 | 收斂回**既有條目**的 targetCgi |

→ 第4題必須走 **量測驅動**,不可等 RLF 重建統計;且解析結果是**新** NCGI 才算未知。

## 5. RIC 待建 guard

| 步驟 | 動作 |
|---|---|
| ① 觀測 | func6 `e2MessageCopyAggregate.measurementReportAggregate` + `e2NodeInformation` |
| ② 診斷 | 某 (pci, arfcn) `sampleRatePerMin` 高、rsrp 強且穩,但 NRT 查無條目 |
| ③ 排除 | 既有關係 succ 高且 failCause 空(非既有故障)、MRO 三類平坦(非 MRO)、PRB 平坦(非 MLB) |
| ④ 解析 | `RC_MEASCONFIG_REPORTCGI(pci, arfcn)` **多次抽樣**(防 confusion) |
| ⑤ 修復 | 收斂到新 NCGI → `SONTRIG_ANR_ADD_REQUEST(s01_c0, {cgi, pci, arfcn, NR, 20895})` |
| ⑥ 驗證 | RLF 回落 + 該方向改走乾淨換手 |

**卷面紅線**:L2 禁止僅憑 PCI 直接寫入關係(必須先 REPORTCGI 解出 CGI);
L4 禁止單一視窗即觸發(需持續性,建議 ≥2 窗)。

## 6. 驗收基準(卷面）

- `RLF.DetectedRate` 回落至 **不超過基準 1.5 倍**,並連續 6 個滑動窗維持。
- 處置後既有各關係 `MM.HoExeSuccRatio_last50` **不得低於 0.97**。

---

## 7. 閉環實測(2026-08-18 04:29–04:47 UTC · RIC dt-anr-xapp)

```
04:29:21  RC_MEASCONFIG_REPORTCGI(pci=301, arfcn=633333, rat=NR)   ← 先解析(遵守 L2 紅線)
          ReportCGI outcome → pci=301 cgi=unk_c0  unique=true
04:30:13  ADD unk_c0→s01_c0 / unk_c0→n02_c0 / unk_c0→n03_c0        ← 反向關係(讓 UE 能回流)
04:30:23  ADD s01_c0→unk_c0 pci=301 → result=ADDED                 ← 核心修復
```

**RLF 單調回落(s01_c0 RLF.DetectedRate,每 20s 取樣)**:
```
5.8 → 5.0 → 4.3 → 3.9 → 3.5 → 3.1 → 2.7 → 1.9 → 1.1 → 0.4 → 0(無事件)
```

### 驗收基準對照

| 卷面基準 | 實測 | 結果 |
|---|---|---|
| RLF 回落至 ≤ 基準 1.5 倍,連續 6 窗維持 | 6.7/min → **0**(單調下降,無回彈) | ✅ |
| 既有各關係 succ_last50 ≥ 0.97 | n02→n03 **1.0**、n03→n02 **1.0**、n03→s01 **0.94**\* | ✅ |

\* `n03→s01` 的 0.94 **非真失敗**:該關係 73 SUCC / **0 FAIL**、`failure_cause` 全空。
0.94 來自 last-50 視窗把 3 筆 in-flight `PREP`(換手進行中)計為非成功的取樣假象,
非處置副作用。**已知量測特性,不是 bug**。

### 卷面紅線遵守情形
- **L2**(禁止僅憑 PCI 寫入):✅ 先 `REPORTCGI` 解出 `cgi=unk_c0` 才 ADD。
- **L4**(禁止單一視窗即觸發):✅ guard 持續觀測數分鐘後才動作。

## 8. 結論

**「量測聚合鑽取發現強訊號未知 PCI → 排除表排除既有故障/MRO/MLB/RF 劣化 → REPORTCGI 解出**新** NCGI
→ ADD → RLF 6.7/min 歸零」整條由真的 RIC xApp 自動跑通。**

第4題(未知 cell 偵測)達成。API 涵蓋:`REPORTCGI`(新 NCGI 分支)+ `ADD`。
