# Agent 手冊:從挑劇本、啟動、讀觀測到下命令(DT + RIC 合併版,2026-09-28 多 gNB)

取代 2026-09-23 版。對應版本:DT 多 gNB 版(`docs/architecture/multi_gnb_plan.md`)、RIC rtmgr 0.9.7-mit2 / submgr 0.10.4-mit1 / dt-preproc 0.1.7 / rc-probe(rc, anr, ccc 皆帶 IE 20)。
實證:多 gNB 驗收 7–18 全數通過(2026-09-27:run 4–7、並行兩場、節能補驗);單 node 時期的 run 40–45 結論仍適用。

**多 gNB 一句話**:場域裡每個 gNB 是一個獨立的 E2 node(自己的 CU、meid、gen);cell 識別走 3GPP 規則;gNB 之間有 Xn,UE 可跨 gNB 換手;
命令要送到「該 cell / 該 UE 所在」的 node。識別規則見 `Agent介面總覽_2026-09-28.md` §零。

```
 Agent ──I-1/I-2 挑劇本──► DT orchestrator ──I-3 啟動──► RAN(cu/du/ru/ue 容器) ──E2──► RIC
 Agent ◄──I-4/I-6/I-7 狀態/事件/變更── DT                                          │
 Agent ◄──I-5 GET /observation──────────────────────────────────── ric-scenario-gw ◄┘
 Agent ──POST /control────────────────────────────────────────────► ric-scenario-gw ──rc-probe──► E2 ──► RAN
```

一句話分工:**劇本與注入在 DT(I-1~I-4、I-6、I-7),觀測與控制在 RIC 閘道(I-5、/control)。** Agent 不碰 InfluxDB、不碰 E2;下命令用 `nodeId`(gNB 名稱),meid 只在查 gen 時用到(由 I-2 或閘道 `/v1/scenarios/{id}` 取得)。

---

## 第一部分:DT 端(劇本、啟動、事件、稽核)

Base:`http://<DT>:8302/api/v0.1/Run_orchestrator/Agent_api/`,全 **POST + JSON**;回應 `{"success", "message", "data"}`。
時間:`offset_s` = 劇本秒(自起點);`ts_iso` = 對映牆鐘 UTC。倍速:走廊 cached 場標 10x、實測約 4.7x。

### 1. 挑劇本 —— I-1 `FieldReader/list`
`{"category": "corridor"}`(可選 `ready_only: true`)。
**分類目前只有兩種在用:`corridor`(走廊)與 `other`(室內 live 測試場)**;`anr / intent / scale` 是預留值、尚無場域。ANR 題型全部由走廊場 + I-3 事件製造(見 §3 表)。

| name | 區塊 | gNB / cell / UE | 模式 | 事件 |
|---|---|---|---|---|
| corridor24_00_08 / 08_16 / 16_24 | 1 / 2 / 3 | 3 / 3 / 18(每 gNB 一顆 cell) | cached(≤10x) | cell_outage, energy_saving_state, tx_power_change, relation_change, pci_change |
| livetest_corridor | 4 | 見 I-2 | live(≤2x) | 上述 + cell_addition, antenna_change |

每筆另附 **`e2_identities[]`**:每個 gNB 的 `node_id`(= 閘道 nodeId)、`meid`、`gnb_id_bits`、cell 的 NCI 與 ncgi —— 啟動前就能部署 xApp。

每筆附 `config_version`、`event_types`、`event_param_schema`(照它組 I-3 的 params)、`load_profiles`(人流寫定,`ue_count` 只能往下裁)。

