# 天線與 MIMO 可調參數表(操作者視角)

假設:操作者透過前端調整一支「已完整運作」的 RAN,目標是設計出期望的波束與 MIMO 行為。
本文列出所有會改變波束或 MIMO 行為的參數,一列一個旋鈕,說明它作用在哪一層、誰能改、規範給的值域、轉了會變什麼、要先設什麼。

預設情境:64T64R 宏站、O-RU Category B(預編碼在 RU)、支援 PDBF + WDBF、FR1 3.5 GHz、SSB L_max = 8。「轉了會變什麼」一律以此舉例。

---

## 0. 怎麼讀

### 0.1 五層

| 層 | 名稱 | 誰在改 | 改一次要多久 | 真實 RAN 走哪個介面 |
|---|---|---|---|---|
| ① | 實體部署 | 工程人員 / DT 情境 | 小時到天(爬塔)或秒(ALD RET) | 爬塔、AISG/ALD;DT 可直接改 |
| ② | O-RU 設定 | O-DU 或 SMO 經 NETCONF | 秒級,半靜態 | O-RAN M-plane(YANG rw 葉、RPC) |
| ③ | 小區 / UE 無線資源設定 | CU / DU | 百毫秒級,需 RRC 重配 | 3GPP RRC(TS 38.331 ASN.1) |
| ④ | 逐 slot 排程命令 | O-DU 排程器 | 每 slot(0.5 ms @ 30 kHz SCS) | O-RAN C-plane(section、extension) |
| ⑤ | 排程器政策 | 廠商演算法 / DT 自訂 | 隨時 | 規範不管,無標準介面 |

### 0.2 欄位

| 欄 | 意思 |
|---|---|
| 參數 | 名稱,含 YANG leaf 或 ASN.1 欄位原名 |
| 值域(規範原文) | 直接抄 YANG type/range/enum、ASN.1 INTEGER/ENUMERATED、或條文;規範沒給就寫「廠商自訂」或「RU 自報」 |
| 轉了會變什麼 | 對波束形狀、指向、功率、層數、UE 量測值的直接影響,以 64T64R 舉例 |
| 前置條件 | 要先設哪個參數,或 RU 要宣告哪個能力(YANG if-feature / 能力葉) |
| 出處 | 章節、YANG 行號,或本專案摘錄編號 |
| 類型 | [3GPP-N] 規範、[3GPP-TR] 研究報告校準值、[ORAN-N] O-RAN 規範、[SIM] 規範未定義,DT 自行假設或向廠商取得 |

### 0.3 真實 RAN 與 DT 的差別

標「只有 DT 能直接改」的列,在真實 RAN 要靠換硬體、廠商工具或根本不開放。DT 裡它們都是情境參數,可以直接寫。表中用 **DT 直接改** 標示。

---

## 1. 第 ① 層:實體部署

決定天線「長什麼樣、裝在哪、朝哪」。改了會整體平移所有波束,不會改變波束之間的相對關係。

| # | 參數 | 誰能改 | 值域(規範原文) | 轉了會變什麼(64T64R 例) | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|---|
| 1.1 | 陣列規格 (M_g, N_g, M, N, P) | 換硬體;**DT 直接改** | M, N 為 uint16 無上限;P ∈ {1, 2};O-RAN 另有 Q(array layers)uint8 | 單元數 = M·N·P。64 → 16 時,G_beam 峰值 18 dB → 12 dB,主瓣寬約兩倍,可同時服務的 MU 用戶數下降 | 無 | TR 38.901 §7.3.0;O-RAN MP tx-arrays number-of-rows / columns / array-layers;polarisations list min 1 max 2 | [ORAN-N] / [3GPP-TR] |
| 1.2 | 單元間距 d_H, d_V | 換硬體;**DT 直接改** | O-RAN MP horizontal-spacing / vertical-spacing:decimal64 公尺,無範圍;38.901 校準用 0.5λ / 0.7λ | 間距 > 0.5λ 會出現柵瓣(grating lobe),同一組權重 w 指向改變;間距縮小則主瓣變寬 | 無 | O-RAN MP tx-arrays spacing;TR 38.901 Table 7.8-6A | [ORAN-N] / [3GPP-TR] |
| 1.3 | 單元場型(θ3dB, φ3dB, SLA_V, A_max, G_E,max) | 換硬體;**DT 直接改** | 校準值 65° / 65° / 30 dB / 30 dB / 8 dBi;商用天線為廠商 datasheet | 決定 G_elem(θ″, φ″) 的包絡,所有波束掃到偏角時的衰減速度;偏 40° 時 G_elem 由 8 掉到 3.5 dBi | 無 | TR 38.901 Table 7.3-1 | [3GPP-TR];商用值 [SIM] |
| 1.4 | 方位角 α(bearing) | 爬塔;ALD 可讀 `antenna_bearing`;**DT 直接改** | 38.901:實數 (°);37.466 device data 0x25:uint16 0..3599,單位 0.1° | 整個扇區的所有波束一起水平轉向;三扇區校準預設 30 / 150 / 270 | 無 | TR 38.901 §7.1.3;TS 37.466 Annex B Table B.1 field 0x25 | [3GPP-TR] / [3GPP-N] |
| 1.5 | 機械下傾 | 爬塔;ALD 可讀寫 `installed_mechanical_tilt`;**DT 直接改** | 37.466 device data 0x26:int16,單位 0.1°;規範不限範圍 | 整組波束一起往下壓;與 1.6、2.5 三種下傾相加 | 無 | TS 37.466 Annex B Table B.1 field 0x26 | [3GPP-N] |
| 1.6 | RET 電調下傾 | ALD SetTilt(0x33);**DT 直接改** | int16,單位 0.1°,正值向下;上下限由天線 device data 0x06 / 0x07 自報 | 天線內移相器改變所有單元的垂直相位梯度,主瓣仰角整體下壓;不改變方位 | 天線支援 RET;ALD 連線 | TS 37.466 §3.1、§6.6.3、Annex B | [3GPP-N] |
| 1.7 | 天線高度 h | 爬塔;**DT 直接改** | 無區間;38.901 場景值 UMa 25 m、UMi 10 m、InH 3 m | 改變每個 UE 的 (θ″, φ″) 與距離 d,間接改變 G_elem、G_beam、PL | 無 | TR 38.901 §7.2 場景表 | [3GPP-TR] |

