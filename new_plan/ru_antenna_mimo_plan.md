# RU 天線 / MIMO / Beamforming 模擬重新規劃(2026-09-16)

依據:3GPP TS 38.104(BS 硬體型態)、TR 38.901 §7.3(天線元件/面板模型)、TS 38.211/38.214(CSI-RS 埠與 codebook)、O-RAN WG4 CUS-plane(O-RU Cat A/B 與四種 beamforming 方法)、O-RAN WG1 使用案例(docs/MIMO)。目標:把目前 RU 的「一個 Sionna PlanarArray = 一個 gNB」模型,升級成能對應 O-RU 硬體規格與 RIC 可控 beamforming 的三層模型。

---

## 0. 現況(2026-09-16)

| 層 | 現在的做法 | 問題 |
|---|---|---|
| 天線描述 | registry `AntennaPreset`:pattern / rows / cols / polarization / spacing / max_gain。scene 層級一組 gNB 陣列 + 一組 UE 陣列 | 沒有「元件 vs TRX vs 邏輯埠」的分層:rows×cols 直接當 Sionna 元件,也直接當 CSI-RS 埠。沒有面板(Mg,Ng)、沒有子陣列、沒有機械/電子下傾分離 |
| 物理 | Sionna `PlanarArray`(tx/rx 各一,scene-global),每 tick 回 H (rx_ant × tx_ant) 與 per-port path gain;方位 α=90°−az、tilt 進 orientation | Sionna 陣列是 scene-global → 一個 run 只能一種 gNB 陣列;cached 模式只存純量 path gain,沒有 H |
| RU beamforming | Type I 單面板 codebook(OAI 表,2/4 埠、1–4 層)由 DU 帶 PMI/layers 下來;RU 用未預編碼 H 做 SVD 估 rank 與每層 SINR | 只有 codebook precoding(= O-RAN Cat A 的 DU 側 precoding 語意),沒有 O-RU 側 beamforming;沒有 beam 概念(GoB / beam ID / weights);最多 4 埠 |
| DU | rank、每層 SINR → EESM 有效 SINR → MCS;PMI 固定 | 沒有 RI/PMI 選擇(UE 端 CSI 回報流程);沒有 SRS / 上行 CSI |
| RIC | E2SM-KPM/RC/ANR/CCC;控制只有換手、ANR、cell 參數 | 沒有任何 beam/MIMO 可觀測量或控制點 |

實測(2026-09-15 P5-5):4-port gNB / 2-port UE、單 UE LOS,rank 2 成立、每層 SINR [16.7, 9.0] dB、滿載吞吐 +24%。這條路徑是對的,但只到「單面板 codebook」。

---

## 1. 規格要點(重新規劃的依據)

### 1.1 3GPP TS 38.104:BS 硬體型態決定「我們在模擬哪一個介面」
- **BS type 1-C**:FR1,傳導要求定義在**天線接頭**(每根天線一條 RF 線,傳統 2T2R/4T4R)。
- **BS type 1-H**:FR1,傳導要求定義在 **TAB 接頭**(Transceiver Array Boundary:收發機陣列與複合天線的邊界)+ 部分 OTA 要求。這是「多 TRX + 天線陣列」的 AAS。
- **BS type 1-O / 2-O**:沒有接頭,全部 OTA(FR1 mMIMO 面板、FR2)。要求定義在 **RIB**(Radiated Interface Boundary),用 EIRP / TRP 與 beam 定義(beam peak direction、beamwidth、OTA peak directions set、OTA coverage range)。
- 對模擬的意義:**TRX 數(TAB 埠數)≠ 天線元件數 ≠ 邏輯天線埠(CSI-RS 埠)數**,三者要分開建模。O-RU 規格書寫的 32T32R / 64T64R 是 TRX 數。