### 2. 看設定 —— I-2 `FieldReader/config`
`{"field_id": "scene-…"}` → `cells[]`(cell_id / ran_cell_id / **所屬 gNB `gnb_id` 與 E2 node `ran_name`** / **ncgi 字串 / nr_cell_identity 數值** / pci / arfcn / 功率 / 位置 / 天線 / 狀態)、`e2_identities[]`(每 gNB 一筆)、`son`(**實際生效**的 SON 開關)、`collection`、`unavailable_fields`。
- cell 識別三種寫法 I-3 都收:`"src"`、`"e20:src"`、`"208095-003880000"`。
- **`3-1` / `2-8` / `3-1-group` 要的數值 `target_nci` 直接取 `cells[].nr_cell_identity`**;目標可以是別的 gNB 的 cell(跨 gNB 換手)。
- NCI = gNB ID << 14 | local_cell_id,**從 NCI 就看得出屬於哪個 gNB**(右移 14 位)。
- **UE 座標永遠沒有**(設計決定)。

### 3. 啟動 —— I-3 `ScenarioController/run`(唯一可寫)
```json
{"field_id": "scene-…", "config_version": "405c36afe21f", "seed": 103, "duration_s": 1800,
 "ue_count": 18, "requester_task_id": "…",
 "son": {"anr_auto_add": false, "anr_pci_lookup": true, "anr_cgi_fail_rate": 0.0},
 "events": [{"event_id": "E1", "type": "relation_change", "at_offset_s": 60, "duration_s": null,
             "target": "e20:src", "params": {"action": "add", "source_ncgi": "e20:src", "target_ncgi": "e22:mid"}}]}
```
- `seed`、`duration_s`(≥720)必填;`ue_count` 只減不增;`magnitude` 收下不作用。
- **`son` 與 `events` 都是啟動時決定、整場固定**;事件在 `at_offset_s` 那個劇本秒由排程器執行,`duration_s` 到期自動還原(outage / es / cell_addition / pci_change)。**沒有跑到一半改設定的介面。**
- 回應:`run_id`(= I-4/6/7 的 run_id = **RIC 閘道的 scenarioId**)、`instance_id`、`echo`(實際生效值含 `son`、`ue_names`、`speed_x`)、`unavailable_fields`。
- 錯誤:400 驗證(逐筆 event_id 原因 + `supported_types`)、404、409(config_version 不符 / 場域正在跑)、503(RIC 閘道不在)。

| 事件 | params | 效果 |
|---|---|---|
| `cell_outage` | `reason?` | DU 停排程 + RU 停發射 |
| `energy_saving_state` | `state_after: energySaving\|notEnergySaving` | 同上開關 |
| `tx_power_change` | `tx_power_dbm_after` | RU 功率 + PEE 輸入 |
| `relation_change` | `action: add\|remove\|set`, `source_ncgi`, `target_ncgi`, `attributes?` | CU NRT,與 xApp 同入口 |
| `pci_change` | `pci_after` 0~1007 | 只改廣播 PCI 標籤(訊號不變)→ 與另一顆相同 = 混淆 |
| `cell_addition` | `tx_power_dbm?` | 只能開備用 cell |
| `antenna_change` | `tilt_deg_after`, `azimuth_deg_after` | live 限定 |

**ANR 題型對照**

| 題型 | I-3 設定 | RIC 端會看到 |
|---|---|---|
| 缺漏鄰區 | `son.anr_auto_add=false`(走廊預設即關,開場 NRT 空);或 `relation_change add`@60 s → `remove`@1200 s 造窗 | 量測有 PCI 但 `ncgi` 缺席、`neighbourCellRelations` 沒那條、換手做不了 —— **多 gNB 下 UE 只能 RLF 後跨 gNB 重建** |
| 錯誤/多餘鄰區 | `relation_change add` 一條收不到訊號的關係 | 關係表有、`measurementReportAggregate` 沒有 |
| 關係旗標錯 | `relation_change set` + `attributes` | `hoValidated` / 換手率異常 |
| PCI 混淆 | `pci_change` nbr → 與 mid 同 PCI(A:`anr_auto_add=true`;B:false + guard) | `servingCells` 兩顆同 PCI、該 PCI 量測率跳升、`ncgi` 覆蓋率掉到約一半、rsrp 上移 |
| cell 停機/節能 | `cell_outage` / `energy_saving_state`(+`duration_s`) | 關係還在、目標無訊號 |

