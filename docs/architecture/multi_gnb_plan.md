# 多 gNB 架構改版計畫(方向 B)—— v2(雙方確認)

> 狀態:**v2,RIC 端 anr_xapps [47006d] 已於 2026-09-27 確認**(C1–C15、D2、D3 同意;D4 順序依 RIC 修正;R1–R8;驗收 1–18)。
> DT 端依本計畫開工。RIC 端 R1–R8 的開工時間由 RIC 端使用者決定,另行通知。
> 起草:DT 端,2026-09-27。依據:DT 全元件盤點(CU、DU、RU、UE、e2adapter、orchestrator、registry、前端、文件),
> 以及 RIC 端 anr_xapps [47006d] 的查證回覆(2026-09-27,閘道、xApp、R-NIB、rtmgr、observation)。

## 1. 目標與不做的事

**目標:** 一個場景裡的每個 gNB 都是真正獨立的 gNB。

- 每個 gNB 有自己的 CU、自己的 E2 node、自己的 gNB ID。RIC 對一個場景看到 N 個 E2 node。
- 一個 CU 可以接多個 DU(F1),支援同 gNB 跨 DU 換手。
- gNB 之間走真的 Xn:Xn Setup、換手準備、SN 狀態轉交、UE Context Release、重建時取回 UE context。
- 全場共用一個 AMF,做 NG Setup、UE 註冊、Path Switch;沒有 Xn 時可退回 NG-based 換手。
- 無線環境(通道、跨 cell 干擾)仍然全場一起算,結果與拆分前一致。
- 單一 gNB 的場景行為不變(退化成 1 CU + 1 DU)。

**不做:** 真實 SCTP/ASN.1 的 F1、Xn、NG(三者沿用 HTTP + JSON,與現行 F1 一致);CU-CP/CU-UP 拆成不同容器。

## 2. 目標拓撲(一場)

```
                 ┌──────────── AMF(新,全場 1 個)────────────┐
                 │ NG Setup / UE 註冊 / Path Switch / NG HO   │
                 └───────┬──────────────┬──────────────┬──────┘
                         NG             NG             NG
   RIC ◀─E2─ e2adapter-g0   e2adapter-g1   e2adapter-g2      (每個 gNB 一個 E2 node)
                 │              │              │
               CU-g0 ◀──Xn──▶ CU-g1 ◀──Xn──▶ CU-g2           (每個 gNB 一個 CU)
              F1│  │F1        F1│            F1│
            DU-a  DU-b         DU-c           DU-d            (每個 DU 一個容器)
               └────┴────FAPI───┴──────────────┘
                         RU / 空中介面(全場 1 個,含時鐘)
                         UE(全場 1 個)
```

| 角色 | 數量 | 命名 |
|---|---|---|
| amf | 1 | `amf-<rid>` |
| cu | 每個 gNB 1 | `cu-<rid>-<g>` |
| e2adapter | 每個 gNB 1 | `e2adapter-<rid>-<g>` |
| du | 每個 DU 1 | `du-<rid>-<d>` |
| ru | 1 | `ru-<rid>`(兼任全場時鐘) |
| ue | 1 | `ue-<rid>` |

`<g>`、`<d>` 用 registry 的 gNB、DU 序號。

## 3. 需要先定案的決策

### D1 全場時鐘:鎖步,由 RU 驅動(DT 內部)

**問題:** 現在時鐘在唯一的 DU 裡。多個 DU 各自計時會漂移,而跨 cell 干擾需要所有 cell 在同一拍的負載。

**決定:** RU 當全場時鐘。每一拍:
1. RU 對所有 DU 平行發出「跑第 k 拍」。
2. 各 DU 完成排程,回傳本拍 DL TTI 與各 cell 的下行、上行負載。
3. RU 用全場的負載與全部 UE 一次算完空中介面(DL 干擾、UL 干擾、live 模式合併成一次射線追蹤),把各 UE 的量測分回對應 DU。
4. 場景時鐘 +sim_dt。

DU 改成「由外部驅動」模式,不再自己計時。UE、orchestrator、事件排程改讀 RU 的時鐘。
DU 的 in-process SINR 改讀 RU 公布的**全場**上一拍負載(與現在一樣是一拍延遲,但涵蓋所有 cell)。

### D2 cell 標籤與 NCI(請 RIC 確認)

- **cell 標籤改成每個 gNB 各自的前綴**:`<gNB 槽位低 12 bit>:<名稱>`,例 `e11:src`、`e12:mid`。看標籤就知道屬於哪個 gNB,且全場唯一(RIC observation 的 cell 鍵要求全場唯一)。
- **NCI 改成 3GPP 定義**:NCI(36 bit)= gNB ID(22 bit)‖ 本地 cell ID(14 bit),取代現在對名稱做 SHA-1。好處是從 NCGI 就能算出目標 gNB,Xn 路由與 RIC 端都能直接用。
- **影響:** 所有 cell 的 NCI 值會改變。RIC 已確認執行期沒有快取或寫死的 NCI;寫死的只有測試腳本與 rc-probe 預設值,列入 R7、R8。
- **ncgi 字串格式固定:** `<PLMN 6 位>-<NCI 9 位十六進位,小寫,零填補>`,例 gNB 0xe31 的本地 cell 1:NCI = 0xe31 << 14 | 1 = 0x0038c4001 → `208095-0038c4001`。DT 所有輸出(E2、Agent API、歸檔)一律照此格式,雙方以字串比對。