### 1.2 3GPP TR 38.901 §7.3:天線元件與面板模型
- 單元件輻射圖(Table 7.3-1):垂直 A_V(θ)=−min[12((θ−90°)/65°)², 30] dB,水平 A_H(φ)=−min[12(φ/65°)², 30] dB,合成 A(θ,φ)=−min[−(A_V+A_H), 30],最大增益 **G_E,max = 8 dBi**,HPBW 65°,前後比 30 dB。Sionna 的 `tr38901` pattern 就是這個。
- 面板陣列以 **(M_g, N_g, M, N, P)** 描述:M_g×N_g 個面板,每面板 M 列 × N 行元件,P=1 或 2(雙極化 ±45°),元件間距 d_V、d_H(常用 0.5λ / 0.5λ 或 0.8λ / 0.5λ),面板間距 d_g,V、d_g,H。
- **元件 → TXRU 的映射**(TR 36.897/38.901 的「virtualization」):一個 TXRU 通常帶一整列(或一段)垂直元件,用固定相位權重做電子下傾(virtualization weights)。這就是 64T64R = 12×8×2 元件、每 TXRU 帶 3 個垂直元件那種算法(Avnet 例:12×8 陣列、32 個雙極化子陣列、每子陣列 6 元件)。

### 1.3 3GPP TS 38.211 / 38.214:邏輯埠與 codebook
- CSI-RS 埠數 ∈ {1,2,4,8,12,16,24,32}(TS 38.211 §7.4.1.5);SRS 1/2/4 埠。
- Type I 單面板 codebook(TS 38.214 Table 5.2.2.2.1-2):埠數 = 2·N1·N2,支援 (N1,N2) 組合 4:(2,1);8:(2,2)(4,1);12:(3,2)(6,1);16:(4,2)(8,1);24:(4,3)(6,2)(12,1);32:(4,4)(8,2)(16,1),過取樣 (O1,O2)=(4,4) 或 (4,1),rank 1–8,PMI = (i1,1, i1,2, [i1,3], i2)。W = W1·W2:W1 是 DFT 波束群(GoB 的數學本體),W2 是選波束 + 極化間共相。
- Type I 多面板(Table 5.2.2.2.2)、Type II(L=2/3/4 個波束線性合成、寬/子頻帶幅度、QPSK/8PSK 相位,rank ≤ 2)、eType II(Rel-16,頻域 IDFT 壓縮,rank ≤ 4)。
- **現況只實作 2/4 埠 Type I**(OAI 表);要到 8–32 埠必須改成參數化 DFT 產生器,而不是查表。

### 1.4 O-RAN WG4 CUS-plane:O-RU 的 beamforming 在哪裡做、DU 怎麼告訴它
- **Category A O-RU**:不做 precoding;DU 做 precoding 後把每個「空間流 = eAxC」的頻域 IQ 送到 RU,RU 只做 IFFT/CP/RF。適合 ≤ 8 埠。→ 我們現在的模型(DU 帶 PMI、RU 套 codebook)在語意上是 Cat A + 把 precoder 乘法放在 RU 算 SINR。
- **Category B O-RU**:RU 做 precoding / beamforming;DU 送的是 layer 資料 + beamforming 指示。mMIMO(>8 埠)必須是 Cat B。
- **四種 beamforming 方法**(C-plane section 帶):
  1. **Predefined-beam**:RU 開機經 M-plane 公告可用的 beam 集合(GoB),DU 每 section 只帶 `beamId`。
  2. **Attribute-based**:DU 帶波束屬性(方位、仰角、波束寬…),RU 自己合成權重。
  3. **Weight-based**:DU 直接帶每個 TRX 的複數權重(BFW,可壓縮),每 TTI 甚至每 symbol 換。
  4. **Channel-information-based**:DU 送 UE 的 CSI,RU 自己算權重(ZF/MMSE 等)。
- **eAxC**:fronthaul 上的資料流識別(band/sector/CC/spatial stream);Cat B 下 eAxC 數 = 層數(≤ 16 左右),不是 TRX 數。
- **O-RAN 天線模型**:M-plane 公告面板、極化、元件位置與朝向,讓 DU 能「無歧義指定天線元件」——正好對應 TR 38.901 的 (M_g,N_g,M,N,P) + 幾何。