---

## 2. 第 ② 層:O-RU 設定(M-plane,半靜態)

NETCONF 寫入 O-RU 的 YANG rw 葉或 RPC。這是真實 RAN 中「不用改 RRC、也不用每 slot 下命令」就能改變波束的地方。

| # | 參數 | 誰能改 | 值域(規範原文) | 轉了會變什麼(64T64R 例) | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|---|
| 2.1 | `tx-array-carriers/active` | O-DU / SMO NETCONF | enum {INACTIVE, SLEEP, ACTIVE} | 載波開關;SLEEP 為節能狀態。INACTIVE 時該載波所有波束消失 | 載波已建立 | O-RAN MP UP tx-array-carriers(rw);MP-085 | [ORAN-N] |
| 2.2 | `tx-array-carriers/gain` | NETCONF | decimal64 fd4,dB,mandatory;需在 tx-arrays `min-gain`..`max-gain` 之內(RU 自報) | 直接改 P_Tx,所有波束 RSRP 同步平移 | 2.1 | O-RAN MP UP tx-array-carriers;MP-011 | [ORAN-N] |
| 2.3 | `carrier-max-power-reduction` | NETCONF | dB,≥ 0 | 載波功率上限往下壓,等效降低 P_Tx | 2.1 | O-RAN MP UP tx-array-carriers | [ORAN-N] |
| 2.4 | `max-power-control-config/max-power-level-index` | NETCONF | leafref → tx-arrays `supported-max-power-level/index`;index 0 = 不降功率 | 整片陣列 PA 上限分級下調;O-DU 須先減少排程 PRB 再寫入 | RU 支援 MAX-POWER-CONTROL;RU 宣告 supported-max-power-level 清單 | O-RAN MP §20.6;MP-125 | [ORAN-N] |
| 2.5 | RPC `modify-predefined-beam-tilt-offset` elevation / azimuth | NETCONF RPC | int16 −90..90,單位度,default 0;實際生效角 = (angle DIV granularity) × granularity;granularity uint8 0..30,0 = 不支援;elevation 負值朝天頂,azimuth 正值向右 | 整組預定義波束(GoB)數位平移,不動硬體、不改權重檔;例如 elevation +3 → 全部波束下壓 3° | RU 支援 BEAM-TILT;min/max-supported-tilt-offset 內;`run-time-tilt-offset-supported` 為 false 時須先把該頻段 array-carrier 設 INACTIVE | O-RAN MP §15.4.4;MP-049;CUS-012 | [ORAN-N] |
| 2.6 | RPC `activate-beamforming-config-by-capability-group` | NETCONF RPC | input:`beamforming-config-file`(string,須在 o-ran/beamforming/ 資料夾);回 ACCEPTED / REJECTED | 整批替換 beamId → 權重 w 的對應表,等於換一套 GoB 設計;失敗自動回復出廠檔 | 權重檔已上傳;每 capabilities-group 至少 2 個檔(出廠唯讀 + 可改) | O-RAN MP §15.4.3;MP-047 / MP-048 | [ORAN-N];**檔案內容格式** [SIM](implementation specific) |
| 2.7 | `tx-array-carriers/configured-tx-beamId-table-index` | NETCONF | uint8 1..255;index 1 永遠是全域預設表(大小 32767) | 切換到另一張 beamId 表;同一 beamId 在不同表可對應不同權重 | `general-config/multiple-beamId-tables-support-enabled` = true;RU 宣告 `max-beamId-tables-supported` | O-RAN MP §15.4.6;MP-050b | [ORAN-N] |
| 2.8 | `tx-array-antenna-mask-config/antenna-bitmask` + `antenna-bitmask-index` | NETCONF | binary,長度 = 最大陣列單元數,1 = 開 0 = 關,base64 編碼;預設全 1;清單中必含全 1 項 | 關掉部分單元:有效孔徑縮小 → 主瓣變寬、G_beam 峰值降(64 → 32 單元約 −3 dB)、可能破壞原權重檔的波束形狀 | RU 支援 MPLANE-TRX-CONTROL;mask 須對「最大陣列」設定;與 C-plane TRX control(4.6)互斥,一方非全 1 時另一方必須全 1 | O-RAN MP §20.3.2;MP-122 | [ORAN-N] |
| 2.9 | `null-steering-info/intended-null{id, azimuth-angle, zenith-angle, null-width, null-freq}` | NETCONF | azimuth int16 0.1°(可省略,省略則為 elevation null stripe);zenith int16 0.1° mandatory;null-width uint8 default 1;null-freq uint32;角度用 CUS §12.5.2 陣列座標系 | RU 重算預定義波束的權重,在指定方向壓出零點;用來抑制往鄰區或特定建物的干擾 | RU 宣告 `null-steering-capability`;可用 `beam-id-ranges-in-scope` 限定哪些 beamId 受影響(需 BEAM-ID-SCOPE-NULLING) | O-RAN MP §15.4.7;MP-130 / MP-131;CUS §12.4.2.3 | [ORAN-N] |
| 2.10 | `low-level-tx-endpoints/bf-methods` + `configured-bf-profile-id` | NETCONF | bf-methods leaf-list ⊂ {NOBF, PDBF, WDBF, ABBF, CIBF, DMRS_BF_EQ, DMRS_BF_NEQ};profile-id 指向 RU 宣告的 endpoint-bf-profile-group | 決定這條 eAxC 之後在 C-plane 可以用哪種方式指定波束(查表 / 送權重 / 送角度 / 送通道) | RU 的 endpoint-bf-profile-group(ro)有列出該方法 | O-RAN MP UP low-level-tx-endpoints(rw);MP-050 / MP-061 | [ORAN-N] |
| 2.11 | `low-level-tx-endpoints/e-axcid` | NETCONF | DU_Port / BandSector / CC / RU_Port 四段 bitmask,合計 ≤ 16 bit,須互斥且連續 | 決定 C-plane 每條資料流的門牌號;改錯會讓 beamId 送到錯的 port | 與 O-DU 設定一致 | O-RAN CUS §5.1.3.2.7;MP-050 | [ORAN-N] |