### D3 E2 槽位與 gNB ID(依 RIC 建議:每個場景一段連續區塊)

- **區塊:** 每場配一個區塊號 b(**1–15**),區塊大小 16。第 i 個 gNB(registry 順序,i = 0–15)的槽位 = 16·b + i,
  gNB ID = 0x000e00 | 槽位,E2 node 名稱 `gnb_208_095_000eXY`(X = 區塊、Y = gNB 序號)。例:區塊 1 → e10、e11、e12;區塊 2 → e20、e21、e22。
- **e00 保留**給 RIC 常駐 xApp 的共用節點,區塊 0 不配。**b 限 1–15**:b ≥ 16 時 0xe00|0x100 = 0xf00,meid 與 cell 前綴會變成 f 開頭,命名不一致。上限:一場最多 16 個 gNB、同時最多 15 場。
- **gNB 序號必須穩定:** registry 新增 `Gnb.e2_index`(0–15,場景內唯一),不依建立順序或名稱排序推算。
- **釘選:** `Scene.e2_slot` 改名語意為「區塊號」(`e2_block`)。Agent 用的場景釘區塊;未釘的場景開場時動態配區塊。
- **注意:** 現有釘選場景(e01–e04)的 meid 會改變(例 e03 → e30、e31、e32),Agent 與 RIC 文件要同步更新。

### D4 RIC 場景閘道(RIC 已確認現有設計支援)

- register 的 `nodes` 改為**陣列**,每個 gNB 一筆:`{"nodeId": "<registry gNB 名稱>", "meid": "gnb_208_095_000eXY", "plmn": "02F859", "gnb_id_bits": "<22 位元>"}`。
- **順序:** 先向閘道綁定所有 node,**之後**才啟動 e2adapter 做 E2 Setup。否則 RIC 常駐 xApp 會接手未綁定的 meid。
  → orchestrator 開場順序改為(依 RIC 修正):**配區塊 → register 綁全部 node → POST /xapp 部署 xApp → 起 AMF、CU、DU、RU、UE → 起 e2adapter 做 E2 Setup → 等全部 node CONNECTED 且每個 meid 都有訂閱 → activate**。
  xApp 早於 E2 Setup 部署沒有副作用(訂閱迴圈等 node CONNECTED 才建);先部署才能讓 activate 的 warnings 為空、第一個視窗就有資料。
- activate 要求所有 node 都 CONNECTED(閘道現行行為,不改)。
- 控制 API:多 node 時 body 必帶 `nodeId`(閘道現行行為)。Agent 文件的固定 `"nodeId": "cu"` 改為 gNB 名稱。
- 停止:閘道 DELETE 會逐 node 清 R-NIB;DT 的停止通知也逐 node 送。

### D5 PLMN 與 gNB 層參數

- PLMN、A3、RLF 計時器、ANR 政策改為**每個 gNB 各自設定**,由 registry 的 gNB 讀入,各自注入對應 CU(現在 PLMN 寫死 208/95、A3 只取第一個 gNB)。
- gNB 模板收窄為上述 CU 層參數(另案,見第 8 節)。

## 4. 各元件改動(依盤點)

### 4.1 AMF(新容器)
- NG Setup:登記每個 CU 的 gNB ID、PLMN、TAC、端點。
- UE 註冊:配發全場唯一且換手不變的 AMF UE NGAP ID;維護 (gNB, RAN UE NGAP ID) → UE。
- Initial UE Message、Initial Context Setup、DL NAS 路由到正確的 CU。
- Path Switch Request/Ack:更新 UE 所在 gNB 與 RAN UE NGAP ID。
- NG-based 換手(Handover Required/Request/Command):Xn 不存在或被禁用時的退路。
- 取代 CU 內建的假 AMF。

### 4.2 CU
- **多 DU 路由:** DU 註冊時記下端點;所有 F1 指令依 UE 所在 DU 或 cell 所屬 DU 路由。UeContext 記錄 `gnb_du_id`。
- **同 gNB 跨 DU 換手:** 對目標 DU 送 UE Context Setup,完成後對來源 DU 送 Release。
- **身分只含自己:** E2 Setup、KPM、ANR indication、E2FullReporter 只列本 gNB 的 cell;RAN UE NGAP ID 改為每個 CU 自己配發。
- **Xn:** Xn Setup(交換 served cells,建立外部鄰區表)、Handover Request/Ack、SN Status Transfer、UE Context Release、Retrieve UE Context(跨 gNB 重建)、RLF Indication / HO Report(MRO)。TXnRELOCprepExpiry 改由真的計時器觸發。
- **鄰區關係:** NRT 的目標可以是外部 cell(記目標 gNB);查 cell 的地方都要能查外部鄰區表;ANR seeder 不再刪除跨 gNB 關係;反向關係由對端 CU 經 Xn 自行建立。
- **E2 控制:** RC 3-1、群組換手、CCC 節能卸載的目標可以在其他 gNB,自動走 Xn。
- xnBlocklist、Xn 建立狀態只作用在跨 gNB 的關係;同 gNB 換手不看 Xn。

### 4.3 DU
- 每個 DU 只帶自己的 cell;`SIM_GNB_DU_ID` 各自不同;F1 指向自己的 CU。
- 外部驅動的 tick(D1);`replace_cells`、`replace_ues` 只處理自己的部分。
- 跨 DU 換手時正確釋放 UE;拒絕不屬於自己的 cell 的控制。
- 鄰區 PCI、ARFCN 從全場 cell 表查。

