    # DT 平台 E2 支援命令清單(單一真相來源)

    > **這份文件是 DT E2 node 對 RIC/xApp 支援命令的權威清單。**
    > 任何 E2 命令的新增 / 修改 / 移除,都必須同步更新本文件。
    > 對接細節另見:[`e2sm_ccc_cell_control.md`](./e2sm_ccc_cell_control.md)(CCC 格式)、[`e2sm_fullkpm.md`](./e2sm_fullkpm.md)(FULLKPM 欄位)、[`rc_observation_api.md`](./rc_observation_api.md)(RC 觀測 API)。

    最後更新:2026-08-18

    ---

    ## 0. 節點識別
    | 項目 | 值 |
    |---|---|
    | PLMN | MCC=208 / MNC=95 |
    | gNB ID | `gnbDT`(`gnb_208_095_000e00`,gNB-ID hex `0x000e00`, len 22) |
    | RMR types | 12040 CONTROL_REQ · 12041 CONTROL_ACK · 12042 CONTROL_FAILURE |
    | CCC 編碼 | JSON(非 ASN.1),包在 E2AP OCTET STRING |

    ---

    ## 1. E2 Setup 廣播的 RAN Function（xApp 可發現）

    | RAN Func ID | Service Model | OID | 版本/說明 | 狀態 |
    |---|---|---|---|---|
    | **2** | **KPM** | `1.3.6.1.4.1.53148.1.2.2.2` | E2SM-KPM v2.0.03 | ✅ 常開 |
    | **3** | **RC** | `1.3.6.1.4.1.53148.1.1.2.3` | E2SM-RC v01.03 | ✅ 常開 |
    | **4** | **CCC** | `1.3.6.1.4.1.53148.1.1.2.4` | E2SM-CCC(cell 開關/節能) | ✅ 開，受 env `E2SM_CCC_ENABLE` gate |
    | **5** | **FULLKPM** | `1.3.6.1.4.1.53148.1.1.2.100` | sim 擴充：190 欄完整 KPM | ✅ |

    > 定義位置：`RANsim-CU/main/apps/cu_cp/services/optional/e2/global_e2_node_id.py`
    > Adapter 廣播 gate：`RANsim-E2Adapter/.../codec/e2ap_codec.py`（CCC 由 `E2SM_CCC_ENABLE` 控制）

    ---

    ## 2. 支援的 E2 程序（procedure）

    | 程序 | 支援 | 用於 |
    |---|---|---|
    | E2 Setup | ✅ | 廣播上表 4 個 RAN function |
    | RIC Subscription（create / delete / list） | ✅ | KPM（量測訂閱） |
    | RIC Indication（polling 取代 SCTP push） | ✅ | KPM / FULLKPM 上報 |
    | RIC Control（Request → ACK / FAILURE） | ✅ | RC / CCC |
    | RIC Control（CCC Indication 狀態回報） | ⏳ 未接 | CCC 節能完成回報（需 xApp 先訂閱 CCC） |

    ---

    ## 3. KPM（id=2）— 量測上報

    - Report **Style 1**（E2 Node Measurement）。
    - 支援 metrics（9）：

    | Metric | 單位 |
    |---|---|
    | DRB.UEThpDl / DRB.UEThpUl | bps |
    | DRB.PdcpSduVolumeDL / DRB.PdcpSduVolumeUL | kbit |
    | DRB.RlcSduDelayDl | μs |
    | RRU.PrbTotDl / RRU.PrbTotUl | PPM |
    | RSRP | dBm（sim 擴充） |
    | SINR | dB（sim 擴充） |

    > 定義位置：`RANsim-E2Adapter/.../codec/e2sm_kpm_codec.py`

    ---

    ## 4. RC（id=3）— 控制（RIC Control）

    | Style / Action | 命令 | 用途 | 粒度 | 狀態 |
    |---|---|---|---|---|
    | **Style 1 / Action 2** | QoS flow mapping | 改 UE QoS flow 對應 | per-UE | ✅ |
    | **Style 2 / Action 6** | Slice-level PRB Quota（min/max/dedicated） | IM / ES | per-cell / gNB | ✅ |
    | **Style 3 / Action 1** | **Handover** | CCO / ES 趕人 | per-UE | ✅ 已端到端驗證 |
    | **Style 9 / Action 1** | **MeasConfig ReportCGI**（PCI+ARFCN→CGI） | ANR 鄰區發現 | per-query | ✅ sim 驗;CGI 回 control-ACK **outcome**（需 RIC 送 Style9+讀 outcome） |
    | Style 2 / Action 7 | cell on/off（**非標準 legacy**） | 舊版開關 cell | per-cell | ⚠️ 保留但已被 CCC 取代 |

    > Style 9 ReportCGI 格式（給 rc-probe）：control message ranP `1=PCI, 2=ARFCN, 3=RAT(選配)` → sim 回 RIC Control Acknowledge，`RICcontrolOutcome`(id=32) 是 JSON `{physicalCellId, arfcn, cgi, unique, confusion, results}`。confusion=true 表同 PCI 多 cell（需 ARFCN 消歧）。

    > Decode：`RANsim-E2Adapter/.../codec/e2sm_rc_codec.py`
    > 落地：`RANsim-CU/.../actors/e2_control_actor.py` → `request()` 分支

    ---

    ## 5. CCC（id=4）— cell 配置與控制 / 節能（JSON）

    透過 `listOfCellsControlled[].listOfConfigurationStructures[].newValuesOfAttributes`：

    | 屬性（結構） | 值 | 效果 | 狀態 |
    |---|---|---|---|
    | **administrativeState**（NRCellDU） | LOCKED / UNLOCKED | 硬開關，即時，不趕人 | ✅ |
    | **cellState**（NRCellDU） | INACTIVE / ACTIVE | 硬開關 | ✅ |
    | **energySavingControl**（O-CESManagementFunction） | toBeEnergySaving / toBeNotEnergySaving | **兩階段節能**：趕人(HO) → 清空 → 關 cell | ✅ 已端到端驗證 |

    - 上行回 **RIC_CONTROL_ACK**（成功）/ **FAILURE**。
    - cell 識別：xApp 送 **`nRCellIdentity` 字串**（`gnbDT_c0` / `gnbDT_c1`）；數字 NR Cell Identity 需另加映射。
    - **CCC Indication（狀態回報）producer 尚未接**，需 xApp 先訂閱 CCC。

    > Codec：`RANsim-E2Adapter/.../codec/e2sm_ccc_codec.py`
    > 狀態機：`RANsim-CU/.../actors/e2_control_actor.py` → `_cell_energy_saving()`
    > 詳細格式：[`e2sm_ccc_cell_control.md`](./e2sm_ccc_cell_control.md)

    ---

    ## 5b. ANR / E2SM-ANR（ran_func=6，JSON 承載，受 `E2SM_ANR_ENABLE` gate）

    > 目標：xApp 由組態書寫者 → gNB SON 觸發者（`docs/ANR情境_v8.docx`）。真實度 = A（命令真實改變模擬行為）。分階段見 `docs/plan/anr_xapp_commands_plan.md`。OID `1.3.6.1.4.1.53148.1.1.2.6`，ricStyleType=1。

    **觀測（M0 完成）：**
    | 端點 | 對應 xApp 命令 | 說明 |
    |---|---|---|
    | `POST /CU/E2/NodeInfo/read {cell_id?}` | `RC_E2NODEINFO_QUERY` | 回 §9.3.38 neighbourCellRelations（+卷面延伸、flags、version）|
    | `POST /CU/E2/Anr/reseed` | —（內部）| 從 CellConfig 重種 NRT + CGI 解析 |
    | `POST /CU/E2/Anr/set_barred {cell_id, barred}` | —（劇本佈署用）| TS 38.331 **cellBarred**:cell 仍被量測回報,但 UE 不得駐留(RRC 重建落點排除)|

    **SON 觸發控制（M1 廣播 + M2 命令完成）：** E2 Setup `accepted=[2,3,4,6,5]`（含 6）。
    xApp 送 RIC Control（ran_func=6，JSON `controlMessageFormat.sonTriggerRequest`）→ adapter 解碼 → `POST /CU/E2/Anr/control`：
    | requestType | 參數 | 效果 | 對應 xApp 命令 |
    |---|---|---|---|
    | `ADD` | sourceCellId, target{cgi,pci,arfcn[,rat,plmn]} | 新增/更新鄰區關係，version+1 | `SONTRIG_ANR_ADD_REQUEST` |
    | `REMOVE` | sourceCellId, targetCgi, reason | 移除；保護條目(is_remove_allowed=False/no_remove)→拒絕 | `SONTRIG_ANR_REMOVE_REQUEST` |
    | `FLAG` | sourceCellId, targetCgi, flag∈{hoBlocklist,noRemove,xnBlocklist}, op∈{set,clear} | 設/清旗標，version+1 | `SONTRIG_ANR_FLAG_REQUEST` |

    - 受控物件：`NrCellRelation`、`CgiResolution`；種子：F1 Setup 後自動建 intra-gNB 鄰區（冪等）。
    - **ADD/REMOVE/FLAG 三種都回 `RICcontrolOutcome`(id=32)= JSON** `{requestType,sourceCellId,targetCgi,result,version,detail}`；`result` ∈ `ADDED`/`UPDATED`/`REMOVED`/`FLAG_SET`/`FLAG_CLEAR`/`REJECTED_PROTECTED`/`REJECTED_ANR_DISABLED`/`ADD_REJECTED`/`NOT_FOUND`/`UNSUPPORTED`。xApp 可從 ACK 即時分辨結果(不必等 indication)。
    - confirm 慣用式：以 `version` 變化 / 條目出現消失判定（xApp 輪詢 NodeInfo/read）。
    - `NodeInfo/read` 的 neighbourCellRelation IE 帶 **`relationAgeSec`**(now−created_at,過期關係判齡用)。

    **2026-08-18 新增觀測欄位(ANR 驗測 campaign 逼出來的,對所有題目通用):**

    | 欄位 | 位置 | 用途 |
    |---|---|---|
    | `anrIntraEnabled` | `e2NodeInformation` | ANR 自動建立功能之部署組態。**false 時 ADD 回 `REJECTED_ANR_DISABLED` 且不寫 NRT**(REMOVE/FLAG 不受限);xApp 須先做此前置檢查,停用時只得 SMO_NOTIFY。env `ANR_INTRA_ENABLED`(預設 true)|
    | `nrtCapacity` = `{limit, used}` | `e2NodeInformation` | NRT 每 cell 容量。**滿載時新增條目回 `ADD_REJECTED` / `detail=NRT_CAPACITY_REACHED` 且不寫 NRT**;既有條目「更新」不受限。env `ANR_NRT_CAPACITY`(預設 32,卷面第9題假設值 8)|
    | `sourceCellNcgi` / `bySourceCell` | `e2MessageCopyAggregate` 每列 | **來源歸屬**:回報該 PCI 的 UE 當下 serving cell。鄰區關係是 per source cell,少了它 xApp 無從決定 ADD 的 `sourceCellId`。`bySourceCell` 給多來源時分別建關係 |
    | `reason` | `relationChangeEvents` | `action=ADD_REJECTED` 時帶 `NRT_CAPACITY_REACHED`(卷面事件格式)|

    **行為面新增:**

    - **量測回報門檻**(對齊 TS 38.331 `reportConfig`):sim 原本把**所有 cell 照報**(不真實),
      現在只回報 RSRP ≥ 門檻的鄰區。env `MEAS_REPORT_MIN_RSRP_DBM`(預設 -110 ≈ 不濾)。
      無此門檻則「深邊緣稀疏樣本」情境做不出來 —— 每台 UE 都會回報每個 cell。
    - **`cellBarred`**(TS 38.331,`CellConfig.is_barred`):RRC 重建改選 **suitable cell** ——
      DU 送的最強 cell 若 barred/inactive,CU 用該 UE 最近量測的鄰區清單依 RSRP 挑第一個合格者。
      ANR 情境需要「量得到但不收 UE」的鄰居,否則它必然把 UE 吸走、情境瓦解。
      ⚠️ 範圍:`cellBarred` 管**閒置態選網/重建**;**連線態換手**歸 `isHoAllowed`/`hoBlocklist` 管 ——
      關係一旦建立,UE 換入 barred cell 是正常行為(即修復成功的表現)。
    - **Xn 反向關係自動建立**(TS 38.300 §15.3.3.2 步驟 4c):ADD 落地後由 gNB 自行經 Xn 建反向關係,
      延遲 `ANR_XN_SETUP_DELAY_SEC`(預設 2.0s,不阻塞 Control ACK),兩邊標 `xnX2Established=true`。
      審計歸屬用 `by="gnb-xn"`(非 `xapp`),讓 xApp 分辨得出那筆不是自己做的。
      **卷面紅線:xApp 禁止替對端寫反向關係。**

    **M4（A 級行為）已完成並驗證：** A3 換手決策 `evaluate()` 讀 `ho_blocklist`（env `ANR_ENFORCE_HO_BLOCKLIST` 可停用）→ 被封鎖的鄰區直接略過。決定性測試:未封鎖→HO 觸發;FLAG set→不觸發;clear→恢復。→ 真實「封鎖止血」行為。

    **觀測（CU 查詢層 + E2 wire indication 皆完成）：**
    | xApp 命令 | CU 端點（HTTP） | 狀態 |
    |---|---|---|
    | RC_E2NODEINFO_QUERY | `/CU/E2/NodeInfo/read` | ✅ §9.3.38 全欄 + freq + change events |
    | RC_MEASCONFIG_REPORTCGI | `/CU/E2/Anr/cgi_resolve` | ✅ PCI→NCGI + confusion |
    | perNeighbourRelation KPM | `/CU/E2/Anr/kpm` | ✅ HO 速率/成功比 + failureCause（真值,P2-2）|
    | RC_MSGCOPY(MEAS) | `/CU/E2/Anr/meas_aggregate` | ✅ RSRP 分位數 |
    | RLF / 重建 | `/CU/E2/Anr/rlf_kpm` | ✅ RLF/DropRate/ReEstabInbound + inbound-by-prevPci（P1）|
    | MRO 歸因 | `/CU/E2/Anr/mro_kpm` | ✅ TooEarly/TooLate/ToWrongCell（P2-1）|
    | **ANR Indication（一包）** | `/CU/E2/Anr/indication` | ✅ 上塊全含,**func 6 producer 週期上 E2 wire** |

    > **觀測已上 E2 wire（2026-08-12)**:func 6 indication producer 每 period 拉 `/CU/E2/Anr/indication`
    > → JSON+zlib → SCTP 給 RIC(同 FULLKPM 信封)。xApp 對 func 6 標準訂閱即收。
    > 對接:[`e2sm_anr.md`](./e2sm_anr.md)。

    ---

    ## 6. FULLKPM（id=5）— 完整 PM

    - KPM 擴充版，一次輸出 **190 欄完整 pm 欄位**（對齊 `E2_data_example.md`）。
    - 給需要完整 PM 的 xApp。

    > 詳見 [`e2sm_fullkpm.md`](./e2sm_fullkpm.md)

    ---

    ## 7. 變更紀錄（每次擴充/修改 E2 命令都在此追加一行）

    | 日期 | 變更 | 影響 SM / Style-Action |
    |---|---|---|
    | 2026-08-11 | 建立本清單（現況盤點） | KPM / RC / CCC / FULLKPM 全部 |
    | 2026-08-11 | ANR M0：NrCellRelation/CgiResolution 模型 + 種子 + `E2/NodeInfo/read`（RC_E2NODEINFO_QUERY）| 新增 §5b ANR |
    | 2026-08-11 | ANR M1：E2SM-ANR ran_func=6 廣播（E2SM_ANR_ENABLE gate）+ codec；E2 Setup accepted=[2,3,4,6,5] | §5b |
    | 2026-08-11 | ANR M2：ADD/REMOVE/FLAG → `E2/Anr/control` 落地 NrCellRelation + version;adapter SCTP 路由 | §5b |
    | 2026-08-11 | ANR M4（A 級）：A3 換手 evaluate() 讀 ho_blocklist skip target;決定性驗證通過 | §5b |
    | 2026-08-11 | ANR 控制 3 件正規 E2 端到端驗證（rc-probe ADD/REMOVE/FLAG，ACK rtt 22-25ms）+ handler 診斷韌性 | §5b |
    | 2026-08-11 | ANR 觀測 O0 CU 查詢層（NodeInfo/kpm/meas/cgi_resolve/change events）| §5b 觀測 |
    | 2026-08-12 | P0 GBR 排程 + discard 轉真;P1 RLF/重建(RlfEvent + reestablishment + rlf_kpm);P2 MRO 歸因 + HO failureCause(mro_kpm)| §5b 觀測 / KPM pm 欄 |
    | 2026-08-12 | ANR 觀測**上 E2 wire**:func 6 indication producer(`/Anr/indication`→JSON+zlib→SCTP);RIC accepted=[2,3,4,5,6];對接 e2sm_anr.md | §5b func 6 indication |