### 4. 狀態 —— I-4 `RunReader/status`
`{"run_id"}` → `status`(running / done / failed / stopped)、`progress_s`、`duration_s`、`windows_available`、`events{total, pending, alive, deadline_s}`、`ue_names`。`done` = 劇本秒到 `duration_s` 由 DT 停止。

### 5. 事件 —— I-6 `RunReader/events`
`{"run_id", "from"?, "to"?, "types"?}`;型別 `meas_report, ho_exe_succ, ho_exe_fail, ho_prep_fail, rlf, rrc_reestab_req, cgi_resolution`。
每筆 `{type, offset_s, ts_iso, gnb_id, cell_id, ue_id, node_id, meid, ric_triggered, ric_label, ric_instance_id, payload}`;`meas_report.payload.reported[]` 以 `pci/arfcn/rsrp/rsrq` 為準。
換手 payload 有 `ho_type`(`intra-DU` / `inter-DU` / `Xn` / `NG`)、`source_ncgi` / `target_ncgi`、`ngap_id`(**跨 gNB 不變**)。**跨 node 移動 = Xn/NG 換手 + RLF 後在別的 gNB 重建**(`rrc_reestab_req` 屬落點的 node),兩種都要看。

### 6. 變更稽核 —— I-7 `RunReader/config_changes`
`{"run_id", "from"?, "to"?, "origin"?}`;每筆 `{offset_s, ts_iso, origin, source, object_type, object_id, action, outcome, before, after, reason}`。
- 每筆另有 `node_id`、`meid`、`ric_triggered`、`ric_label`、`ric_instance_id`、`ric_requestor_id`。
- `source` 前綴:**`agent/*`** = 你自己的 I-3 事件;**`ric/*`** = RIC/xApp 控制(`outcome` = ACK / FAIL / pending);**`son/*`** = gNB 自主(ANR 自動加關係、CGI 解析)與 RIC 命令落地(`son/ric_apply prb_quota_applied`)。
- **與 RIC 稽核對帳**:IE 20(E2AP RICcallProcessID)上的是閘道改寫後的 `<scenarioId>|<nodeId>|g<gen>|<呼叫端 label>`,I-7 `ric_label` 就是這個字串;RIC `control_audit` 則把四段分開存(標籤 `scenario`、`nodeId`,欄位 `gen`,`label` = 呼叫端原始 label)。join:把 `ric_label` 拆四段逐一對;或用 `ric_instance_id` 對 `control_audit` 的 `instance_id`(rc-probe 重啟後從 1 重來,要連 run 一起比)。2026-09-27 以前的場次這幾欄是空的(已修)。
- 跨 gNB 的反向關係由對方 gNB 經 Xn 自建,記在**對方 node** 的列。

---

## 第二部分:RIC 端(觀測與控制)

閘道:叢集內 `http://ric-scenario-gw.ricplt:8080`,叢集外 `http://<RIC IP>:30990`。**所有資料經閘道進來、所有命令經閘道出去。**

### 7. 部署形態
| 形態 | 用途 | 部署 |
|---|---|---|
| A. 叢集內 Deployment(推薦) | 常駐自動決策(範例 dt-exec) | helm chart 放 `components/<name>/charts`,`bootstrap/versions.env` 加 `<NAME>_IMAGE`,`40-apps.sh` 加一行 helm;不需 RMR、不需註冊 appmgr |
| B. 叢集外程序(LLM Agent) | 實驗、腳本 | 直接打 NodePort;程式碼與 A 相同,只差 URL |
| C. 真正 E2 xApp | 自己訂閱 E2 | 另見 RIC `xApp開發規範`,本手冊不涵蓋 |
紀律:動叢集前跑 `ric-deploy-gate.sh`(RAN 有 run 就不動);換映像改 `values.yaml` + `helm upgrade --reset-values`,不要 `--set image.tag=`。