### 4.4 RU(空中介面 + 時鐘)
- 全場時鐘與鎖步(D1)。
- 每拍合併所有 DU 的負載與 UE:DL 干擾、UL 干擾跨 DU 正確計算;live 模式一拍一次射線追蹤。
- cell 表記錄所屬 DU;`update_cells` 一次收全場。

### 4.5 UE 容器
- 保留 gNB → DU → cell 結構;每個 cell 對應的 CU、DU。
- UE 依選到的 cell,經該 cell 的 DU 送 Initial UL RRC 到該 gNB 的 CU(真實流程),不再全部接到預設 cell。
- 各項控制、查詢對所有 CU、DU 分送或合併;每個 gNB 各自的 A3。

### 4.6 e2adapter
- 每個 CU 一個(現行設計已是 per-CU);NCI 計算與 D2 一致。

### 4.7 orchestrator
- 以「實例」而非「角色」管理容器:spawn、健康檢查、重啟接手、停止。
- 一場配 N 個槽位;每個 CU、DU 各自的資料庫。
- 歸檔:每個 CU、DU、e2adapter 各自輪詢,資料列加上 gNB / E2 node 欄位。跨 gNB 換手只從來源端記一次。
- RIC:register 送 N 個 node、停止時逐一清理。
- Agent API:I-1、I-2 回傳每個 gNB 一組 E2 身分;I-3 事件依目標 cell 路由到對應 CU、DU;I-6、I-7 帶 gNB。

### 4.8 registry 與前端
- `Scene.e2_slot` 改名 `Scene.e2_block`(區塊號 1–15);`Gnb.e2_index`(0–15,場景內唯一,自動配發);`Cell.local_cell_id`(gNB 內唯一,自動配發);場次存 `e2_block` 與每個 gNB 的身分清單 `e2_nodes`;run_instance 加實例名稱、gNB、DU 參照,新增角色 amf。
- 場景編輯器:每個 gNB 的槽位欄;DU 選擇器(一個 gNB 多個 DU)。
- 執行監控:列出所有 CU、DU、e2adapter。

### 4.9 文件
- Agent 介面總覽、Agent 手冊、E2 訂閱對照:改為多 E2 node。

## 5. RIC 端改動(依 RIC 查證回覆,約 300 行 + 測試,不動平台元件)

| 項目 | 內容 | 規模 |
|---|---|---|
| R1 observation 節點歸屬 | aggregated 的 cell 級、關係級 entry(servingCells、neighbourCellRelations、measurementReportAggregate、reestablishmentInboundByPreviousPci)加 nodeId/meid;raw 改依 scene_sim_ms 分桶,`e2[]` 改 `[{nodeId, meid, gnb_id, cells}]` | 約 80 行 |
| R2 閘道 cell 檢查依 node | 控制的 source cell 必須屬於被點名的 node,否則 422 | 約 20 行 |
| R3 dt-exec 節點選擇 | 2-6 依 UE 的 servingCell 反查 node(不再取 controlTargets[0]);R1 缺鄰區改用全場 PCI 索引 | 約 30 行 |
| R4 dt-preproc 跨 node 合併 | ue_level 以 UE 為鍵合併,servingNode 隨換手變,handoverInWindow 涵蓋跨 node | 約 60 行 |
| R5 dt-anr 場景級關係視圖 | guard 的 xn-reverse 判斷改看場景級關係(反向關係在另一個 node);全場 PCI 索引 | 約 100 行 |
| R6 文件 | AGENT_GUIDE 寫明多 node 時 body 必帶 nodeId | — |
| R7 rc-probe | 3-1、3-1-group 的 target_nci 改必填,移除 0x38 預設;2-6 的 target_nci 維持選配 | 約 10 行 |
| R8 測試腳本 | fieldc2-anr-add.sh、ranp4-verify.sh、control_selftest.py 改由場景的 controlTargets / observation 取 node、cell、NCI | — |

**不用改(RIC 已確認):** register/activate/xapp deploy/刪除清理、dt-fullkpm、rc-probe(RC 3-1 以 target_plmn_hex + target_nci 指定任意 gNB 的 cell,UEID 用 amf-UE-NGAP-ID)、2-8、CCC、ReportCGI 的送出端、xApp 部署維持「一場一組、訂多 meid」。

**RIC 對 DT 的要求(已納入本計畫):**
- nodeId = registry gNB 名稱;meid 依 D3 區塊;cell 名全場唯一。
- node 綁定早於 E2 Setup(D4)。
- CU 的 ReportCGI 要能回答鄰 gNB 的 cell(由 Xn Setup 交換的 served cells 提供,4.2)。
- 每個 gNB 一條 SCTP:e2adapter 重連抖動要控制(驗收時觀察 rtmgr 推送失敗率)。

**RIC 端備註:** e2mgr 目前不會把 F1 元件解成 servedNrCells(C7 不作為 RIC 端的閘);R2 以 ran_func 6 的 anr_serving_cell 判斷 cell 歸屬。

## 5.1 對 RIC 與 Agent 可見的介面變更(雙方逐項確認)