| 2026-08-12 | A3 補 NRT gating(`ANR_REQUIRE_NRT`,target 需 NrCellRelation)+ 換場景自動 reseed(du_config_update)+ seeder 清 stale;閉環實測缺漏 RLF3.33/HO0→ADD 後 RLF0/HO3.33 | §5b + A3 |
    | 2026-08-12 | RC **Style 9/Action1 ReportCGI**(PCI+ARFCN→CGI 走 E2):adapter 解碼 + CU `_handle_reportcgi`(cgi_resolve)+ CGI 回 control-ACK outcome(id=32);sim 端驗證 pci→cgi | §4 RC |
    | 2026-08-12 | ANR 驗測 4 情境全閉環(#1 缺漏 ADD／#2 有害 FLAG hoBlocklist＋HO force-fail 注入／#3 撞號 REPORTCGI confusion／#4 過期 REMOVE)。**ANR ADD/REMOVE/FLAG ACK 補 RICcontrolOutcome(id=32)**(對齊 ReportCGI,修 22-byte 裸 ACK 落差);neighbourCellRelation 加 `relationAgeSec` | §5b ANR |
    | 2026-08-18 | ANR 驗測 campaign 續(第2/3/4/9題):新增觀測欄位 **`anrIntraEnabled`**(停用時 ADD 回 `REJECTED_ANR_DISABLED`)、**`nrtCapacity{limit,used}`**(滿載回 `ADD_REJECTED`/`NRT_CAPACITY_REACHED`)、**`sourceCellNcgi`/`bySourceCell`**(量測聚合來源歸屬)、`relationChangeEvents.reason` | §5b |
    | 2026-08-18 | 行為面:**量測回報門檻** `MEAS_REPORT_MIN_RSRP_DBM`(38.331 reportConfig,原本所有 cell 照報)、**`cellBarred`** `CellConfig.is_barred`(38.331,重建改選 suitable cell,端點 `/CU/E2/Anr/set_barred`)、**Xn 反向關係自動建立**(38.300 步驟4c,延遲 `ANR_XN_SETUP_DELAY_SEC`,審計 `by="gnb-xn"`) | §5b |
    | 2026-08-18 | A3 預設由 11dB/3000ms 調為 **3dB/300ms** — 原值在 ANR 劇本不換手,先前為逼出換手用的 1.5dB/80ms 必然乒乓、污染各題排除表的「MRO 平坦」條件(TooEarly 4.0→1.6/min,HO 仍正常) | compose / A3 |