---

## 3. 第 ③ 層:小區與 UE 無線資源設定(RRC)

CU / DU 寫在 RRC 訊息裡,UE 收到才生效。這一層決定「UE 看得到幾個 port、量哪個波束、回報什麼、最多幾層」。

### 3.1 SSB(初始接入波束掃描)

| # | 參數 | 值域(規範原文) | 轉了會變什麼 | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|
| 3.1.1 | `ssb-PositionsInBurst` | BIT STRING,長度 L_max ∈ {4, 8, 64}(依頻段 case);最左 bit 對應 index 0 | 選哪幾個時間位置真的發 SSB,等於選「掃幾個方向」;8 bit 全 1 = 掃 8 束,只開 4 bit = 掃 4 束 | 頻段決定 L_max | TS 38.331 ServingCellConfigCommon;TS 38.213 §4.1;331-030 | [3GPP-N] |
| 3.1.2 | `ssb-periodicityServingCell` | ENUMERATED {ms5, ms10, ms20, ms40, ms80, ms160};缺省 5 ms | 掃描週期;越長省資源,UE 初始接入與波束量測越慢 | 無 | TS 38.331 p.1232;331-030 | [3GPP-N] |
| 3.1.3 | SSB index → beamId 對應表 | 規範未定義 | 決定第 i 個 SSB 用 RU 的哪個 beamId 發;是把 UE 回報的 SSB index 換回波束的唯一途徑 | 2.6 的權重表要有對應的 beamId | 本專案 schema `ssb_to_beam_map` | **[SIM]** |

### 3.2 CSI-RS 資源(讓 UE 量細波束與通道)

| # | 參數 | 值域(規範原文) | 轉了會變什麼 | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|
| 3.2.1 | `nrofPorts` | ENUMERATED {p1, p2, p4, p8, p12, p16, p24, p32};Rel-19 可聚合 2–4 組至 48 / 64 / 128 | UE 看到的 H_eff 欄數 P;P 越大通道資訊越細,但 CSI-RS 開銷與回報量越大 | RU 的 TXRU / spatial streams ≥ P | TS 38.331 CSI-RS-ResourceMapping;TS 38.211 §7.4.1.5;331-002 | [3GPP-N] |
| 3.2.2 | `frequencyDomainAllocation` / `firstOFDMSymbolInTimeDomain` / `cdm-Type` / `density` | row1 4 bit、row2 12 bit、row4 3 bit、其他 6 bit;symbol 0..13;cdm 依 38.211 Table 7.4.1.5.3-1;density {dot5, one, three} | 決定 CSI-RS 佔哪些 RE;影響開銷與量測精度,不影響波束本身 | 與 nrofPorts 組合須在 Table 7.4.1.5.3-1 的合法列 | TS 38.211 Table 7.4.1.5.3-1;331-002 | [3GPP-N] |
| 3.2.3 | `periodicityAndOffset` | CHOICE slots4 … slots640 + offset(CSI-ResourcePeriodicityAndOffset) | 量測更新頻率;MU-MIMO 與高速 UE 需要短週期 | resourceType = periodic / semiPersistent | TS 38.331 NZP-CSI-RS-Resource;331-001 | [3GPP-N] |
| 3.2.4 | `powerControlOffset` / `powerControlOffsetSS` | INTEGER (−8..15) dB;ENUMERATED {db-3, db0, db3, db6} | CSI-RS 相對 PDSCH / SSB 的功率偏移;會直接出現在 CSI-RSRP 數值裡,扣天線效應時要一併扣 | 無 | TS 38.331 p.1022;331-001 | [3GPP-N] |
| 3.2.5 | `qcl-InfoPeriodicCSI-RS`(指向 TCI state) | TCI-StateId;typeD 來源可為 SSB 或另一個 periodic CSI-RS | 告訴 UE「這組 CSI-RS 跟哪個 SSB 波束同方向」,UE 才知道用哪個接收波束去量 | TCI state 已設定(3.4.3) | TS 38.214 §5.2.2.3.1;331-001 | [3GPP-N] |
| 3.2.6 | CSI-RS resource → beamId 對應 | 規範未定義;O-RU 側可用 SE19 以 port 為單位帶 beamId | 決定每組 CSI-RS 實際用哪個細波束發;是波束管理(P2)細掃的核心 | 2.6 權重表 | 本專案 schema `beam_id_oru`;CUS-056 | **[SIM]** |
| 3.2.7 | resource set `repetition` | ENUMERATED {on, off},缺省 off | on = 同一波束重複發,讓 UE 掃自己的接收波束(P3);off = 基站換波束讓 UE 挑(P2) | repetition = on 時 reportQuantity 只能是 cri-RSRP / cri-SINR / none,且 nrofPorts ∈ {1, 2} | TS 38.214 §5.2.2.3.1;331-005;V-38 | [3GPP-N] |