| # | 項目 | 改版前 | 改版後 |
|---|---|---|---|
| C1 | 一場的 E2 node 數 | 1 | = gNB 數 |
| C2 | meid | `gnb_208_095_000e0N`(一場一號) | `gnb_208_095_000eXY`(X 區塊、Y gNB 序號) |
| C3 | 閘道 register `nodes` | 單一 node,nodeId `cu` | 陣列,每 gNB 一筆,nodeId = gNB 名稱 |
| C4 | 開場順序 | E2 Setup 後才 register | register 綁定後才 E2 Setup |
| C5 | cell 名 | `e03:src`(全場同一前綴) | `e31:src`(前綴 = 所屬 gNB 槽位) |
| C6 | NCI | SHA-1(cell 名) | 3GPP:gNB ID(22 bit)‖ 本地 cell ID(14 bit) |
| C7 | E2 Setup 的 F1 元件 / servedNrCells | 列出全場 cell | 只列本 gNB 的 cell |
| C8 | ran_func 5 `all_rsrp`、鄰區 | 鄰區都是同 node 的 cell | 鄰區可能屬於其他 node;`ncgi` 仍只在 NRT 解得出來時附帶 |
| C9 | ran_func 5 `ngap_id` | 同 CU 內唯一 | = AMF UE NGAP ID,全場唯一,跨 gNB 換手不變 |
| C10 | RC 3-1 目標 | 只能同 gNB | 可指定任一 gNB 的 NCI;跨 gNB 走 Xn |
| C11 | ANR ADD/REMOVE 目標 | 只能同 gNB | 可為其他 gNB 的 cell;反向關係由對端 CU 經 Xn 建立,出現在對端 node 的關係表 |
| C12 | ReportCGI | 只解本 gNB 的 PCI | 也能解鄰 gNB 的 PCI(Xn Setup 交換的 served cells) |
| C13 | Agent I-1/I-2 `e2_identity` | 單一物件 | `e2_identities[]`,每個 gNB 一筆;每個 cell 帶 `ran_name` |
| C14 | Agent I-6/I-7 事件 | 無 node 欄位 | 每筆加 `node_id`、`meid`、`ric_triggered`(bool)、`ric_label`(閘道注入的 `<sid>\|<node>\|g<gen>\|<label>`);換手事件另加 `ho_type`(intra-DU / inter-DU / Xn / NG)、`ngap_id`、`source_ncgi`、`target_ncgi` |
| C15 | 停止通知、R-NIB 清理 | 單一 node | 逐 node |

## 6. 分階段與順序

| 階段 | 內容 | 相依 |
|---|---|---|
| P0 | 本計畫與 RIC 確認 | — |
| P1 | registry schema、場景樹、場景編輯器 | P0 |
| P2 | 身分:cell 標籤、NCI、槽位(D2、D3) | P0 |
| P3 | 鎖步時鐘、RU 全場合併、DU 外部驅動(D1) | P1 |
| P4 | CU 多 DU、跨 DU 換手 | P3 |
| P5 | AMF 容器、CU 改接 AMF | P4 |
| P6 | Xn 與跨 gNB 換手、重建、MRO、ANR 跨 gNB | P5 |
| P7 | UE 容器改造 | P4 |
| P8 | orchestrator、歸檔、Agent API | P2、P4 |
| P9 | RIC 端改動(依第 5 節) | P0 |
| P10 | 前端、文件 | P8 |
| P11 | 驗收(第 7 節) | 全部 |

每階段結束跑該元件單元測試,加上「單一 gNB 場景」回歸,確認舊行為不變。

## 7. 驗收條件(全部通過才算完成)

**測試場景:**
- 走廊(3 個 gNB,各 1 DU、1 cell)。
- 新建「雙 DU」測試場景:1 個 gNB 下 2 個 DU,驗證跨 DU 換手。
- osm_ntust_test(多 gNB、32T32R),驗證 MIMO 與 MU-MIMO 在拆分後仍正常。

**DT 端:**
1. 開場產生正確數量的容器;停止後全部清除,資料庫也刪除。
2. 單一 gNB 場景的 KPM 與改版前一致(同 seed 比對)。
3. 同 gNB 同 DU、同 gNB 跨 DU、跨 gNB(Xn)、無 Xn 時的 NG 換手,四種都實際發生並記錄;跨 gNB 換手後 AMF UE NGAP ID 不變、RAN UE NGAP ID 改變。
4. 跨 gNB 的 RLF 重建能經 Xn 取回 UE context。
5. 跨 DU、跨 gNB 的干擾與拆分前一致(同一場景同 seed 比對 SINR 分布)。
6. Agent API I-1 到 I-7 全部回歸通過,並正確呈現多個 E2 node。

