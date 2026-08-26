# ANR 驗測 Case #3:PCI 撞號(PCI Confusion)— sim 重現 + REPORTCGI 消歧

> 目標:重現 `ANR情境_v8.docx` 第 5 題「PCI 撞號」— 中央 gNB 的 UE 兩邊都量到 **同一個 PCI**,
> xApp 對該 PCI 做 CGI 解析會得到**多個 NCGI** → 判定 confusion → **不得逕行 ANR ADD**。
> 日期:2026-08-12。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

---

## 1. 問題(Problem)

真網 PCI 只有 1008 個,大網必然重用;規劃失誤時**相鄰**兩 cell 重用同一 PCI = confusion。
中央 gNB 的 UE 兩邊都量到 PCI=7 → 對 `(pci=7)` 做 CGI 解析得到**兩個 NCGI**(west_c7 / east_c7)
→ 無法唯一定位鄰區 → **xApp 必須拒絕 ADD**(否則加錯關係)。對應題型:第 5 題。

## 2. 劇本 `anr_pci_confusion`

| gNB | 位置 | cell | pci |
|---|---|---|---|
| west | (-600,30,0) | `west_c7` | **7** |
| mid | (0,30,0) | `mid_c0` | 0(UE 起始服務) |
| east | (600,30,0) | `east_c7` | **7** |

3.5GHz / 40MHz(west/east **同 arfcn** → ARFCN 也消不掉 = 真撞號)。conf_ue 在中央,兩邊都收到 PCI 7。

---

## 3. REPORTCGI 消歧(func6 / RC Style 9)

xApp 送 `RC_MEASCONFIG_REPORTCGI(pci=7)` → sim `cgi_resolve` 讀 CellConfig → 命中 2 cell →
RIC Control Acknowledge 的 `RICcontrolOutcome`(IE id=32,JSON)帶:

```json
{"physicalCellId":7,"arfcn":null,"results":{"east_c7":2,"west_c7":1},
 "unique":false,"confusion":true}
```

- `confusion=true` + `results` 多鍵 → **xApp 判定撞號,不 ADD**。
- 對照:`pci=0` → `{"results":{"mid_c0":3},"unique":true,"confusion":false}` → 可 ADD。

sim 端驗證(2026-08-12):
```
POST /CU/E2/Anr/cgi_resolve {pci:7} → results={east_c7:2,west_c7:1} unique=false confusion=true ✓
POST /CU/E2/Anr/cgi_resolve {pci:0} → results={mid_c0:3}          unique=true  confusion=false ✓
```
E2 路徑:`e2_control_actor._handle_reportcgi` 把 `confusion` 塞進 `control_outcome` → adapter 編進 ACK outcome。

---

## 4. RIC xApp 待做(閉環)

| 步驟 | 動作 |
|---|---|
| ① 觀測 | 某 cell 的 UE 量到某 PCI,NRT 無對應關係 → 想 ADD |
| ② 解析 | `RC_MEASCONFIG_REPORTCGI(pci=7)` → 讀 ACK outcome |
| ③ 判定 | `confusion==true`(results 多鍵)→ **停止 ADD**,記錄/告警(需人工或 O1 換 PCI) |
| 對照 | `confusion==false && unique==true` → 正常走 ADD(Case #1 路徑) |

**止血=「不加錯關係」**:撞號時逕行 ADD 會把換手導向錯 cell;正確行為是**偵測到 confusion 就不 ADD**。

---

## 5. 閉環驗證(2026-08-12 08:15:41 UTC · RIC dt-anr-xapp 0.0.10-measdisc)

```
DETECT  mid_c0 量到 pci=7 @120/min 但無關係(measurement-driven,非 RLF/HO 觸發)
RESOLVE REPORTCGI → confusion=true, results={east_c7:2, west_c7:1}
ACTION  ADD_SUPPRESSED + alarm  → sim NRT relation count=0(沒加錯關係)✓
對照組  pci=0 → {mid_c0:3} unique=true confusion=false ✓
```

- **關鍵**:此情境 pci=7 RSRP -79.5 vs serving -70.5,差 9dB **未觸發 A3** → 無 RLF、無 HO 失敗。
  必須靠 **measurement-driven** 偵測(不能等 RLF/HO 失敗信號)。該分支同時是 Case #1 的**預防版**
  (先 REPORTCGI 確認 unique 才 ADD,撞號就 suppress)。
- Alarm 可查:`GET http://<dt-anr-xapp>:8080/alarms`。

---

## 6. 結論

**「發現(measurement 量到未知 PCI)→ 解析(REPORTCGI)→ 判定 confusion → 抑制 ADD + 告警」
整條由真的 RIC xApp 自動跑通,sim NRT 維持 0 未加錯關係。** API 涵蓋:`REPORTCGI`(Style 9,confusion 分支)。