### 8. 讀觀測 —— I-5
| 方法 | 路徑 | 用途 |
|---|---|---|
| GET | `/v1/scenarios` | 活著的場景清單(入口):`scenarioId`(= DT `run_id`)、`run`、`state` |
| GET | `/v1/scenarios/{id}` | 單場景:`nodes{}`、`labels.scene_name`、`allowedStyles`、`xappNames` |
| GET | `/v1/scenarios/{id}/observation` | **主要讀口**。`format=aggregated`(預設,一份 = 最新 60 s 窗)/ `raw`(逐份 E2 報告,正序分頁 `page_size`、`next_token`、`from/to`)/ `both`;`run=N`;`at=<epoch ms>` |
| GET | `/v1/scenarios/{id}/series?db=&measurement=&run=&since=&limit=` | 直接讀某 measurement(含 `dt_preproc.control_audit` 稽核表) |
| GET | `/v1/nodes/{meid}` | 節點目前 `gen`(**下命令前必查**;多 gNB 每個 node 各自一個 gen) |

彙整格式頂層:`window{sceneTimeStart, sceneTimeEnd, reports, qualifiedForBaseline, reason}`、**`controlTargets[]`(空 = 不能下命令)**、`e2NodeInformation{servingCells[], neighbourCellRelations[]}`、`ueLevel[]{ueId, ngapId, servingCellNcgi, handoverInWindow, rsrp/sinr/throughput p50, controllable}`、`kpmIndication{cellLevel{"<量測>.<cell>": {current, baseline?, trendLast30Min}}, perNeighbourRelation[]}`、`e2MessageCopyAggregate{measurementReportAggregate[], reestablishmentInboundByPreviousPci[]}`、`unavailable_fields`。

語意:
- 一列 = 60 s 窗、時戳為窗**結束**,約 15 s 寬限後出現;場景 active 後約 90 s 才有第一窗(`404 no-observation` 不是錯)。
- `baseline` 是前 6 個合格窗中位數,約第 11 窗起才有;**你自己的命令會讓那窗 `control(n)` 不進基準**。
- `ncgi` 在彙整格式是 **cell 名**(`e20:src`),ran_func 5 與 6 一致;數值另有 `nci` / `ncgiStd`(關係另有 `targetNci` / `targetNcgiStd`),或查 **DT I-2**。
- cell 級與關係級每筆帶 `nodeId` / `meid`;`controlTargets[]` 每個 node 一筆。
- 鄰區以 **PCI@ARFCN** 為鍵;`ncgi` 只在 gNB NRT 恰好解出一顆時才附;兩顆同 PCI 同時可見 → 合併一筆、**不附**。
- `RRU.PrbTotDl` 是 ran_func 6 cell 級值、每窗最後一筆(與 DT 每秒峰值不同量)。
- `ueLevel[].ngapId` 是 `3-1` / `2-6` 的 UEID(AMF UE NGAP ID,跨 gNB 不變);`controllable=false` 下不了;`servingCellNcgi` 是該窗眾數,`handoverInWindow=true` 的 UE 執行時可能已不在那顆,**甚至已不在那個 node**。
- `position` 永久沒有。

### 9. 下命令 —— `POST /v1/scenarios/{id}/control`
Header `X-Scenario-Gen: <GET /v1/nodes/{meid} 現查的 gen>`(**查的是 nodeId 對應那個 node 的 gen**);body 共通 `{"style", "nodeId": "<gNB 名稱,如 nbr>", "label": "<前綴>-<動作>-<目標>", "wait_ack": true, "wait_timeout": 8, …}`,**不帶 meid**(一律 400);`nodeId` 在場景有 ≥2 個 node 時必帶(否則 422 nodeId-required),單 node 場景可省略(閘道用唯一那個)。