**RIC 端(與 xApp 實測,依 RIC 建議的驗法):**
7. RIC 看到 N 個 E2 node,每個 node 的 E2 Setup 只含自己的 cell;activate 回應的 warnings 為空。
8. 每個 node 都收得到 indication:dt-fullkpm `GET /stats` 每個 meid 都有計數;InfluxDB `dt_fullkpm.scene_clock` GROUP BY meid 每個 node 都有列;submgr 每個 meid 各兩筆訂閱(ran_func 5、6)。
9. 跨 gNB RC 3-1:經閘道 style=3-1、nodeId=來源、target_plmn_hex + target_nci=另一 gNB 的 NCI、ngap_id → rcProbe.ack == "ACK";DT I-7 有紀錄;下一窗 ueLevel 該 UE 的 servingNode 變成目標 node。再做 3-1-group。
10. 跨 gNB ANR:一場 anr_auto_add=0、guard 開,鄰 gNB 的 cell 故意不在 NRT → guard 對來源 node 送 rc-reportcgi 解出外部 NCGI → anr-add ACK → 關係出現且 xnX2Established=true;對端 CU 經 Xn 自行建立反向關係,guard 不誤判;再手動 anr-remove。
11. CCC:對每個 node 各下 ccc-lock/unlock;節能卸載能把 UE 換到其他 gNB 的 cell。
12. 2-6 落在 UE 的服務 node(control_audit.nodeId 正確);併驗 ranP[4]:帶 target_nci 的 2-6 只套用在那一個 cell。
13. 負向:不帶 nodeId → 422 nodeId-required;用 node A 的 nodeId 下 node B 的 cell → 422(R2)。只適用有 cell 名參數的 style(anr-*、CCC、3-1-group 的 serving_cell、ReportCGI);3-1 的 target_nci 指向其他 gNB 是合法的,不擋。
14. 多場並行(例 2 場 × 3 node = 6 node):rtmgr 推送無失敗。
15. 世代隔離:DELETE 後以同一區塊重新 register,用舊 gen 下控制 → 409 scenario-generation-mismatch。
16. 停止後全清:N 個 meid 的 `GET /v1/nodes/{meid}` 都 404、submgr 沒有它們的訂閱、e2mgr `/v1/nodeb/{meid}` 404、R-NIB 無殘留。
17. 跨 gNB 換手在 dt-preproc 看得到:下一窗 ue_level 該 UE 的 servingNode 變成目標 node、handoverInWindow = true、ngap_id 不變(驗 R4)。
18. 負向:任一 node 尚未 CONNECTED 就 activate → 409 ran-not-connected,並列出該 node。

**分兩段驗:** 多 node 能起、能 E2 Setup 時,先驗 7、8、16、18;Xn 完成後驗 9–15、17。每次起場景前先與 RIC 端約時間;動 RIC 叢集走 RIC 端閘門。

## 8. 另案(不在本次範圍)
- gNB 模板收窄、新增 cell 模板(管理平台 UX)。
- F1、Xn、NG 改用真實 ASN.1。


## 9. DT 端實作紀錄與內部驗證(2026-09-27)

### 9.1 各階段狀態

| 階段 | 狀態 | 主要落點 |
|---|---|---|
| P1 registry | 完成 | e2_block / e2_index / local_cell_id、遷移、場景編輯器區塊與 gNB 表、64 個 registry 測試 |
| P2 身分 | 完成 | `ran_sim_protocol.e2_identity`、`run_topology`(一場的拓樸,env `RUN_TOPOLOGY` 發給每個容器);CU / DU / UE / e2adapter / Agent API 全部改讀它 |
| P3 鎖步時鐘 | 完成 | RU `phy_low/lockstep_clock`(`RU/State/LockstepClock/*`);DU `SIM_CLOCK=external` + `TickController/step`;UE 端時鐘操作改打 RU |
| P4 CU 多 DU | 完成 | DuRegistry.endpoint;F1 依 UE / cell 路由;Initial UL RRC 帶 cell 與 gNB-DU ID;同 gNB 跨 DU 換手(目標 DU UE Context Setup → 來源 DU Release) |
| P5 AMF | 完成 | 新容器 `RANsim-AMF`(NG Setup / Initial UE / Initial Context Setup / Path Switch / NG 換手 / Release);compose 預設開 |
| P6 Xn | 完成 | CU `Xn/XnRouter/*`:Xn Setup 交換 served cells、換手、SN Status Transfer、UE Context Release、跨 gNB 重建、Handover Report;ANR 跨 gNB(反向關係經 Xn 由對端建);RC 3-1 以 NCI 指鄰 gNB;沒有 Xn 時依 run knob `ho_ng_fallback` 走 NG 換手,否則照舊 TXnRELOCprepExpiry |
| P7 UE 容器 | 完成 | `ran_endpoints`(依拓樸路由)、在選定 cell 的 DU 接入、下行路由表(CU 換手後通知 `UE/UserPlane/path_update`)、每 gNB 各自的 A3 |
| P8 orchestrator | 完成 | 以實例管理容器(label)、區塊配發、D4 開場順序、多 node 閘道宣告 / 逐 node 清理、多 CU 歸檔(node_id / meid)、Agent API `e2_identities[]` 與 C14 欄位、`no_ric` 內部測試模式、`/status` 的 `no_ric` / `meids` |
| P9 RIC 端 | RIC 已完成 R1–R8(閘道 0.8.26-multinode 等) | — |
| P10 前端 / 文件 | 執行監控前端已支援多實例;本節為實作紀錄;Agent 手冊待與第一場多 node 場景一起定稿 | — |
| P11 驗收 | DT 端 1–6 已在內部(no_ric)驗過,見 9.3;RIC 端 7–18 待約時間 | — |

### 9.2 與 RIC 的追加約定(v2 之後)

