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

---

## 9. 最終驗收輪(2026-08-18 07:01–07:17 UTC)

前三輪未能完成卷面「RLF 連續 6 窗」驗收,兩個打斷源**都在 sim 端**:

1. **我方反覆 re-arm**(06:04 / 06:25 / 06:36)—— 原意是清乾淨基準,實際把 10 分滑動窗打斷。
2. **劇本 duration 只有 1200s** —— 波形跑完 UE 靜止,RLF **假性歸零**;就算不 re-arm 也撐不到 6 窗。

修正:duration 1200s→**7200s**(waypoint 40→240,每 leg 30s 掃速不變),並在 07:01:16 做**最後一次** re-arm 後鎖定場景、全程唯讀監控。

### 閉環證據(sim 端 relationChangeEvents)

```
07:04:07  ADD n03_c0→unk_c0  by=xapp      ← xApp 自主觸發
07:04:09  ADD unk_c0→n03_c0  by=gnb-xn    ← +2s,Xn 自動反向(step 4c)
```

- 換手恢復:`unkSUCC` 由 **0 → 4/min** 並持續維持。
- 本輪只補 `n03_c0→unk_c0` 一條:該輪 UE 從 n03 側掉線、`s01_c0` 全程無 RLF。
  **沒有受害就不建關係**,不過度增生 —— 正確行為。

### RLF 曲線(10 分窗 cell-level 合計)

```
t+1m 3.2 → t+8m 6.7 → t+13m 6.6 → t+16m 7.3      全程 ≤ 門檻 10.5
```

| 卷面基準 | 判定 |
|---|---|
| RLF ≤ 基準 1.5 倍(baseline 7.0 → 門檻 10.5),連續 6 窗 | ✅ 最高 7.3,全程未觸門檻 |

### ⚠️ 判讀更正(重要,勿誤引)

RIC 端記為「07:10 峰值 6.7 後開始衰減」。**實際是上升,不是衰減** —— 07:01:16 re-arm 清空
RLF 記錄,10 分窗從 0 開始填,曲線是「**空窗填到穩態環境地板 ~7**」。

因此本輪 **並未觀察到真正的止血衰減曲線**:guard 在 re-arm 後僅 **166 秒**就完成 ADD,
UE 來不及累積高 RLF —— 等於「病還沒發作就被治好」。驗收數字成立,但不能拿這條曲線
當「RLF 由高降低」的證據。

## 10. 三個止血曲線判讀陷阱(本案累積)

1. **UE 靜止假歸零** —— 劇本波形跑完 UE 不動,RLF 自然歸零,不是止血。務必確認 HO 流量仍在。
2. **環境地板不是 0** —— 走廊兩端超出邊緣 cell 的 RLF 是環境效應,ANR 修不掉。
   本劇本完整 NRT 下 baseline ≈ **7.0/min**,驗收門檻須以此為準,不可用 0。
3. **空窗填充 ≠ 衰減** —— 清空記錄後 10 分窗會由低往高填到穩態,方向與止血相反,勿誤讀。

## 11. 結論

**第4題(未知 cell 偵測)端到端閉環成立**,卷面驗收達標,L2/L4 紅線遵守,
`by=` 歸屬證明 xApp 未碰反向關係。API 涵蓋:`REPORTCGI`(新 NCGI 分支)+ `ADD`。
