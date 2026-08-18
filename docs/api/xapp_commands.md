# DT 平台 — xApp 能下的 E2 指令總覽(RIC 對接用)

> 給 RIC / rc-probe 團隊:目前 DT E2 node 支援、xApp **現在就能下**的所有 E2 指令。
> 分兩類:**控制類(不用訂閱,直接送)** 與 **訂閱類(要先訂閱)**。
> 節點:PLMN 208/95,gNB `gnbDT`(meid `gnb_208_095_000e00`)。E2 Setup `accepted=[2,3,4,5,6]`。

最後更新:2026-08-18

---

## 0. RAN Function 一覽(E2 Setup 廣播)

| ran_func | Service Model | OID | 用途 |
|---|---|---|---|
| 2 | KPM | `…1.2.2.2` | 量測訂閱 |
| 3 | RC | `…1.1.2.3` | 控制(HO / PRB / QoS / ReportCGI) |
| 4 | CCC | `…1.1.2.4` | cell 開關 / 節能 |
| 5 | FULLKPM | `…1.1.2.100` | 190 欄完整 PM 訂閱 |
| 6 | ANR | `…1.1.2.6` | SON 觸發(增/刪/旗標)+ 觀測 indication |

RMR:12040 CONTROL_REQ · 12041 CONTROL_ACK · 12042 CONTROL_FAILURE。
控制類編碼:RC 走 ASN.1(ranP);CCC / ANR 走 **JSON**(E2AP OCTET STRING 內)。

---

## A. 控制類 —— **不用訂閱,rc-probe 直接送 → 讀 ACK**

> 全部是 one-shot：送 RIC Control Request → 收 RIC Control Acknowledge。cell/CGI 一律用**字串**（`src_c0`/`nbr_c0`…）。