**命令送到哪個 node**:
- UE 級(`3-1`、`2-6`):送到 **UE 目前的服務 node**(`ueLevel[]` 的服務 cell 所屬 node)。`3-1` 的 `target_nci` 可以是別的 gNB 的 cell —— 那就是跨 gNB 換手(Xn,Xn 不通時依設定走 NG 或回 TXnRELOCprepExpiry)。
- 依欄位分兩類(閘道 R2):
  - **source 類**(`sourceCellId`、`cell_id`、`serving_cell`):必須是被點名 node 的服務中 cell,否則 422。所以 `anr-*`、`ccc-*`、`3-1-group` 要送到**來源 cell 所屬的 node**。
  - **target 類**(`anr-add` 的 `target.cgi`、`anr-remove` 的 `targetCgi`、`3-1` / `3-1-group` / `2-8` 的 `target_nci`):**可以指向同場景另一個 node 的 cell**,閘道放行、由 CU 走 Xn。跨 gNB 鄰區送到**來源**那個 node,不是目標的 node。
- `3-1` / `3-1-group` / `2-8` 的 `target_nci` **必填**(rc-probe 400 target_nci-required);`2-6` 的 `ranP[4]` 目標 cell 選配。
- `2-6` 帶 `ranP[4]` 目標 cell 時,cell 必須屬於這個 node,否則 RAN 回 FAILURE(`not served by this E2 node`)。
- `anr-add` 的目標可以是別的 gNB 的 cell(`target.cgi` 用 cell 名或 ncgi 字串);**反向關係由對方 gNB 經 Xn 自建,不要替對方下**。
回應 `{"resolvedMeid", "audited", "rcProbe": {"ack": "ACK"|"FAILURE", "rmr_state", "instance_id", "outcome", "error", "detail"}}`。
**判定順序**:HTTP≠200 閘道拒 → `rcProbe.error` 有值沒送出 → `rmr_state≠0` RMR 沒送 → `ack=="FAILURE"` RAN 拒 → `"ACK"` 成功。閘道會擋:`422 style-required`、`403 style-not-allowed`、`400 bad-generation`、`409 scenario-not-active / ran-not-connected`。

| style | 類別 | 參數(鍵名照 rc-probe) | 從哪拿 |
|---|---|---|---|
| `rc-reportcgi` | 唯讀 | `pci`, `arfcn` | `servingCells[]` / `measurementReportAggregate[]`。回 **cell 名**;鄰 gNB 的 PCI 也解得出來(Xn Setup 交換的 served cells)。混淆時回 `cgi=null, confusion=true, results{兩顆}` |
| `anr-add` | ANR | `sourceCellId`, `target:{cgi, pci, arfcn, rat:"NR", plmn:"208095"}` | cell 名 `servingCells[].ncgi`;**pci/arfcn 要帶**(只帶 cgi 時 RAN 會用本地設定補) |
| `anr-remove` | ANR | `sourceCellId`, `targetCgi`, `reason` | `neighbourCellRelations[]` |
| `anr-flag` | ANR | `sourceCellId`, `targetCgi`, `flag`∈hoBlocklist/noRemove/xnBlocklist, `op`∈set/clear | 同上 |
| `2-6` PRB 配額 | RC UE 級 | `ngap_id`, `min_prb`, `max_prb`, `dedicated_prb` | `ueLevel[].ngapId`;RAN 落地後 DT I-7 會有 `prb_quota_applied` |
| `3-1` 換手 | RC UE 級 | `ngap_id`, `target_nci`(數值), `target_plmn_hex`("02f859") | `target_nci` ← DT I-2 `nr_cell_identity`(或 raw `neighbors[].ncgi` 反查) |
| `3-1-group` | RC cell 級 | `serving_cell`, `pci`, `target_nci`, `target_plmn_hex`, `cond_arfcn?` | 同上 |
| `2-8` 波束 | RC cell 級 | `target_nci` + `tilt_decideg` / `beams` / `max_layers` / `txru_pct` / `beam_window` / `beam_power` 至少一個 | 同上 |
| `ccc-lock` / `ccc-unlock` / `ccc-es-on` / `ccc-es-off` | CCC | `cell_id`(完整 cell 名 `e21:nbr`) | `servingCells[].ncgi`。`es-on`:cell 先進 `toBeEnergySaving`(**不再收新 UE**),把 UE 趕到其他 cell(本 gNB 沒有就經 Xn 趕到鄰 gNB),清空才關、轉 `isEnergySaving`;`es-off` 開回 |