### 3.3 CSI 回報設定(UE 回報什麼、碼本幾頁、允許幾層)

| # | 參數 | 值域(規範原文) | 轉了會變什麼 | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|
| 3.3.1 | `reportQuantity` | ENUMERATED {none, cri-RI-PMI-CQI, cri-RI-i1, cri-RI-i1-CQI, cri-RI-CQI, cri-RSRP, cri-SINR, ssb-Index-RSRP, ssb-Index-SINR, cri-RI-LI-PMI-CQI, …} | 決定 UE 回報的是波束強度(RSRP)還是通道結構(PMI / RI);要做 MU-MIMO 必須有 PMI | 無 | TS 38.331 CSI-ReportConfig;331-008 | [3GPP-N] |
| 3.3.2 | `reportConfigType` | CHOICE {periodic, semiPersistentOnPUCCH, semiPersistentOnPUSCH, aperiodic} + 週期 | 回報多久一次;影響基站更新 W 與 beamId 的速度 | 無 | TS 38.331 p.850;331-008 | [3GPP-N] |
| 3.3.3 | `codebookType` | CHOICE:typeI-SinglePanel / typeI-MultiPanel / typeII / typeII-PortSelection / typeII-r16 / -r17 / -r18 / -r19 …,只能擇一 | **決定 rank 上限與通道解析度**:Type I SP ≤ 8 層、Type I MP ≤ 4、Type II(Rel-15)≤ 2、eType II ≤ 4;Type II 才有足夠解析度做 MU-MIMO 零點對準 | port 數須在該碼本支援清單內 | TS 38.214 §5.2.2.2;TS 38.331 CodebookConfig;331-009;codebook_catalog | [3GPP-N] |
| 3.3.4 | `n1`, `n2`(+ `ng`) | (N1, N2) 依 TS 38.214 Table 5.2.2.2.1-2,需 2·N1·N2 = P;Ng ∈ {2, 4} | 告訴 UE 碼本的 DFT 格點怎麼排,必須跟 RU 的 port 幾何一致,否則 PMI 指向的方向是錯的 | 3.2.1 的 P | TS 38.214 Table 5.2.2.2.1-2;V-01 / V-02 | [3GPP-N] |
| 3.3.5 | `codebookMode` | INTEGER (1..2);r19 為 {modeA, modeB} | 改變 PMI 索引 i2 的解析度(mode 2 多一倍相位候選);Ng = 4 時只能 mode 1 | 3.3.3 | TS 38.214 §5.2.2.2.1;331-009 | [3GPP-N] |
| 3.3.6 | `codebookSubsetRestriction`(CBSR) | BIT STRING,長度 Ac = N1·O1·N2·O2(Type I SP);bit = 0 的頁碼 UE 不得回報 | **直接限制 UE 能選哪些 DFT 方向**:把指向鄰區的頁碼設 0,就能避免 UE 把波束拉向干擾方向 | 3.3.3、3.3.4 | TS 38.214 §5.2.2.2.1;331-009;V-08 | [3GPP-N] |
| 3.3.7 | `ri-Restriction` | BIT STRING:Type I SP 8 bit、MP 4 bit、Type II 2 bit、eType II 4 bit;bit r−1 = 0 則不得回報 rank r | 限制 UE 可回報的層數;例如只開 bit 0、1 → UE 最多建議 2 層 | 3.3.3 | TS 38.214 §5.2.2.2;331-009;V-10 | [3GPP-N] |
| 3.3.8 | Type II 專屬:`numberOfBeams` L / `phaseAlphabetSize` / `subbandAmplitude` / `paramCombination` | L ∈ {2, 3, 4}(P = 4 時只能 2);NPSK ∈ {4, 8};bool;r16 paramCombination 1..8 | L 越大、NPSK 越大,UE 描述通道越精細,回報 bit 越多;MU 零點對準品質直接受此影響 | codebookType 為 Type II 系 | TS 38.214 §5.2.2.2.3 / .5;331-009 | [3GPP-N] |
| 3.3.9 | `nrofReportedRS` / `groupBasedBeamReporting` | ENUMERATED {n1, n2, n3, n4}(v1900 另有 n6, n8);bool,default false | 一次回報幾個最強波束;group-based = true 固定回 2 個可同時接收的波束 | reportQuantity 為 cri-RSRP / ssb-Index-RSRP 類 | TS 38.331 p.848–849;331-008;V-39 | [3GPP-N] |
| 3.3.10 | `portSubsetIndicator`(r19) | BIT STRING 1..32(r19 至 128),bit i 對應 port 3000+i | 只讓 UE 用部分 port 算 CSI,等於在 port 層再做一次子陣列選擇 | 3.2.1 | TS 38.214 §5.2.2.2;214-069 | [3GPP-N] |

