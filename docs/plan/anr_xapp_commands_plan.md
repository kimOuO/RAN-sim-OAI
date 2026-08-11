# ANR xApp 命令實作計畫(E2SM-ANR)

來源需求:`docs/ANR情境_v8.docx`(xApp 由組態書寫者 → gNB SON 觸發者)。

## 鎖定決策(2026-08-11)
- **真實度 = A**:命令真實下發 + 模擬行為真的跟著變(非 stub、非純影子)。
- **承載 = 新 E2SM-ANR**,`ran_function_id = 6`,JSON 承載(比照 CCC),env `E2SM_ANR_ENABLE` gate。
- **起手範圍 = M0**(資料層+觀測);終點瞄準 A(行為接線)。
- feature branch:`feature/e2sm-anr`。

## A 級行為掛勾點(已確認)
`RANsim-CU/main/apps/cu_cp/services/optional/mobility/a3_handover_calculation.py`
`evaluate()` line ~113 的 neighbor 迴圈:挑 target 前查 `NrCellRelation`——
- 無關係條目(未 ADD)→ 不可作為 HO 目標(skip)
- `hoBlocklist=true` → skip
這是 A 級唯一接點,資料模型須支撐此查詢。

## xApp 命令 → 平台落差(全表見對話記錄)
觀測類:KPM_REPORT_SUBSCRIBE(有)、RC_MSGCOPY_*(無)、RC_E2NODEINFO_QUERY/SUBSCRIBE(無)、
RC_MEASCONFIG_REPORTCGI(無)、RC_MOBILITY_HO_CONTROL(有)。
SON 觸發類(自定 E2SM,要新增):ADD_REQUEST / REMOVE_REQUEST / FLAG_REQUEST / confirm。

## M0 資料模型設計(NrCellRelation / CgiResolution)

### NrCellRelation(CU, app_label=cu_cp)
| 欄位 | 型別 | 來源/語意 |
|---|---|---|
| source_cell_id | Char(64) idx | 本網轄下 cell(CellConfig.cell_id) |
| target_cgi | Char(64) idx | 目標 NCGI(§9.3.38 cgi) |
| target_pci | Int | §9.3.38 pci |
| target_arfcn | Int | §9.3.38 frequencyInfo/arfcn |
| target_rat | Char(8) default NR | §9.3.38 |
| target_plmn | Char(16) | 本網 |
| is_ho_allowed | Bool default True | 卷面延伸(管理面視圖) |
| is_remove_allowed | Bool default True | 卷面延伸(保護條目=False) |
| is_xn_allowed | Bool default True | 卷面延伸(NoXn) |
| xn_x2_established | Bool default False | §9.3.38 正式(gNB 加入後自建) |
| ho_validated | Bool default False | §9.3.38 正式(首次成功 HO 後 true) |
| ho_blocklist | Bool default False | flag(28.313 §6.4.1.3.5) |
| no_remove | Bool default False | flag |
| xn_blocklist | Bool default False | flag(NoXn 最強假設) |
| version | Int default 1 | §9.3.38 正式;每次變更 +1 → confirm 載體 |
| created_at / updated_at | DateTime | |
unique_together = (source_cell_id, target_cgi)

### CgiResolution(CU) — RC_MEASCONFIG_REPORTCGI 用
| 欄位 | 型別 |
|---|---|
| pci | Int idx |
| arfcn | Int idx |
| cgi | Char(64) |
| plmn | Char(16) |
unique_together = (pci, arfcn)

### 種子(開劇本時)
從 CellConfig 自動建初始 NRT:同 gNB / 同或鄰近 arfcn 的其他 active cell 互為鄰區關係,
`is_*_allowed=True, blocklist=False, xn_x2_established=True, ho_validated=false, version=1`。
CgiResolution 從 CellConfig(pci,arfcn)→cell_id/nr_cellid 建。

### M0 觀測 API(RC_E2NODEINFO_QUERY 落地)
`POST /api/v0.1/CU/E2/NodeInfo/read {cell_id}` →
`{servingCells:[...], neighbourCellRelations:[§9.3.38 欄位...], relationChangeEvents:[...]}`
(先 CU 端 HTTP;之後 M1 才經 E2SM-ANR/adapter 對 RIC。)

## 里程碑
- **M0**(本次):models + migration + 劇本種子 + NodeInfo/read query API。驗:query 拉到 NRT。
- **M1**:e2sm_anr_codec + E2 Setup 廣播 id=6(gate)+ adapter 解碼。驗:E2 Setup accepted 含 6。
- **M2**:ADD/REMOVE/FLAG → 改 NrCellRelation + version+1 + ACK。驗:xApp 下命令→表變→confirm。
- **M3**:E2NodeInfo subscribe(關係變更事件)→ confirm(ENTRY_PRESENT/ABSENT/FLAG_STATE)。
- **M4(A 級行為)**:A3 evaluate 讀 hoBlocklist/關係表 skip target;失敗原因計數器經 KPM。
  驗:封鎖後 UE 不再換到該目標 → demo 止血→體驗回升。

每步同步更新 `docs/api/e2_supported_commands.md`(新增 ANR 章 + §7 變更列)。