### 1.5 O-RAN WG1 使用案例(docs/MIMO;摘要見附錄 A)
WG1 R005-v20.00 的 §4.6(mMIMO:GoB 最佳化、beam-based MRO、Cell Shaping)、§4.22(MU-MIMO)、§4.21.3.2(RF channel reconfiguration 節能)把控制分成**兩個迴路**:
- **慢迴路 O1 / OFH M-plane(Non-RT RIC / rApp,秒–分)**:水平/垂直波束寬度、波束方位、機械 RET 與每天線/每載波數位傾角、每波束最大功率、GoB pattern 表與預設 beam weight、antenna mask / TRx 開關(64→32 通道)。
- **快迴路 E2(Near-RT RIC / xApp,10–100 ms)**:MU-MIMO 用戶分組與資源指派、預編碼係數、MCS、bCIO 等波束移動性參數、SRS/CSI-RS/DMRS 回報配置。
- **RAN 要暴露的能力**:波束寬度可調範圍、方位/仰角範圍、支援的覆蓋組合、TRx mask 能力、RET/數位傾角。
- **KPI**:每波束 RSRP/RSRQ/CQI/SINR、每波束功率與 PRB、beam HO(too early/late/attempted/success/fail)與 beam failure、每 UE CQI/RI/PMI、SRS、SU/MU-MIMO 傳輸時長(E2SM-KPM §7.10.10.4/5)、NI。
docs/MIMO 的簡報 PDF 是這份規範的圖解,沒有陣列尺寸/埠數/波束數等硬體數字;那些要靠 §1.1–1.4 的 3GPP 表決定。

---

## 2. 目標模型:三層天線 + 兩種 O-RU 類別

```
[元件層]  TR 38.901 面板 (Mg,Ng,M,N,P) + 元件圖樣 + 幾何(方位、機械下傾、位置)   ← Sionna 只看這層
    │  virtualization(每 TXRU 帶哪些元件、固定相位 = 電子下傾)
[TRX 層]  TXRU 數 = O-RU 規格的 nT/nR(2T2R … 64T64R);Cat B 的 BFW 作用在這層     ← O-RAN CUS 的 BFW / beamId
    │  埠映射(CSI-RS 埠 = TRX 或 TRX 群;Cat A 時埠 = TRX)
[埠層]    CSI-RS 埠 P ∈ {2,4,8,16,32};Type I/II codebook 作用在這層                ← 3GPP 38.214;DU 的 PMI/RI
```

- **Cat A 路徑(現況升級版)**:埠 = TRX = 元件(或子陣列),DU 帶 PMI,RU 套 codebook → 現有流程,只把 codebook 換成參數化產生器,支援到 32 埠。
- **Cat B 路徑(新增)**:RU 持有 GoB(predefined)或收到 BFW/屬性,對 H(rx × 元件)套 **W_bf(元件 × 層)**;DU 只給 layer 數與 beamId / 屬性。這條路徑讓 RIC 能控 beam。
- 兩條路徑共用同一個「有效通道」抽象:`H_eff = H_elem · W_virt · W_bf(或 W_codebook)`,SINR/rank/每層 SINR 的計算(P5-4 的 SVD + EESM)不變。

---

## 3. 資料模型變更(registry `equipment_preset` / `equipment_ran`)

### 3.1 `antenna_preset` 擴充為「面板 + TRX + 埠」
| 欄位 | 意義 | 例(64T64R mMIMO) | 例(4T4R 小站) |
|---|---|---|---|
| element_pattern | tr38901 / iso / dipole | tr38901 | tr38901 |
| panels_mg, panels_ng | 面板數 | 1, 1 | 1, 1 |
| elem_rows (M), elem_cols (N) | 每面板元件 | 12, 8 | 1, 2 |
| polarization (P) | V / cross(±45°) | cross | cross |
| d_v, d_h, d_gv, d_gh | 間距(λ) | 0.8, 0.5, —, — | 0.5, 0.5 |
| max_gain_dbi | 元件最大增益 | 8 | 8 |
| trx_count | TXRU 數(T=R) | 64 | 4 |
| trx_virtualization | 每 TXRU 帶的元件(列群)+ 電子下傾 | 每 TXRU 3 個垂直元件 | 1:1 |
| electrical_tilt_deg | virtualization 相位對應的電子下傾 | 6 | 0 |
| csi_ports | 邏輯埠數 | 32 | 4 |
| port_layout (N1,N2) | 38.214 面板維度 | (4,4) | (2,1) |
| ru_category | A / B | B | A |
| bf_method | predefined / attribute / weight / channel_info(Cat B) | predefined | — |
| gob | GoB 定義(見 3.3) | 32 beams | — |

UE 側維持簡化:元件 = 埠(1/2/4),pattern iso 或 dipole。