### 10. 執行 xApp / Agent 內部必須有的(RIC 端踩坑清單)
1 只有一個資料入口(`/observation`);2 每個 (scenarioId, run, timestamp_ms) 只處理一次;3 `controlTargets` 空就不做;4 `404 no-observation` 要等不報錯;5 gen 送前現查;6 body 不帶 meid;7 判定看三層、`ack` 是字串;8 參數鍵名照 rc-probe(錯鍵會用預設值送出);9 目標冷卻 600 s + 每窗上限 3;10 `handoverInWindow=true` 的 UE 不拿來下 UE 級命令(或標明在賭);11 同 PCI 對到兩顆 cell → 不推目標;12 沒有的資料就不做、不從別處補(曾掃出假 NCI)。
留痕:每筆決策帶 evidence;`label` 固定前綴;提供 `/status`;要有 `DRY_RUN` 開關(只觀察的場先切)。

---

## 第三部分:一場的標準流程

1. `I-1` 挑 `category=corridor` 的場 → `I-2` 記下 `config_version`、`e2_identities[]`(nodeId ↔ meid)、cell 的 `ncgi`/`nr_cell_identity`/`pci`/`arfcn`/所屬 gNB、`son` 現值。
2. `I-3` 啟動(帶 `seed`、`duration_s`、`son`、`events`)→ 拿 `run_id`。
3. RIC `GET /v1/scenarios/{run_id}` 等 `state=active`;約 90 s 後 `GET …/observation` 有第一窗;基準約第 11 窗。
4. 迴圈:讀 observation → 規則 → 決定目標 node(UE 的服務 node / cell 所屬 node)→ `GET /v1/nodes/{該 node 的 meid}` 取 gen → `POST …/control`(帶 `nodeId`、label)→ 看 `rcProbe.ack`。
5. 隨時 `I-4` 看進度;`I-6` 看事件;**`I-7` 看誰改了什麼**(自己的 `agent/*`、RIC 的 `ric/*`、gNB 的 `son/*`),與 RIC `control_audit` 以 `ric_label`(拆四段)或 `ric_instance_id`(連 run)對帳。
6. `I-4 status=done` 收工;歸檔資料保留一輪(下一場啟動時清上一場之前的)。

## 附:DT 端變更(2026-09-28 晚)
- I-6 `meas_report.reported[]` 已移除 `cell_id`;`rrc_reestab_req.previous_ncgi` 改為 ncgi 字串(cell 名另放 `previous_cell_id`)。
- `3-1` 單 UE 換手**沒成**(如 TXnRELOCprepExpiry、CellNotAvailable、RandomAccessProblem)時,RAN 回 **RICcontrolFailure**(cause ricRequest/unspecified),outcome(IE 32)帶 `{"result":"HANDOVER_FAILED","failureCause":…}`;以前回 ACK。`3-1-group` 維持 ACK + REJECTED/PARTIAL。
- 節能 `toBeEnergySaving` 期間 cell 也拒收 UE 的第一次接入(RRC Reject),UE 改接其他 cell。
- RIC 端 guard 與 `anr_auto_add` 解耦:關 gNB 自主 ANR 不會再連帶關 guard。
- 2026-09-27 以前場次的 I-7 `ric_*` 欄位是空的。
- 前端沒有事件注入面板;人工測試請直接打 I-3。