- **ANR 的 `ncgi` 欄位(選項 A)**:ran_func 6 的 `ncgi` 維持 cell 名稱(`e31:src`);另加 `nci`、`ncgiStd`(D2 字串),關係加 `targetNci`、`targetNcgiStd`,measurementReportAggregate 在 PCI 唯一對到一顆 cell 時加 `reportedNci` / `reportedNcgiStd`。輸入端 cell 名稱與 D2 字串都收。
- **D2 例子更正**:NCI = gNB ID << 14 | 本地 cell ID,例 gNB 0xe31 cell 1 → `208095-0038c4001`(v2 原文例子寫錯,規則沒變)。
- **RIC 對帳**:閘道標籤放 E2AP RICcallProcessID(IE 20,UTF-8);RC / ANR / CCC 三條控制路徑都解出來記進控制稽核、ACK / Failure 原樣帶回。I-6 / I-7 帶 `ric_triggered`、`ric_instance_id`、`ric_label`(、I-7 另帶 `ric_requestor_id`)。
- **`/status`**:running[] 每筆帶 `no_ric`、`meids`;RIC 部署閘門只擋 `no_ric=false` 的場次。
- **資料切點**:下列 9.4 的修正只對新場次生效;RIC 以「第一場多 node 場景的 run 號」為切點,之前的 run 36–48 不與之後比較 RLF 類判定與吞吐 / PRB 絕對值。

### 9.3 DT 端內部驗證(no_ric,走廊 08–16,18 UE,10×)

| 驗收 | 結果 |
|---|---|
| 1 容器數 / 清除 | 3 gNB 場景:amf + 3 cu + 3 du + ru + ue = 9 個容器,7 個 DB;停止後容器與 DB 全清(多次) |
| 2 單一 gNB KPM 不變 | 新舊時鐘同場景 40 分鐘:逐 UE 每分鐘吞吐相關 0.9985、SINR 0.986;平均吞吐 1.282 / 1.283 Mbps;RLF 368 / 357 |
| 3 四種換手 | intra-DU、inter-DU(雙 DU 場景 28 次)、Xn(34 次)、NG(23 次);跨 gNB 後 AMF UE NGAP ID 不變、RAN UE NGAP ID 改變(例 p10:790647096 固定;RAN 1201065785 → 401568321 → 1201065785) |
| 4 跨 gNB 重建取回 context | 有關係且 Xn 建立時 REESTAB_WITH_CTX + AMF Path Switch;沒有時 WITHOUT_CTX + 重新 Initial UE Message |
| 5 干擾一致 | 同一 UE 同一秒、干擾 cell 負載相同時,拆分前後 SINR 差的中位數 0.000 dB;差異只隨負載差單調變化。拆分後整體吞吐略低,來自跨 gNB 重建不帶 context 時下行緩衝遺失(真實行為,合併時同一 DU 不會發生) |
| 6 Agent API | I-1 / I-2 回 `e2_identities[]`(每 gNB 一筆,cell 帶 `ran_name`、NCI、ncgi);I-4 / I-6 / I-7 在多 gNB 場次正常,事件帶 node_id / meid / ho_type / ngap_id / ncgi |

測試場景:`mgnb_xn_test`(走廊,anr_auto_add=1)、`mgnb_dualdu_test`(1 gNB 2 DU)、`mgnb_ng_test`(anr_xn_auto_reverse=0、ho_ng_fallback=1)。三者都由走廊 08–16 複製,沿用同一份通道快取。

### 9.4 過程中修掉的問題(舊版也受影響者標 *)

- * CU 寫 UE context 會互蓋(`update_entity` 整列寫回):traffic profile 被清空、serving cell 被寫回舊值 → 部分 UE 整場沒流量、每秒一次假 RLF。改為只寫變更的欄位;AMF Initial Context Setup 只在 serving cell 為空時補。
- * 流量產生器以「牆鐘 × 當下倍速」推算劇本時間:注入量隨倍速漂移、中途進場的 UE 從自己的 t=0 重播。改讀劇本時鐘。
- * full KPM 快照只在歸檔啟動時抓一次(註解寫每 60 劇本秒)。
- * ANR 控制格式錯時 e2adapter 送 Failure 會自己出錯,RIC 等不到 Failure。
- 鎖步:DU 回報的 cell 負載含別的 DU 的舊值,RU 合併時蓋掉新值 → 部分 cell 負載凍在初值(改為只報自己的 cell)。
- NG 換手後量測報告的最後一步找不到已移走的 UE → 500 → 交易回滾把換手事件一起撤掉。
- Xn 換手後舊 DU 在途的量測報告觸發 ANR,在錯的 gNB 寫出來源是別人 cell 的關係(改為丟棄非本 gNB 服務中 UE 的報告)。
- 開場 DU 的 F1 Setup 比 UE 接入晚 → 接入被拒且不重試(改為先等每個 CU 認得自己的 cell,並重試失敗的接入 / 回場)。
- RU 的 cell → 通道快取鍵固定用「gNB 名#PCI」,場景預算後改了 cell 所屬 gNB 就對不上(改以快取實際的鍵為準,與 DU 同規則)。

- 第二場前的控制面檢查(2026-09-27,no_ric 實測於 `mgnb_xn_test`,直接呼叫 CU):
  - RC 3-1 群組換手:鄰區是別的 gNB 的 cell 時原本永遠匹配 0 個 UE(只查本地 cell 表);改為本地與 Xn 外部鄰區表都查。實測 src → nbr 群組 EXECUTED(Xn 換手 SUCC)。
  - RC 3-1 逐 UE 換手到鄰 gNB 的 cell:回覆裡的 `target_nr_cell_id` 以前退回 hash 值,改取 Xn 鄰區表的 NCI。實測以 AMF UE NGAP ID 指定 UE 換到 mid 成功(之後因 mid 訊號弱 RLF、重建到 nbr 並對來源送 MRO ToWrongCell,屬正常行為)。
  - CCC 節能趕人:本 gNB 沒有其他 cell 時(每站一 cell 的走廊)原本趕不出去、cell 永遠停在 toBeEnergySaving;改為退回挑 Xn 鄰 gNB 的 cell(優先已有關係且未 blocklist)。本地有其他 cell 時行為不變。實測 src 3 個 UE 趕到 nbr → isEnergySaving,開回後 UE 自然換回。
  - RC 2-6 / 2-8 的 ranP[4] NCI 指到鄰 gNB 的 cell:現在解得出來(Xn 鄰區表),但配額 / 波束只能下在本 E2 node 自己的 cell → 409「not served by this E2 node」,不送 DU(與改版前「解不出 → 409」同一類回覆)。