### 3.2 `cell` 增加 beam 執行期狀態
- `mechanical_tilt_deg`(現 `tilt_deg`)、`electrical_tilt_deg`、`active_beam_set`(GoB 子集,RIC 可改)、`max_layers`、`mu_mimo_enabled`。

### 3.3 GoB(Grid of Beams)定義
- 以 38.214 的 DFT 波束定義:方位向 N1·O1 個、仰角向 N2·O2 個候選,選其中一個子集為「GoB」;每個 beam 記 `beam_id`、`(azimuth_deg, zenith_deg)`、`hpbw_az/el`、`weights(TRX×1 複數,可省略而由 DFT 生成)`。
- 這同時滿足 O-RAN predefined-beam(beamId)與 WG1 GoB 最佳化使用案例(RIC 改 beam 集合)。

---

## 4. 各系統改動

### 4.1 Physics(Sionna)
1. `PlanarArray` 改用 preset 的 (M,N,P,d_v,d_h) 建**元件層**;多面板用 Sionna 的多 `Transmitter` 或自訂位置陣列。
2. 回傳的 H 改為 **(rx_ant × tx_elem)**,不再在 physics 做 per-port 正規化(移到 RU 的 virtualization 之後)。
3. 每 tx 的 orientation 只放**機械**方位/下傾;電子下傾由 RU 的 W_virt 實現(這樣 RIC 改電子下傾不用重建 engine)。
4. cached 模式:cache 從純量 path gain 升級為**每 UE 每 cell 的 H(rx×tx_elem,複數)**或至少「每埠 gain + 主徑 AoD/ZoD」;否則 cached 模式永遠 rank 1、無 beam。建議存 `H` 的 float16 複數(18 UE × 2 cell × 4×24 = 小),24h 場景約 172,800 × 18 × 2 × 96 × 4 B ≈ 2.4 GB → 改為每 5 tick 存一筆 + 內插,或只存主徑參數重建。

### 4.2 RU(RANsim-RU)
1. `AntennaConfig` 對齊 3.1(直接吃 preset);新增 `beam` 表(GoB)與 `ru_state.active_beams`。
2. 新增 `beamforming/services/optional/virtualization.py`:由 preset 生成 W_virt(元件×TRX,含電子下傾相位)。
3. `codebook.py` 改成 **參數化 Type I 產生器**(N1,N2,O1,O2 → W1 DFT + W2 共相),涵蓋 4–32 埠、rank 1–4(先不做 Type II);保留 OAI 表當 2/4 埠回歸對照。
4. 新增 `gob.py`:由 (N1,N2,O1,O2) 生成 DFT 波束集合、算每 beam 的 (az, zen, hpbw);`beam_select`:對 H_eff 逐 beam 算增益,回報最佳 beamId 與前 K 名(給 RIC 的 beam RSRP 統計)。
5. `dl_tti_pipeline`:依 `ru_category`
   - Cat A:`H_port = H_elem·W_virt·P_port`,再 `apply_pmi`(現流程)。
   - Cat B:`H_eff = H_elem·W_virt·W_bf`,W_bf 來自 DU 的 `beam_id`(predefined)/ 屬性 / 權重;rank、每層 SINR、UL SINR 同現流程。
6. `CqiIndication` 新增 `best_beam_id`、`beam_rsrp_top_k`、`ri`、`pmi_recommended`(RU 端代 UE 做 RI/PMI 選擇:對候選 rank 與 PMI 做 SINR 窮舉,對齊 38.214 UE 行為)。

### 4.3 DU(RANsim-DU)
1. `DlPduConfig` 新增 `beam_id` / `bf_attr` / `bfw_ref`(Cat B);`layers` 改由 RU 回報的 RI 決定(取 min(RI, cell.max_layers))而非固定。
2. PMI 改用 RU 回報的 `pmi_recommended`(現在固定 0)。
3. 排程器加 **MU-MIMO 配對**(可選,第二階段):同 TTI 對不同 beam 的 UE 共用 PRB,干擾用 beam 間相關度估。
4. PM 新增每 cell 每 beam 的 PRB 使用、每 UE 的 beam_id / RI / PMI 直方圖。