### 3.4 PDSCH / PUSCH / TCI(層數上限與波束參考)

| # | 參數 | 值域(規範原文) | 轉了會變什麼 | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|
| 3.4.1 | `maxMIMO-Layers`(PDSCH-ServingCellConfig,cell 級;PDSCH-Config maxMIMO-Layers-r16,BWP 級) | INTEGER (1..8);BWP 未設時沿用 cell 值 | 下行層數硬上限;實際 r = min{此值, UE 能力, 碼本 rank 上限, P} | 無 | TS 38.331 p.1051、p.1061;331-012 / 331-013;V-11 | [3GPP-N] |
| 3.4.2 | `DMRS-DownlinkConfig`:`dmrs-Type`、`maxLength`、`dmrs-AdditionalPosition`、`dmrs-TypeEnh-r18` | dmrs-Type {type2}(缺省 type1);maxLength {len2}(缺省單符號);additionalPosition {pos0, pos1, pos3}(缺省 pos2) | 決定正交 DM-RS port 數:type1 單符號 4、雙符號 8;type2 單符號 6、雙符號 12;enhanced 至 16 / 24。**這是 SU 層數與 MU 配對總層數的天花板** | 無 | TS 38.331 p.870–871;TS 38.211 §7.4.1.1;331-014;V-15 | [3GPP-N] |
| 3.4.3 | `tci-StatesToAddModList`(每個 TCI-State 含 qcl-Type1 / qcl-Type2 → SSB 或 CSI-RS) | SEQUENCE SIZE (1..maxNrofTCI-States = 128);UE 能力 {4, 8, 16, 32, 64, 128};MAC CE 一次啟用 ≤ 8 個 codepoint | 定義「PDSCH 用哪個波束發」的候選清單;DCI 的 3 bit TCI 欄位從已啟用的 8 個中選 | CSI-RS / SSB 已配置 | TS 38.331 PDSCH-Config;TS 38.214 §5.1.5;331-012;V-37 | [3GPP-N] |
| 3.4.4 | PUSCH `txConfig` / `maxRank` / `codebookSubset` | ENUMERATED {codebook, nonCodebook};INTEGER (1..4)(v1810 可至 8);ENUMERATED {fullyAndPartialAndNonCoherent, partialAndNonCoherent, nonCoherent} | 上行層數上限與 UE 可用的預編碼子集;nonCodebook 時每個 SRS resource 只能 1 port | UE 能力 | TS 38.331 PUSCH-Config;331-016 / 331-017;V-17 / V-18 | [3GPP-N] |
| 3.4.5 | SRS resource set `usage` | ENUMERATED {beamManagement, codebook, nonCodebook, antennaSwitching} | 決定上行參考訊號拿來做什麼;`beamManagement` 的 SRS 是 RU 做 DMRS-BF / CIBF 的輸入 | 無 | TS 38.331 SRS-ResourceSet | [3GPP-N] |

---

## 4. 第 ④ 層:逐 slot 排程命令(C-plane)

O-DU 排程器每個 slot 下給 O-RU 的命令。這一層才是「此時此刻這塊 PRB 用哪個波束」。