- 第二場(run 5)RIC 回報:ran_func 5 的 cell_id 變成 15 位 NCI hex,與 ran_func 6 的 cell 名稱對不上。原因是 full KPM 與 ReportCGI 的舊規則「cell 有 nr_cellid 就印 hex」—— 舊場景的 cell 沒有 nr_cellid,所以一直是名稱;多 gNB 起每個 cell 都有 NCI 才觸發。改為一律回 cell 名稱,數字另放 `nci` / `ncgiStd`(舊場景輸出不變)。ReportCGI 另補:鄰 gNB 的 PCI 以前一律 FAIL(只查本地 cell),改為也查 Xn 外部鄰區表。第三場生效。

- 第二場 11c:es-on 時 mid 的 UE 有經 Xn 趕到 nbr(鄰 gNB 退回路徑生效),但同一瞬間另有 UE 重建進 mid,cell 停在 toBeEnergySaving。舊版就有的限制(單 CU 亦同)。改為:toBeEnergySaving 期間接入閘(出生安置、換手目標、重建落點、鄰 gNB 轉入)視同 barred(`admission_blocked`,對外觀測的 barred 欄位不變);清不空時背景每 1 s 再趕一輪,清空即關 cell 轉 isEnergySaving,收到 es-off 即停,120 s 仍清不空則維持 toBeEnergySaving。

- orchestrator 健康監控在多 gNB 版整場無作用(每 5 s `'str' object is not callable`):新增的 `_name()` 方法被 `threading.Thread` 自己的 `self._name`(執行緒名稱字串)蓋掉。影響自動停 / 自動重啟 / 進度回寫,不影響 E2 與資料。已改名 `_cname`,重啟 orchestrator 後無此錯。
- 上述四項於 2026-09-27 08:47Z no_ric 實場自測通過(`mgnb_xn_test`):ran_func 5 cell_id = cell 名 + nci / ncgiStd;ReportCGI PCI 0/1/2 皆解成 cell 名(含鄰 gNB);節能 es-on 趕 2 UE 到 nbr → isEnergySaving;背景重試迴圈實場清空 2 UE 並關 cell。

### 9.4a 與 RIC 的聯測結果(2026-09-27)

| 場次 | 內容 | 結果 |
|---|---|---|
| 第一場(run 4,走廊區塊 2) | 16 / 18 | 通過;7 / 8 未達成(RIC rtmgr 路由與 submgr 啟動期問題,RIC 已修) |
| 第二場(run 5,走廊區塊 2) | 7 / 8 / 9 / 10 / 11 / 12(手動)/ 13 / 15 / 16 | 通過(11c 節能部分,已補);發現 ran_func 5 cell 名、ReportCGI、節能 barred、健康監控四項,已修並 no_ric 自測 |
| 第三場(兩場並行:A 走廊區塊 2 run 7;B mgnb_xn_test 區塊 5 run 1) | 7 / 8 / 12(dt-exec 自動)/ 14 / 17 / 16 | 7 / 8 / 12 / 14 / 17 / 16 通過(16:兩場六個 meid 全清,12:39Z RIC 確認) |

- 17 的註記:場 A 沒開 gNB 自主 ANR、也沒人加關係 → 整場 0 次換手,跨 node 移動全是 RLF 後跨 gNB 重建(I-6 看 rlf / rrc_reestab_req);場 B(anr_auto_add=1)六條關係自動建滿,劇本 455–885 s 有 Xn 換手的 UE 與 RIC 判定逐一一致。
- 區塊 3 已被 corridor24_16_24 釘住,場 B 改釘區塊 5。

多 gNB 驗收 7–18 全部完成。11c 的「toBeEnergySaving 擋接入 + 背景趕人」只在 no_ric 自測過,RIC 端下 es-on 的補驗留待任一場。

- 2026-09-27 晚:11c 新版節能由 RIC 端補驗通過(場 B run 2:es-on 一輪趕 3 UE 經 Xn 到 src → isEnergySaving;toBeEnergySaving 期間 Xn 轉入被拒;關閉期間往 nbr 的換手全擋;es-off 後 p06 同秒換回)。e00 共用 adapter 20:01:06Z 換成解 IE 20 的版本(比約定早約 1 分鐘),首次 E2 Setup 因 e2mgr 仍在處理 Reset 被拒、20 s 後重試成功,常駐 xApp 自行重訂,RIC 驗 RC / ANR / CCC 三家族 IE 20 echo 全部正確。
- 同日修:I-7 的 ric_label / ric_requestor_id / ric_instance_id 一直是空的(ControlAuditReader 沒輸出 requestorId / ricLabel,且 I-7 讀的是 snake_case 欄名);CCC 路徑沒把 RICrequestID 轉給 CU(節能趕人的換手事件缺對帳鍵);UE 舊 context 為 RELEASE 時重新接入回 500(舊版即有)。

### 9.4b 並行與容量測試(2026-09-28)