### 4.4 CU / E2 / RIC
1. KPM 新增(對齊 WG1 §4.6.4 / §4.22.4 / E2SM-KPM §7.10.10):每 UE `RI`、`PMI`、`beam_id`、`beam_rsrp_top_k`、CQI;每 cell 每 beam `RSRP/SINR 分布`、`發射功率`、`PRB 使用`、beam HO 統計(too early / too late / attempted / success / fail)與 beam failure;cell 級 `SU/MU-MIMO 傳輸時長`、層數分布、NI。
2. 控制分兩層對齊 WG1:
   - **O1 / M-plane 語意(慢)**:`set_electrical_tilt`、`set_beam_width(az/el)`、`set_active_beam_set`(GoB 子集)、`set_beam_max_power`、`set_trx_mask`(64→32 節能)。先經 registry scene_run knob + RU config API 實作,之後可掛 O1 模擬端點。
   - **E2SM-RC / CCC 語意(快)**:`set_max_layers`、`mu_grouping`(第二階段)、`set_bcio(beam)`、CSI/SRS 回報週期。走現有 control 路徑(adapter → CU → RU/DU),記入 control audit。
3. 註冊到 RIC 閘道的 ranFunctions 不變,由 RC style 擴充。

### 4.5 管理平台 / 前端
- 天線預設編輯器改成 3.1 的欄位(面板圖示:M×N 元件、TRX 分組、埠數;自動算 EIRP 上限 = 功率 + 元件增益 + 10log10(元件數))。
- 場景層可對每 cell 選 preset、機械/電子下傾、GoB 子集;監控頁加「每 cell beam 使用熱圖」「每 UE RI/PMI/beam 時序」。

---

## 5. 分階段(每階段都可獨立驗證)

| 階段 | 內容 | 驗證 |
|---|---|---|
| A1 | preset 三層欄位 + virtualization + 參數化 Type I codebook(4–32 埠);Physics 回元件層 H | 8T8R (N1,N2)=(2,2) 單 UE:rank 2–4、每層 SINR、吞吐對比 4T;與 OAI 2/4 埠表逐位元一致 |
| A2 | RU 端 RI/PMI 選擇(取代固定 PMI);DU 用 RI 定層數 | 同一 UE 走動時 PMI 隨角度變、RI 隨 LOS/NLOS 變 |
| B1 | GoB 生成 + Cat B predefined-beam 路徑;beam_id 進 KPM | 32 beam GoB:UE 在不同方位選到的 beam 與幾何一致;beam RSRP top-k 合理 |
| B2 | 電子下傾與 active beam set 的 E2 控制;監控頁 beam 熱圖 | RIC 改 tilt / beam set → SINR 分布改變且可回滾 |
| C | cached 模式存 H(或主徑參數)→ cached 也有 MIMO/beam | corridor 三段 cache 重算後 rank/beam 與 live 一致 |
| D | MU-MIMO 配對(排程器)+ Type II codebook(可選) | 多 UE 滿載時 cell 吞吐 > SU-MIMO |

不做 / 保留簡化:類比/混合 beamforming(FR2)、Type II 子頻帶回報、真實 SRS 通道估計誤差(用理想 CSI + 可設誤差)。

---

## 6. 已知風險
- Sionna 陣列 scene-global:多 cell 不同 preset 需要多 engine 或以最大陣列建、用 W_virt 遮罩;先限制「同 run 同 preset」。
- 元件數上升(64T = 192 元件)ray tracing 成本線性上升;live 模式一次一個 run 的限制更嚴,cached 化(階段 C)更重要。
- OAI 對齊:OAI rfsim 預設 1×1;8 埠以上沒有 OAI 對照,只能對 3GPP 表與 MathWorks 參考實作對拍。

## 參考
- 3GPP TS 38.104 §4.3 / §7–§10(BS type 1-C/1-H/1-O/2-O、TAB、RIB、OTA)— https://itecspec.com/3gpp/38.104/s/7.1 、 https://www.tech-invite.com/3m38/toc/tinv-3gpp-38-104_a.html
- 3GPP TR 38.901 §7.3 Table 7.3-1(ETSI TR 138 901 V16.1.0)— https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/16.01.00_60/tr_138901v160100p.pdf
- 3GPP TS 38.214 §5.2.2.2(Type I/II codebook)— https://www.sharetechnote.com/html/5G/5G_CSI_RS_Codebook.html 、 https://www.mathworks.com/help/5g/ug/5g-nr-downlink-csi-reporting.html
- O-RAN WG4 CUS-plane(O-RAN.WG4.CUS.0-R004-v16.01)— https://specifications.o-ran.org/download?id=738 ;Cat A/B 與四種 beamforming:Polese et al., "Understanding O-RAN", arXiv:2202.01032 §IV;Avnet, Open RAN & mMIMO — https://my.avnet.com/silica/resources/article/open-ran-system-architecture-and-mmimo/
- O-RAN WG1 Use Cases Detailed Specification R005-v20.00(docs/MIMO)