| # | 參數 | 值域(規範原文) | 轉了會變什麼 | 前置條件 | 出處 | 類型 |
|---|---|---|---|---|---|---|
| 4.1 | `beamId`(每個 section) | 15 bit,0..32767;0 = 不做 BF(訊號平均送到所有單元);有效值須落在該 eAxC 的 [initial-beam-id, initial-beam-id + max-number-of-beam-ids − 1];同 symbol 內不同 beamId 數 ≤ `max-beams-per-symbol` | **最直接的旋鈕**:這塊 PRB、這個 symbol 用哪個預定義波束。G_beam 隨之逐 slot 變 | 2.10 設為 PDBF / WDBF / ABBF;beamId 在 2.6 的表裡存在 | O-RAN CUS §7.5.3.9、§12.4.2.1;CUS-033;V-20 / V-21 / V-22 | [ORAN-N] |
| 4.2 | WDBF 權重向量(SE1 / SE11 / SE19:bfwCompHdr、bfwCompParam、bfwI / bfwQ) | K 個複數,K = 單元數;壓縮前 |I|, |Q| ≤ 1;壓縮方式與位寬由 bfwCompHdr 指定;**同一 slot 每個 beamId 最多更新一次**,要不同權重就換 beamId | 直接給 64 個單元的振幅相位,任意波束形狀、任意方向、可含零點;是 DT 裡「完全自由設計波束」的入口 | 2.10 含 WDBF;RU `rt-bf-weights-update-support`;beam-update-contention-control 設定 | O-RAN CUS §12.4.3、§7.7.1;CUS-014 / CUS-016;V-23 / V-24 | [ORAN-N] |
| 4.3 | ABBF 屬性(SE2:bfAzPt、bfZePt、bfAz3dd、bfZe3dd、bfAzSl、bfZeSl) | 四個角度欄位各 0–8 bit(位寬由 bfaCompHdr 指定,000b = 不帶);bfAzPt 有號、其餘無號,單位度,**有效範圍 O-RU 自報**;旁瓣抑制 3 bit:10 dB + 5 dB × code,111b ≥ 45 dB;角度依 38.901 §7.1 LCS(φ′, θ′) | 不用算權重,直接告訴 RU「方位 20°、仰角 95°、寬 15°、旁瓣壓 25 dB」,RU 自己合成;適合前端直接操作 | 2.10 含 ABBF;同一 RE 上所有 layer 必須都用 ABBF | O-RAN CUS §7.7.2、§12.4.4;CUS-020 / CUS-042;MP `beamforming-trough-attributes-supported` | [ORAN-N];角度量化步距 [SIM](CUS 未定) |
| 4.4 | ueId 類(ST5 + SE5 / SE24 / SE32 等):CIBF 通道資訊、DMRS-BF 的 ueId 與 layer | ueId 15 bit;layer bits 由 `ueid-max-layer-bits` 1..4 宣告;RU 支援 UE 數 ≤ `max-number-of-ues` | 不指定波束,RU 依 UE 的上行通道(SRS / DMRS)自己算 w;是 MU-MIMO 下最常見的 Cat B 做法,但 DU 看不到 RU 實際用的 w | 2.10 含 CIBF / DMRS_BF_*;RU 宣告 ue-specific-beamforming 能力;3.4.5 SRS usage | O-RAN CUS §12.4.5–12.4.6;CUS-010 / CUS-024;MP-046 | [ORAN-N];RU 內部演算法 [SIM] |
| 4.5 | Section 的 PRB / symbol 範圍(startPrbc、numPrbc、startSymbolId、numSymbol)+ 每 section 的 beamId | PRB 0..273、symbol 0..13 | 同一 slot 內不同 PRB 可用不同 beamId:這就是 MU-MIMO 在頻域上的實作;以及 FDM 多波束 | 4.1 | O-RAN CUS §7.5.3 | [ORAN-N] |
| 4.6 | C-plane TRX control(ST7 / SE 之一,antenna mask + sleep mode) | mask 來自 RU 宣告的 `supported-trx-control-masks`;sleep-mode-type SLEEP_MODE_0–3;wake-up-duration µs | 逐 slot 關閉部分單元節能;效果同 2.8 但可短時間切換 | RU 支援 TRX-CONTROL;**M-plane mask(2.8)必須為全 1** | O-RAN MP §20.3.1;MP-121 / MP-122;V-45 | [ORAN-N] |
| 4.7 | DCI 內的 TCI codepoint、antenna port 欄位、MCS | TCI 0..7(3 bit,從已啟用 ≤ 8 個 TCI state 選);antenna ports 依 38.212 表;MCS 0..31 | UE 端對應:用哪個接收波束、哪些 DM-RS port、什麼調變碼率 | 3.4.3 TCI 已啟用 | TS 38.212 §7.3.1;TS 38.214 §5.1.5 | [3GPP-N] |

---

## 5. 第 ⑤ 層:排程器政策(規範不管)

規範只定介面與上限,以下決策全部由廠商演算法或 DT 自行設計。真實 RAN 沒有標準介面可改,DT 裡則是最核心的「行為」參數。

| # | 決策 | 規範給的約束 | 轉了會變什麼 | 出處 | 類型 |
|---|---|---|---|---|---|
| 5.1 | SSB index ↔ beamId 對應 | 無 | 決定初始接入後 UE 落在哪個粗波束 | — | [SIM] |
| 5.2 | 粗波束 → 細波束的候選集合(coarse-fine relation) | YANG `coarse-fine-beam-capability-based-relation`(RU 自報哪些細波束屬於哪個粗波束);`beam-group-id` 相同者可同時發 | 決定 P2 階段 CSI-RS 要配哪幾個細波束讓 UE 挑 | O-RAN CUS §12.4.2.2;MP-045 | [ORAN-N] 約束 + [SIM] 選法 |
| 5.3 | 波束切換判準(用 L1-RSRP 差幾 dB、持續幾次才換) | 回報格式:L1-RSRP 7 bit −140..−44 dBm;差分 4 bit 步進 2 dB | 影響 beamId 隨時間跳動的頻率,直接影響實測 RSRP 時間序列的平穩度 | TS 38.133 Table 10.1.6.1-1 / -2 | [SIM] |
| 5.4 | 預編碼 W 的來源:採 UE 的 PMI,或用 SRS 估計做 ZF / MMSE | Cat A:W 在 O-DU 算,前傳送 precoded stream(≥ 8 條);Cat B:W 在 O-RU 併入 BF 權重 | 決定 SU 層間漏與 MU 配對干擾的大小;ZF 理論上把 Σ_{j≠k} H_k W_j 壓到零 | O-RAN CUS §4.2;CUS-001 / CUS-002 | [SIM] |
| 5.5 | MU-MIMO 配對準則(波束正交度門檻、SINR 下限、最大配對數) | 每 UE ≤ 4 個 DM-RS port(38.300);總 DM-RS port 數 ≤ 3.4.2 的上限;overlapping beams 不得同時排程,neighbouring beams 應避免 | 決定同一 PRB 同時服務幾支 UE、彼此干擾多少 | TS 38.300 §5.2.1;O-RAN CUS §12.4.2.2 | [SIM] |
| 5.6 | 層數選擇(是否照 UE 的 RI,或保守取較小值) | r ≤ min{3.4.1, UE 能力, 碼本 rank 上限, P} | 影響 Throughput 與 BLER 的取捨 | V-11 | [SIM] |
| 5.7 | 鄰區波束協調(同時避免兩個扇區的波束對準同一區) | 無 | 影響鄰居干擾項 Σ RSRP_n 的大小 | — | [SIM] |
| 5.8 | CSI-RS 與 SSB 的功率分配(3.2.4 的設定策略) | 值域見 3.2.4 | 影響 CSI-RSRP 與 SS-RSRP 之間的固定偏移 | — | [SIM] |