- **三場並行接 RIC**(corridor24_00_08 區塊 1、corridor24_16_24 區塊 3、osm_ntust_test 區塊 6 = 2 gNB × 3 cell):dt-exec 自動 4 筆落在 3 場 4 個 node;osm 場 2-6 帶 ranP[4]=g0_c1 只套 g0_c1、不帶套 g0 三顆,ccc lock/unlock 只動 g0_c1;跨場景負向被閘道 422 擋;16 通過。
- **容量(3 gNB × 1 cell × 15 UE 的 cached 場,cap_01…cap_10)**:
  - no_ric、目標 10×:1 場 8.5×、4 場最慢 5.4×、8 場最慢 4.8×(CPU 78%);第 9 場起不來 —— **PostgreSQL 連線上限**(max_connections 300,每場約 30–35 條)。
  - 接 RIC、目標 4×:1–3 場 ≈4.0×,4 場最慢 3.59–3.72×(load 20.8 / 24 核),5 場最慢 3.39–3.43×(load 34)→ **上限 4 場**;瓶頸是 DT 主機 CPU(每 gNB 多一個 e2adapter + E2 傳輸),RIC 端 5 場 15 node 無劣化。
  - 另有固定上限:E2 區塊 15 個,扣掉 5 個釘住的場域,其他場域最多同時 10 場。
- 同日修:activate 原本只看閘道 subscriptionCount(被 RIC 常駐 mobiflow 的訂閱墊高而失效),改為另外確認 DT 每個 CU 都已收到 KPM 訂閱,最多等 160 s;cap_04/05 起開場無資料缺口。

### 9.4c 收尾修正(2026-09-28)

- RC 3-1 單 UE 換手沒成:CU 回 409 + control_outcome,adapter 送 **RICcontrolFailure**(cause ricRequest/unspecified,IE 32 帶 `{"result":"HANDOVER_FAILED","failureCause":…}`)。以前回 ACK + HANDOVER_TRIGGERED。3-1-group 維持 ACK。RIC 同意 (a) 案。
- RIC guard 與 `anr_auto_add` 解耦:只有 run knob `ric_guard=0` 才帶 `ANR_GUARD_ENABLE=0`(RIC 決定)。
- 節能 `toBeEnergySaving` 的 cell 拒收 UE 第一次接入(CU 409 = RRC Reject);DU 拆掉 Msg3 時建的 context;UE 回場被拒時改選場上其他 cell。
- I-6:`rrc_reestab_req.previous_ncgi` 改 ncgi 字串(另有 `previous_cell_id`);`meas_report.reported[].cell_id` 移除。
- e00 共用 adapter 06:05Z 重啟(stop 送 Reset → 等 30 s → start,首次 Setup 即過,資料缺口約 100 s),載入稽核欄位修正;3-1 Failure 的改動等 e00 下次重啟。
- registry 刪除測試場景 cap_01…10、mgnb_xn_test、mgnb_dualdu_test、mgnb_ng_test(區塊 5 釋出)。

### 9.4d 場次狀態收成三種(2026-09-28)

- registry `SceneRun.status` 只剩 **idle(閒置、可啟動)/ precomputing(預算中)/ running(執行中)**;上一次怎麼結束另存 `last_result`(done / stopped / failed)。舊的 draft / pending / ready / starting / stopped / done / failed 由遷移 0007 轉換。
- 「有沒有預算」是場景屬性:以通道快取檔 `<legacy_scenario_id 或 scene_uuid>.npz` 是否存在為準;orchestrator 啟動時補齊 cache_path、校正殘留的 running / precomputing。
- **沒預算也能啟動**:cached 場景找不到快取檔時自動改 live、倍速 1×(live 同時只允許 1 場);實測 anr_missing_neighbor 要求 10× → live 1× 正常跑。live 場景本身在多 gNB 架構下實測 2 gNB / 5 UE、2.0× 正常。
- Agent I-4 對外 status 不變(由三種狀態 + last_result 換算);I-1 `ready` 一律 true,另給 `precomputed`、`max_speed_x`。前端兩個都改成三種狀態的中文標籤,上次結果以小字顯示。

### 9.5 尚待處理

- 共用的舊堆疊(ransim-cu / ransim-e2adapter,即 RIC 常駐的 e00)掛載同一份程式碼,新程式碼在沒有 `RUN_TOPOLOGY` 時走舊路徑;要讓 e00 的 e2adapter 也解 IE 20,需重啟它,須與 RIC 約時間。
- ~~Agent 手冊與 E2 訂閱對照表改為多 node~~ 2026-09-28 完成:`docs/agent_need/Agent介面總覽_2026-09-28.md`、`Agent手冊_DT與RIC_2026-09-28.md`(取代 09-23 版)、`E2訂閱與欄位對照.md` 第八節。
- 2026-09-28 順帶修:I-2 / I-3 `son.anr_auto_add` 沒設時報 true、實際是關(舊版即有);I-6 重建事件缺 meid;I-7 CCC 控制缺 object_id;歸檔事件 API 補 node_id / meid;CU 的 NG / Xn Setup 不再於 manage.py shell 等一次性命令觸發。
- 第三場 B 的 4 次「換手失敗」查明:歸檔中 run 1 只有 1 筆 FAIL,是 MRO 把已執行的換手改判 HandoverToWrongCell(UE 旋即 RLF 並在別處重建),非真失敗;場中看到的 4 筆是 CU 即時表的同類改判。