---

## 附錄 A:docs/MIMO 兩份文件摘要(子代理整理,2026-09-16)

### A.1 AI_Powered_O-RAN_MIMO_Optimization.pdf
純圖片簡報(11 頁,WG1 使用案例的中文圖解),無硬體數字;唯一具體數字為「64T64R 關閉一半降為 32 通道」(WG1 §4.21 節能)。涵蓋:mMIMO beamforming / cell shaping(Non-RT RIC)、GoB、MU-MIMO 最佳化(Near-RT RIC:用戶選擇/分組、預編碼、通道預測)、MIMO 降階節能、干擾管理(E2 監測特定波束 → 調 MCS)。控制旋鈕表:

| 控制點 | 旋鈕 | 介面 | 時間尺度 |
|---|---|---|---|
| Non-RT RIC | 水平/垂直波束寬度、電子/數位傾角、波束方位、每波束最大功率、GoB | O1 | 秒–分 |
| Near-RT RIC | 用戶選擇/分組、通道預測、預編碼係數、MCS | E2 | 10–100 ms |
| 節能 xApp | 射頻通道開關(64→32)、層數、MU 排程用戶數 | E2 → OFH M-plane | 秒–分 |

KPI:每波束 RSRP/RSRQ/CQI/SINR、波束功率與 PRB、波束換手失敗、NI;環境資料含站址、站間距、頻率、MIMO 可調範圍;應用層 UE GPS。閉環:採集 → 推論 → 配置 → 監控,異常 fallback。

### A.2 O-RAN.WG1.TS.Use-Cases-Detailed-Specification-R005-v20.00
- **§4.6.3.1 Non-RT GoB beamforming optimization**:O1 控制(TS 28.541)水平/垂直波束寬度、方位、downtilt、每波束最大/平均功率、Beam Pattern Configuration Table、預設 beam weight;資料需求 §4.6.4.1(每波束 RSRP/RSRQ/CQI/SINR、cell 負載、RRC 連線數、吞吐/頻譜效率、NI、每波束功率與 PRB、beam HO/failure 統計、UE GPS)。
- **§4.6.3.2 Near-RT beam-based MRO(bMRO)**:E2 回報每波束 HO KPM(too early/late/attempted/successful/failed,TS 28.552/28.622,粒度 1 s 倍數),控制 bCIO 等 L3 波束移動性參數;GoB pattern 資訊經 O1。
- **§4.6.3.3 NR Cell Shaping**:rApp → Non-RT RIC → SMO → O-DU(O1)→ O-RU(OFH M-plane);需求 Req-4.6.001~022:天線經緯度/方位/高度(TS 28.662 §4.3.2)、每天線 RET(retTiltValue;WG4.MP §14.4.2/14.4.3 + AISG)、每天線/每載波數位傾角、水平/垂直覆蓋寬度、O-RU 支援的覆蓋組合能力。
- **§4.22 MU-MIMO optimization**:全程 E2;xApp 下發 DL CSI 回報配置、UL SRS/DMRS 配置、UE 分組 + 資源指派 + MCS + 預編碼係數;資料需求 §4.22.4(cell 配置、UE 清單與狀態、SRS/ACK-NACK、CQI/RI/PMI、buffer/BSR)。
- **§4.21.3.2 RF channel reconfiguration**:64 通道關 32、減層數/MU 用戶數;鏈路 rApp(A1)→ xApp(E2SM-CCC §8.8.2.6)→ O-DU → O-RU(antenna mask / TRx Control,WG4.MP §20.3.1.2);量測 O1PMeas A.4.13.14~16、TS 28.552 §5.1.1.30/§5.1.1.31.2、E2SM-KPM §7.10.10.4/5、O-RU 能耗。
- §4.14 mMIMO SU/MU grouping 在 v20.00 已 Void。