---

## 6. 操作鏈:想要 X,依序動哪些旋鈕

每一步標明層別與是否為標準介面。「標準」= 真實 RAN 可透過 M-plane / RRC / C-plane 做;「DT」= 只有模擬器能直接改,或要向廠商取得。

### 6.1 想讓某個波束指向特定方向(例如方位 +20°、下壓 6°)

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ② | 若只要整組波束平移:RPC `modify-predefined-beam-tilt-offset`(2.5) | 標準 |
| b | ② | 若要換一套 GoB:上傳新權重檔並 `activate-beamforming-config-by-capability-group`(2.6) | 標準介面,**檔案內容 DT / 廠商** |
| c | ④ | 若 RU 支援 ABBF:C-plane SE2 直接給 bfAzPt = 20、bfZePt = 96、寬度(4.3) | 標準 |
| d | ④ | 若 RU 支援 WDBF:自己算 64 個權重(例如 DFT 向量指向該方向)經 SE1 送出(4.2) | 標準介面,**權重設計 DT** |
| e | ① | 若要所有波束一起動:改 RET(1.6)或機械下傾(1.5) | 標準(ALD)/ 爬塔 |

### 6.2 想讓 UE 量得到這個波束並回報

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ③ | 配一組 NZP-CSI-RS resource,`nrofPorts`(3.2.1)、週期(3.2.3) | 標準 |
| b | ③ | `qcl-InfoPeriodicCSI-RS` 指向該波束所屬 SSB 的 TCI state(3.2.5、3.4.3) | 標準 |
| c | ④/⑤ | 讓 RU 真的用該 beamId 發這組 CSI-RS(3.2.6 對應表;SE19 可逐 port 帶 beamId) | **DT / 廠商** |
| d | ③ | CSI-ReportConfig `reportQuantity` = cri-RSRP 或 cri-RI-PMI-CQI(3.3.1) | 標準 |

### 6.3 想決定 SU-MIMO 傳幾層

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ③ | `maxMIMO-Layers`(3.4.1)設上限 | 標準 |
| b | ③ | 選 `codebookType`(3.3.3):要 8 層必須 Type I Single-Panel;Type II 鎖在 2 | 標準 |
| c | ③ | `ri-Restriction`(3.3.7)再收窄 | 標準 |
| d | ③ | `DMRS-DownlinkConfig`(3.4.2):type1 雙符號才有 8 個正交 port | 標準 |
| e | ③ | `nrofPorts`(3.2.1)≥ 目標層數 | 標準 |
| f | ⑤ | 排程器是否照 RI(5.6) | DT |

### 6.4 想開 MU-MIMO

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ③ | `codebookType` 選 Type II 或 eType II(3.3.3、3.3.8),Type I 的解析度不足以對準零點 | 標準 |
| b | ③ | `DMRS-DownlinkConfig` 開 type2 或雙符號(3.4.2),確保總 port 數夠配對 | 標準 |
| c | ③ | SRS `usage` = codebook / antennaSwitching(3.4.5),給 RU 上行通道做 CIBF / DMRS-BF 的輸入 | 標準 |
| d | ② | `bf-methods` 含 CIBF 或 DMRS_BF_*(2.10),Cat B 才能在 RU 內做 UE-specific 預編碼 | 標準 |
| e | ④ | 同一 slot、同一 PRB 範圍下兩個 section,各帶不同 ueId(4.4)或不同 beamId(4.1、4.5) | 標準 |
| f | ⑤ | 配對準則(5.5)、W 來源 ZF / PMI(5.4) | **DT** |

### 6.5 想縮小孔徑或節能(關掉部分單元)

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ② | 半靜態:`tx-array-antenna-mask-config`(2.8) | 標準 |
| b | ④ | 逐 slot:C-plane TRX control(4.6),前提 M-plane mask 全 1 | 標準 |
| c | ② | 只降功率不關單元:`max-power-level-index`(2.4)或 `carrier-max-power-reduction`(2.3) | 標準 |
| d | ④ | 關單元後原權重檔的波束形狀會變,WDBF 要重算 w(4.2) | DT |

### 6.6 想壓掉某個方向的干擾

| 步 | 層 | 動作 | 標準 / DT |
|---|---|---|---|
| a | ② | `null-steering-info/intended-null`(2.9)給方位、天頂、寬度 | 標準 |
| b | ③ | `codebookSubsetRestriction`(3.3.6)把指向該方向的 PMI 頁碼設 0 | 標準 |
| c | ④ | ABBF `bfAzSl` / `bfZeSl`(4.3)提高旁瓣抑制 | 標準 |
| d | ④ | WDBF 自算含零點的權重(4.2) | DT |

---

## 7. 參數之間的相依與互斥(改一個要檢查另一個)