### A1. RC Handover(Style 3 / Action 1)· ran_func=3
- ranP:`1 = Target Primary Cell ID`(Structure{PLMN, NRCellId} 或 rc-probe 簡化的 valueOctS）
- 效果:UE 換手到 target cell。
- 觀察:CU log `E2 Control [Handover]`;`SessionController/list` UE 的 `serving_cell` 變。

### A2. RC PRB Quota(Style 2 / Action 6)· ran_func=3
- ranP:`1 = min PRB`, `2 = max PRB`, `3 = dedicated PRB`(比例)
- 效果:壓該 cell PRB 上限。
- 觀察:KPM `RRU.PrbTotDl` 掉、該 UE throughput 掉。

### A3. RC QoS flow(Style 1 / Action 2)· ran_func=3
- 需帶 UE 識別(ngap_id / f1ap_id)。
- 觀察:CU log `_handle_qos_flow_mapping`。

### A4. RC ReportCGI(Style 9 / Action 1)· ran_func=3 · **新**
- **PCI+ARFCN → 全域 CGI 解析**(ANR 鄰區發現用)。
- ranP:`1 = PCI`, `2 = ARFCN`, `3 = RAT`(選配)
- **回應在 RIC Control Acknowledge 的 `RICcontrolOutcome`(IE id=32)= JSON**:
```json
{"physicalCellId":30,"arfcn":633333,"cgi":"nbr_c0","plmn":"","unique":true,"confusion":false,"results":{"nbr_c0":3}}
```
- `confusion=true` = 同 PCI 撞多 cell,要靠 ARFCN 消歧。
- 觀察:sim adapter log `ReportCGI control decode: pci=…` + `ReportCGI outcome → cgi=…`。
- **測試值**:目前場景 `pci=30 → nbr_c0`、`pci=20 → src_c0`。

### A5. CCC cell 開關 / 節能 · ran_func=4 · JSON
Control Header:`{"controlHeaderFormat":{"ricStyleType":2}}`
Control Message:
```json
{"controlMessageFormat":{"listOfCellsControlled":[
  {"cellGlobalId":{"plmnIdentity":{"mcc":"208","mnc":"95"},"nRCellIdentity":"src_c0"},
   "listOfConfigurationStructures":[
     {"ranConfigurationStructureName":"NRCellDU",
      "newValuesOfAttributes":{"administrativeState":"LOCKED"}}]}]}}
```
- 硬開關:`administrativeState` LOCKED/UNLOCKED。
- 兩階段節能:`ranConfigurationStructureName:"O-CESManagementFunction"`, `newValuesOfAttributes:{"energySavingControl":"toBeEnergySaving"}` → 趕人(HO)→ 關 cell。
- 觀察:CU log `ES: cell … → isEnergySaving`;KPM 該 cell UE 數/PRB 掉 0。

### A6. ANR SON 觸發(ADD / REMOVE / FLAG)· ran_func=6 · JSON
Control Header:`{"controlHeaderFormat":{"ricStyleType":1}}`
Control Message:`{"controlMessageFormat":{"sonTriggerRequest":{ … }}}`

**ADD**(新增鄰區):
```json
{"requestType":"ADD","sourceCellId":"src_c0",
 "target":{"cgi":"nbr_c0","pci":30,"arfcn":633333,"rat":"NR","plmn":"20895"}}
```
**REMOVE**（移除;保護條目會被拒）:
```json
{"requestType":"REMOVE","sourceCellId":"src_c0","targetCgi":"nbr_c0","reason":"aging"}
```
**FLAG**（封鎖止血;會真的擋換手）:
```json
{"requestType":"FLAG","sourceCellId":"src_c0","targetCgi":"nbr_c0","flag":"hoBlocklist","op":"set"}
```
- `flag` ∈ `hoBlocklist`/`noRemove`/`xnBlocklist`;`op` ∈ `set`/`clear`。
- **⚠️ 反向關係不要自己寫**(卷面紅線)—— ADD 落地約 2 秒後,gNB 會經 Xn 自動建反向,
  `relationChangeEvents` 標 `by="gnb-xn"`(你們的是 `by="xapp"`,分得出來)。
- 效果:改 `NrCellRelation` + `version+1`;`hoBlocklist` 會讓 A3 換手略過該目標。
- **回應在 RIC Control Acknowledge 的 `RICcontrolOutcome`（IE id=32）= JSON**(ADD/REMOVE/FLAG 都帶):
```json
{"requestType":"REMOVE","sourceCellId":"main_c0","targetCgi":"ghost_c0","result":"REMOVED","version":null,"detail":""}
```
  - `result` ∈ `ADDED`/`REMOVED`/`FLAGGED`/`REJECTED_PROTECTED`/`NOT_FOUND`/`UNSUPPORTED`。
  - `REJECTED_PROTECTED` = 命中 `is_remove_allowed=False` 或 `no_remove=True`(保護條目,改由 SMO 決策)。
  - xApp 可直接從 ACK 的 `result` 即時分辨結果,不必等下一筆 indication。
- confirm:輪詢 `RC_E2NODEINFO`(或 func 6 indication）看 version/條目變化。
- 觀察:CU log `ANR ADD/REMOVE/FLAG …`;adapter `ANR control outcome → … result=…` + `ANR RIC_CONTROL_ACK sent`。

---

## B. 訂閱類 —— **要先下 RIC Subscription,sim 才週期推 Indication**

### B1. KPM 訂閱 · ran_func=2
- 標準 KPM Report Style 1,9 metrics(含 RSRP/SINR)。
- 訂閱後 sim 每 period 推 RIC Indication。

### B2. FULLKPM 訂閱 · ran_func=5
- 190 欄完整 PM(JSON+zlib）。對齊 `E2_data_example.md`。

### B3. ANR 觀測 Indication · ran_func=6
- **對 ran_func=6 下 RIC Subscription**(不是 control)→ sim 每 period 推一包 JSON,一次覆蓋 ANR 卷 §貳 的多個觀測命令。
- **文件命令 → func6 indication 塊 對映**(xApp 要哪個資料就讀對應塊):

| ANR情境_v8 §貳 命令 | func6 塊 | 內容 |
|---|---|---|
| `RC_E2NODEINFO_QUERY` / `SUBSCRIBE` | `e2NodeInformation` | servingCells + neighbourCellRelations(§9.3.38)+ frequencyRelations + relationChangeEvents |
| `confirm`(慣用式) | `e2NodeInformation.neighbourCellRelations[].version` / `relationChangeEvents` | version 變化 / 條目出現消失 |
| perNeighbourRelation KPM | `kpmIndication` | HO 速率 MM.HoExeAtt/Succ + handoverFailureCause |
| `RC_MSGCOPY_SUBSCRIBE_MEAS` | `e2MessageCopyAggregate` | RSRP 分位數(P50/P90/std) |
| `RC_MSGCOPY_SUBSCRIBE_REESTAB` | `rlfKpm` | RLF.DetectedRate / DropRate / ReEstabInbound + reestablishmentInboundByPreviousPci |
| `RC_MSGCOPY_SUBSCRIBE_MOBILITY` | `mroKpm` | HO.IntraSys.TooEarly/TooLate/ToWrongCellRate |

### B3-1. func6 indication 的新觀測欄位(2026-08-18)

| 欄位 | 位置 | 你們拿來做什麼 |
|---|---|---|
| `anrIntraEnabled` | `e2NodeInformation` | **前置檢查**。false = ANR 自動建立功能停用 → 只得 SMO_NOTIFY,不得自動 ADD(硬送會回 `REJECTED_ANR_DISABLED`)|
| `nrtCapacity` `{limit,used}` | `e2NodeInformation` | `used==limit` = NRT 滿載。配合 `ADD_REJECTED` 事件 → 判定阻斷點在容量(非偵測失效)|
| `sourceCellNcgi` / `bySourceCell` | `e2MessageCopyAggregate` 每列 | **決定 ADD/REMOVE 的 `sourceCellId`**。請讀欄位、不要寫死 —— UE 移動時受害 cell 會變 |
| `relationChangeEvents[].reason` | `e2NodeInformation` | `action=ADD_REJECTED` 時帶 `NRT_CAPACITY_REACHED` |

**行為面變更(會影響你們讀到的資料)**:
- **量測回報門檻**:sim 原本把所有 cell 照報,現在只回報達門檻的鄰區(對齊 38.331 reportConfig)。
  → 某些 PCI 的樣本會變稀疏或消失,這是刻意的。
- **`cellBarred`**:被標記的 cell **仍會被量測回報,但 UE 不會駐留**(重建落點排除)。
  ⚠️ 範圍:管閒置態選網/重建;**連線態換手不歸它管** —— 關係一旦建立,UE 換進去是正常的(修復成功)。

> **稀有事件注意**:RLF / MRO / HO 失敗是**偶發**事件,`rlfKpm`/`mroKpm` 是**滑動窗速率**(預設 10 min)。事件發生後超過窗就歸零 —— 這是正常滑動窗行為(對齊卷面 300s 窗)。xApp 要在事件發生後及時取樣 + 自算 baseline;用 CU HTTP 查也可帶 `{"window_min": N}` 放大窗涵蓋歷史事件。
>
> baseline / trend / hourlyProfile(O-RAN O1 管理面)= **xApp 自算,平台不提供**(卷面紅字規則)。

---

## C. 從頭測試一次(建議順序)

> 前置:sim 起一個含 UE 的劇本(HO/PRB/ES 要有 active UE 才看得到效果)。控制的 ACK 本身不需要 UE。

| # | 指令 | 類型 | 要訂閱? | 驗收 |
|---|---|---|---|---|
| 1 | **ReportCGI**(Style 9, pci=30) | RC 控制 | ❌ | ACK outcome `cgi=nbr_c0` |
| 2 | **ANR ADD**（src_c0→nbr_c0) | ANR 控制 | ❌ | ACK + NRT 出現關係 |
| 3 | **ANR FLAG** hoBlocklist set | ANR 控制 | ❌ | ACK + version+1;A3 不再換到 nbr_c0 |
| 4 | **ANR REMOVE** | ANR 控制 | ❌ | ACK + NRT 關係消失 |
| 5 | **RC Handover** | RC 控制 | ❌ | UE serving_cell 變 |
| 6 | **RC PRB Quota** | RC 控制 | ❌ | KPM `RRU.PrbTot` 掉 |
| 7 | **CCC** LOCKED / ES | CCC 控制 | ❌ | cell 關 / 節能 |
| 8 | **KPM 訂閱** | 訂閱 | ✅ | 收 Indication(RSRP…) |
| 9 | **FULLKPM 訂閱** | 訂閱 | ✅ | 收 190 欄 |
| 10 | **ANR func6 訂閱** | 訂閱 | ✅ | 收觀測包(NRT/kpm/rlf/mro/meas) |

**1~7 全部不用訂閱,rc-probe 直接送就能測。** 只有 8~10 要先下 RIC Subscription。

> **10/10 全部通過(2026-08-12)**:1 ReportCGI ✓ · 2-4 ANR ADD/FLAG/REMOVE ✓ · 5 HO ✓ · 6 PRB(-68%)✓ · 7 CCC LOCK(CU+DU 兩層 disabled)✓ · 8-10 KPM/FULLKPM/func6 訂閱 ✓。ACK 路由 4/4 全通(dt-anr / dt-fullkpm / mobiflow / 直達 rc-probe 都收得到)。

---

## D. 現場資訊(⚠️ 場景會變,測前必問當前值)
- **cell / PCI 隨場景切換而變**,不要用寫死的舊值。測前**跟 sim 要當前 pci**,或讀 func6 indication 的 `e2NodeInformation.servingCells[].physicalCellId`。
- 例:曾出現 `src_c0`(pci20)/`nbr_c0`(pci30);也出現 `das1_c0`(pci0)/`das1_c1`(pci1)。**REPORTCGI / HO target / CCC cell_id 都要用當下場景的值。**
- 測試期間場景要**釘住**(不要並行起別的劇本),否則命令會打到不存在的 cell(如 4d 曾因 das1_c1 被切走而 DU 回 404)。
- A3 自動換手預設可能開;要看「HO 停住」請先請 sim 關 A3(`Mobility/A3Controller/set {enabled:false}`)。
- sim 端全程開監控,逐項回報「收到 / 解對 / ACK 對 / 效果對」。