| 規則 | 涉及參數 | 出處 |
|---|---|---|
| M-plane antenna mask 與 C-plane TRX control 不得同時非全 1 | 2.8 ↔ 4.6 | MP §20.3.2.5;V-45 |
| 切換 beamId 表前,`multiple-beamId-tables-support-enabled` 必須先為 true,且 index 1 永遠是全域預設表 | 2.7 | MP §15.4.6 |
| tilt offset 必須是 granularity 的整數倍,且在 RU 宣告的 min / max 之內;`run-time-tilt-offset-supported` = false 時要先把 array-carrier 設 INACTIVE | 2.5 ↔ 2.1 | MP-049;V-44 |
| beamId 必須落在該 eAxC 的 [initial, initial + max − 1];0 保留給不做 BF;不支援 BF 的 RU 只能收 0 | 4.1 ↔ 2.10 | CUS §12.4.2.1;V-20 / V-21 |
| 同一 slot 每個 beamId 權重最多更新一次;要不同權重就換 beamId | 4.2 | CUS §12.4.3.1;V-23 |
| 權重個數 = M·N·P·Q(單元總數);mask 長度 ≥ 單元數 | 4.2 ↔ 1.1 ↔ 2.8 | CUS-071 / CUS-041;V-24 |
| ABBF / CIBF:同一 RE 上所有 layer 必須用同一種 BF 方法 | 4.3 / 4.4 | CUS §12.4.1 c) |
| 同一 symbol 內不同 beamId 數 ≤ `max-beams-per-symbol`;同一 slot ≤ `max-beams-per-slot` | 4.1 / 4.5 | MP-062;V-22 |
| Type I SP:2·N1·N2 = nrofPorts 且 (P, N1, N2) 在 Table 5.2.2.2.1-2;Type I MP:2·Ng·N1·N2 = P,Ng = 4 時 codebookMode 只能 1 | 3.3.3 ↔ 3.3.4 ↔ 3.3.5 ↔ 3.2.1 | TS 38.214;V-01 / V-02 |
| CBSR 長度 = N1·O1·N2·O2;ri-Restriction 長度依碼本種類 8 / 4 / 2 / 4 | 3.3.6 / 3.3.7 ↔ 3.3.3 | V-08 / V-10 |
| 實際層數 r ≤ min{maxMIMO-Layers(cell, BWP), UE 能力, 碼本 rank 上限, P};r ≤ 4 用 1 個 codeword,5–8 用 2 個 | 3.4.1 ↔ 3.3.3 ↔ 3.2.1 | V-11 / V-14 |
| DM-RS port 數 = 層數;MU-MIMO 每 UE ≤ 4 個 DM-RS port | 3.4.2 ↔ 3.4.1 ↔ 5.5 | TS 38.300 §5.2.1;V-15 |
| repetition = on 時 reportQuantity 只能 cri-RSRP / cri-SINR / none,且 nrofPorts ∈ {1, 2} | 3.2.7 ↔ 3.3.1 ↔ 3.2.1 | TS 38.214 §5.2.2.3.1;V-38 |
| group-based beam reporting = true 時固定回 2 個 RS | 3.3.9 | V-39 |
| TCI state 總數 ≤ min(128, UE 能力);MAC CE 啟用 ≤ 8;unified TCI ≤ 16 | 3.4.3 | V-37 |
| nonCodebook PUSCH 時每個 SRS resource 只能 1 port;transform precoding 時 PUSCH 只能 1 層 | 3.4.4 ↔ 3.4.5 | V-17 / V-18 |
| Cat A O-RU 每片陣列 P = 1(預編碼在 DU,前傳送 precoded stream) | 2.10 ↔ 1.1 | CUS-005;V-29 |
| RET tilt 須在天線自報的 min / max 內,線上編碼為 0.1° 整數 | 1.6 | TS 37.466;V-54 |
| 波束改變時 TRP 不變(只要 peak 在 OTA peak directions set 內);EIRP 會變 | 任何改 w 的操作 | TS 38.104 §9.3.1;V-34 |

---

## 8. 與附錄 B(天線總表)的對照

附錄 B 描述「一支天線長什麼樣」,多數欄位是 RU 自報的能力(YANG config false)或廠商宣告,操作者不能改,只能讀來當前置條件。本表描述「操作者能轉哪些旋鈕」。

| 附錄 B 欄位 | 在本表的角色 |
|---|---|
| (M,N,P)、d_H / d_V、單元場型 | 1.1–1.3:真實 RAN 不可改,DT 可改 |
| TXRU T/R、RU Cat | 不可改;是 2.10、4.4、5.4 的前置條件 |
| CSI-RS port 數 | 3.2.1 的可寫版本(RRC 設定值 ≤ RU 能力) |
| SSB L_max | 3.1.1 的上限;positions_in_burst 是可寫的 |
| BF 方法 | RU 自報(ro)→ 2.10 從中挑選啟用 |
| beamId 區段 | RU 自報(ro)→ 4.1 必須落在其中 |
| RET 範圍 | RU / 天線自報 → 1.6 必須落在其中 |
| 碼本 / max layers | RU / UE 能力 → 3.3.3、3.4.1 的上限 |
| 高度、方位、下傾 | 1.4–1.7 |
| 每 slot 的 beamId、layers、RI / PMI / CQI、RSRP | 4.1、5.6 的結果與 UE 回報,屬量測欄位 |

---

## 9. 值域未在本地摘錄中逐字核對的項目

- 3.2.3 `CSI-ResourcePeriodicityAndOffset` 的 CHOICE 成員(slots4 … slots640):摘錄檔引用了該型別但未貼 ASN.1 定義,寫法依 TS 38.331 慣例,使用前請對 PDF。
- 4.3 ABBF 四個角度欄位的量化步距:CUS 明寫「O-RU-specific, via M-plane」,本地 YANG 未找到對應 leaf,標 [SIM]。
- 1.7 高度場景值 UMa 25 / UMi 10 / InH 3 m:出自 38.901 §7.2 場景表,摘錄檔未含原文。
