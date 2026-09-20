# 06 — O-RAN WG4 CUS-Plane（O-RAN.WG4.TS.CUS.0-R005-v21.00）天線 / Beamforming / MIMO 規則抽取

- 來源文字檔：`docs/MIMO/specs/txt/O-RAN.WG4.TS.CUS.0-R005-v21.00.txt`
- 表格與公式：以 python zipfile 解開 `docs/MIMO/specs/oran/O-RAN.WG4.TS.CUS.0-R005-v21.00.docx` 的 `word/document.xml` 取得（含 OMML 公式，例如 §12.5.4 的 f(m,n,p,q)）
- 文件沒有頁碼，出處一律寫成「章節號 + 表號/圖號」。表號照 docx 原樣（部分表號在 docx 內沒有連字號，例如「Table 7.3.11」即 Table 7.3.1-1）
- 「原文」欄是逐字引用（英文）；「說明」欄是中文整理。對應到 3GPP 或 M-plane YANG 的內容，如果 CUS 原文沒有明寫，會標「（推論）」
- M-plane YANG 條目編號（ORAN-xxx）沿用 `05_oran.md`

---

## A. 文件架構：Split 7-2x、Category A/B、eAxC

### [CUS-001] Split 7-2x 與 Category A / B O-RU 定義
- 出處：O-RAN.WG4.TS.CUS.0-R005-v21.00 §3.1（Terms）、§4.2.1、Figure 4.2.1-1
- 原文：
  > category A O-RU: O-RU within which the DL precoding is not done
  > category B O-RU: O-RU within which the DL precoding is performed
  > O-RAN has selected a single split point, known as "7-2x" but allows a variation, with the precoding function to be located either "above" the interface in the O-DU or "below" the interface in the O-RU. ... O-RUs within which the precoding is not done (therefore of lower complexity) are called "Category A" O-RUs while O-RUs within which the precoding is done are called "Category B" O-RUs.
  > In particular, for a Category A O-RU, the precoding shall be executed in the O-DU and any beamforming in the O-RU, if present, would exclude the precoding calculation. For LTE precoding schemes other than Transmit Diversity and Spatial Multiplexing with Large Delay CDD and precoding schemes for NR, the precoding may be included in a frequency-domain beamforming processing block within the O-RU for a Category B O-RU (even for time-domain beamforming O-RUs).
- 型別/值域：分類（CAT-A / CAT-B）
- 說明：7-2x 的切點在 O-DU 與 O-RU 之間，差別只在「precoding 放在哪一側」。CAT-A 的 precoding 由 O-DU 做，O-RU 只做 beamforming；CAT-B 可以在 O-RU 內做 precoding，NR 的做法是把 precoding 併進頻域 BF 權重裡。對應 38.211 §6.3.1.5 / §7.3.1.5 的 precoding（layer → antenna port）。M-plane 對應 `ru-supported-category`（ORAN-M01）。

### [CUS-002] 7-2x DL/UL 功能分工，以及 CAT-A O-DU 的 precoded stream 數
- 出處：§4.2.2.1（Figure 4.2.2.1-1～4）、§4.2.3.1（Figure 4.2.3.1-1）
- 原文：
  > When O-DU supports Category A O-RU, O-DU shall support a total number of precoded streams of up to 8. O-DU supporting Category A O-RU may support more than 8 precoded streams.
  > In the DL, OFDM phase compensation (clause 5.4 of [4]), iFFT, CP addition, and digital beamforming functions reside in the O-RU for Category A and Category B O-RUs. In addition, precoding with schemes other than Transmit Diversity and Spatial Multiplexing with Large Delay CDD reside in the Category B ORU. ... The PHY functions including resource element mapping, precoding, layer mapping, modulation, scrambling, rate matching and coding not handled by O-RU reside in the O-DU.
  > In the UL, OFDM phase compensation ..., FFT, CP removal and beamforming functions reside in the O-RU. ... The rest of the PHY functions including resource element de-mapping, equalization, de-modulation, de-scrambling, rate de-matching and de-coding reside in the O-DU.
  > 7-2x interface scales based on "streams", which allows using high number of antennas without higher transport bandwidth.（§4.2.2.2）
- 型別/值域：**上限規則**：支援 CAT-A 的 O-DU 必須支援最多 8 個 precoded streams（可以超過 8）
- 說明：O-RU 負責 iFFT/FFT、CP 與 BF（數位 BF 一定在 O-RU）。fronthaul 的頻寬隨 stream（layer）數增減，不隨天線數增減。對應 38.211 §5.4（OFDM phase compensation）。

### [CUS-003] eAxC_ID 組成（DU_Port_ID / BandSector_ID / CC_ID / RU_Port_ID）
- 出處：§5.1.3.2.7（ecpriRtcid / ecpriPcid）、Table 5.1.3.2.7-2；§3.1「extended Antenna-Carrier (eAxC)」
- 原文：
  > extended Antenna-Carrier (eAxC): a data flow for a single antenna (or spatial stream) for a single carrier in a single sector
  > eAxC_ID subfields: One eAxC identifier (eAxC_ID) comprises a band and sector identifier (BandSector_ID), a component-carrier identifier (CC_ID), a spatial stream identifier (RU_Port_ID) and a Distributed Unit identifier (DU_Port_ID).
  > DU_Port_ID: Used to differentiate processing units at O-DU (e.g. different baseband cards). ...
  > BandSector_ID: Aggregated cell identifier (distinguishes bands and sectors supported by the O-RU).
  > CC_ID: distinguishes Component Carrier supported by the O-RU.
  > RU_Port_ID: designates logical flows such as data layers or spatial streams, and logical flows such as separate numerologies (e.g. PRACH) or signalling channels requiring special antenna assignments such as SRS.
  > The bitwidth of each of the above fields is variable and set via M-Plane messaging. ... the SMO that does the actual assignment will assure all 16 bits are allocated (with or without padding).
  > The eAxC_ID value assigned to an O-RU's endpoint ... shall be unique among all endpoints of O-RU of the same direction (Tx or Rx).
- 位寬/型別/值域：16 bits，型別為 unsigned integer（concatenated bit fields），值域 0x0000–0xFFFF。位元順序從 MSB 起依序為 DU_Port_ID | BandSector_ID | CC_ID | RU_Port_ID（Table 5.1.3.2.7-2），各子欄位的位寬由 M-plane 設定
- 說明：eAxC 是 CPRI「AxC」的延伸。同一方向的 eAxC_ID 在一台 O-RU 內不能重複。對應 M-plane `e-axcid`（`o-du-port-bitmask`、`band-sector-bitmask`、`ccid-bitmask`、`ru-port-bitmask`，見 ORAN-030）。

### [CUS-004] RU_Port 與 layer / spatial stream / antenna 的關係
- 出處：§5.1.3.2.7；§3.1「spatial stream」「TRX」
- 原文：
  > In the present document, one eAxC contains only one spatial stream (i.e. one beam per subcarrier) at a time. When precoding in the O-RU, then each eAxC contains one layer at a time, except for TxD (LTE TM2) when a single eAxC (single ecpriRtcid and ecpriPcid) represents all TxD layers.
  > spatial stream: data flow on the DL associated with precoded data (may be same as layers or different if there is expansion in the precoding), and on UL associated with the number of outputs from the beamforming (sometimes called "beams")
  > TRX: refers to the specific processing chain in an O-RU associated with D/A or A/D converters
  > NOTE: Due to digital beamforming the number of TRXs may exceed the number of spatial streams, and due to analog beamforming, the number of TRXs may be lower than the number of antenna elements.
- 說明：
  - **CAT-A**：一個 eAxC 對應一個 precoded spatial stream，約等於 38.211 的一個 antenna port（例如 PDSCH DMRS port 1000+）。
  - **CAT-B**：一個 eAxC 對應一個 layer（38.211 的 layer），LTE TxD 例外。
  - 數量關係：天線元件數 K ≥ TRX 數（類比 BF 時）；TRX 數 ≥ stream 數（數位 BF 時）。
  - M-plane 對應：`number-of-spatial-streams`、`number-of-ru-ports-ul/dl`（ORAN-M03～M05）。

### [CUS-005] O-RU 輻射結構層級（O-RU → panel → tx/rx-array → array element → radiator）
- 出處：§12.2、Figure 12.2-76
- 原文（節錄）：
  > O-RU: each O-RU can have 1 or several panels
  > panel: each panel can have 1 or several tx-array and/or rx-array
  > Multiple eAxC_ID values may be assigned to a single tx-array or rx-array
  > An eAxC_ID value for a given direction (DL or UL) shall not be assigned to more than one tx-array or rx-array
  > Each tx-array and rx-array has only one polarization for Category A O-RUs.
  > Each tx-array and rx-array may include both polarizations for Category B O-RUs.
  > Category B O-RU shall provide one or more single-polarization rx-arrays for each polarization.
  > Rx-arrays with endpoints supporting DMRS-BF shall include all polarizations supported by the O‑RU ...
  > Amplitude and phase of each array element inside one tx-array and rx-array can be controlled via the weights pointed to by the beamIds which are received via the terminated RU_port_ID(s).
  > array element: each array element can have 1 or several radiators (where amplitude and phase relation between the radiators cannot be changed dynamically during real-time)
- 說明：一個 eAxC 只能屬於一個 array。**CAT-A 的每個 array 只能是單極化**，CAT-B 可以是雙極化。array element 約等於 38.901 的一個 sub-array（多個 radiator 固定組合，對應 38.901 §7.3 的 M×N×P 元件，以及 K 個 element 的 sub-array 模型）（推論）。M-plane 對應 `tx-arrays` / `rx-arrays`（ORAN-010～024）。

### [CUS-006] Calibration（校正）
- 出處：§12.3
- 原文：
  > Calibration is the functionality of eliminating or minimizing relative amplitude and phase differences over frequency domain or time delay over the time domain between the array elements belonging to same tx-array or rx-array (including effect of front-end analog filters).
  > Calibration can also be applied between two or many tx-arrays or rx-arrays if those tx-arrays or rx-arrays belong to the same calibration group which is part of the O-RU capabilities.
- 說明：同一個 array 內的元件一起校正；跨 array 校正需要屬於同一個 calibration group。Table 10.2.4-1 把「Antenna calibration support」列為 Optional。

---

## B. Beamforming 方法

### [CUS-010] 五種 beamforming 方法總覽與 beamId 的使用
- 出處：§12.4.1；Annex J（J.1～J.5）
- 原文（節錄）：
  > There are two main domains in which beamforming is executed, frequency-domain and time-domain; it is also possible to combine both (called "hybrid beamforming").
  > a) Predefined-beam beamforming: In this case, an index called "beamId" indicates the specific beam pre-defined in the O-RU to use. ...
  > b) Weight-based dynamic beamforming (based on real-time-updated weights): Here the O-DU is meant to generate weights that create the beam, so the O-DU needs to know the specific antenna characteristics of the O-RU ...
  > c) Attribute-based dynamic beamforming (based on real-time-updated beam attributes): ... that beamId is associated with certain beam attributes as described in clause 7.7.2. ... When the attribute-based beamforming method is used for at least one layer (or spatial stream), then O-DU shall use same beamforming method for all layers (or spatial streams) of the specific time-frequency resource element(s).
  > d) Channel-information-based beamforming: In this case the O-DU provides channel information per ueId periodically (generally less often than every slot) and then on a slot-by-slot basis the O-DU provides scheduling information which the O-RU uses along with the channel information to calculate the proper beamforming weights ... Here there is no beamId value associated with the beamforming, instead the ueId is associated with each data section. ... The multiple beamId tables feature is not applicable for channel-information-based beamforming.
  > e) DMRS-based beamforming: In this case the O-DU provides a description of the DMRS configuration for PUSCH, and the O-RU uses that description to perform channel estimation and compute beamforming weights with or without an equalization function ... Because there is no use of beamId in this method ...
- 說明：PDBF、WDBF、ABBF 三種方法用 beamId；CIBF 與 DMRS-BF 不用 beamId，改用 ueId。ABBF 與 CIBF 規定：同一個 RE 上的所有 layer 必須使用同一種 BF 方法。
  - 另外，Annex J.1 原文寫 "The present document has four distinct methods supported at the O-RU"，只列 J.2～J.5 四種；DMRS-BF 另見 §12.6。這是文件內的不一致，此處照原文記錄。
- 對應關係：
  - PDBF 約等於 38.214 codebook / SSB、CSI-RS beam sweep 的 GoB（推論）。
  - CIBF 與 DMRS-BF 約等於 reciprocity-based（SRS / DMRS）的 MU-MIMO（推論）。

### [CUS-011] Beamforming 功能的 O-DU / O-RU 支援要求
- 出處：§10.2.4、Table 10.2.4-1
- 原文（逐列）：
  > Predefined-beam beamforming (PDBF) | Mandatory | Conditional Mandatory | Condition applies to UE-specific BF for any O-RU capable of BF; a non-BF O-RU shall be supplied a zero beamId if a C-Plane message containing a beamId is sent at all.
  > Weight-based dynamic beamforming (WDBF) | Conditional Mandatory | Conditional Mandatory | Condition for O-DU: Mandatory only for O-DUs designed to support any kind of BF that involves the operation of updating BF weights in real-time, these kinds include CIBF and DMRS-BF Condition for O-RU: mandatory for any O-RU internally calculating BF weights, these kinds include CIBF and DMRS-BF.
  > Attribute-based dynamic beamforming (ABBF) | Optional | Optional | This is considered to not internally use BF weights.
  > Channel-information-based beamforming (CIBF) | Optional | Optional | This is considered to internally use BF weights.
  > Multiple beamId tables | Optional | Optional | See clause 7.5.3.9 and 12.4.1
  > DMRS-based BF (DMRS-BF) | Optional | Optional |
  > DMRS-based BF with equalization (DMRS-BF-EQ) | Conditional Mandatory | Optional | Condition for O-DU: If DMRS-BF is supported
  > DMRS-based BF without equalization (DMRS-BF-NEQ) | Conditional Mandatory | Optional | ...
  > NULL-STEERING | Optional | Optional | See clause 12.4.2.3
  > BEAM-ID-SCOPE-NULLING / TARGET-BEAM-RANGE | Optional | Optional | See clause 12.4.2.3
  > （另有 Predefined beam tilt、Antenna calibration、SE14、SE17 等列，均為 Optional/Optional）
- 說明：O-DU 必須支援 PDBF。非 BF 的 O-RU 收到的 beamId 必須是 0。只要 O-RU 內部會算 BF 權重（CIBF、DMRS-BF），就必須支援 WDBF。

### [CUS-012] Predefined-beam beamforming（PDBF）
- 出處：§12.4.2.1、§12.4.2.2、Figure 12.4.2.2-77/-78
- 原文：
  > When implementing predefined-beam beamforming, the O-RU shall convey to the O-DU whether the beamforming type is frequency-domain, time-domain, or a mixture of the two ("hybrid beamforming"). ... The beamId points to a single combined frequency-domain and time-domain weight vector.
  > NOTE: There is no requirement that beamIds be in sequential order or that there are no gaps between beamId values.
  > The beamId value of zero is reserved for no beamforming, so shall not be used for any other frequency-domain, time-domain or hybrid beam.
  > 1) beam-type for the subject beamId enumerated as COARSE-BEAM or FINE-BEAM; ... 2) beam-group-id for the subject beamId as an integer; 3) coarse-fine-beam-relation as a list ...; 4) neighbor-beam as a list: a list of all beams that may interfere with the subject beamId
  > Overlapping beams shall not be scheduled together to avoid interference, and neighbouring beams should not be scheduled together to avoid interference where possible.
  > A "beam-group" is the set of beamIds that may be used simultaneously ... different time-domain groups shall be separated in time.
  > If the O-RU controller configures the elevation-tilt-offset-angle as "+A" degrees and azimuth-tilt-offset-angle as "+B" degrees, then the O-RU shall regenerate the beams to change its steering angles to be elevation angle value: "theta + A", azimuth angle value: "phi + B".
  > The elevation-tilt-offset-angle values smaller than 0 represents an up-shift of the default service area towards the zenith (i.e. corresponding to a decrease in zenith angle) ...
- 說明：
  - O-RU 在開機時透過 M-plane 回報每個 beamId 的 beam-type、beam-group-id、coarse/fine 關係與鄰居 beam。
  - 排程規則：重疊的 beam 不得同時排程（shall）；相鄰的 beam 盡量不要同時排程（should）。
  - M-plane 對應：ORAN-B11～B15（beam-type、beam-group-id、coarse-fine、neighbour-beams）；tilt 對應 ORAN-B20～B22。
  - 3GPP 對應：tilt 約等於 38.901 的 β（downtilt）（推論）。

### [CUS-013] Null steering（PDBF 的方向性抑制）
- 出處：§12.4.2.3、Figure 12.4.2.3-1
- 原文（節錄）：
  > Null steering is a directional interference mitigation feature, which is applicable for downlink transmission with predefined beams. ... Support for null steering is declared by the O-RU via YANG feature NULL-STEERING.
  > A null point is a null at a given zenith and azimuth angle, which shall result when O-DU configures both M-Plane parameters azimuth-angle and zenith-angle. An elevation null stripe is null at a given zenith angle for all azimuth angles, which shall result when O-DU configures zenith-angle but not azimuth-angle.
  > The null-width is a unitless positive integer, which defaults to 1 ... If max-total-null-width or max-total-null-stripe-width is not declared, the O-DU shall assume that the corresponding type of null is not supported.
  > There are two null steering control methods: NULL-PER-ARRAY and NULL-PER-ARRAY-CARRIER.
  > Null steering configuration/re-configuration requires deactivation and activation of tx-array-carrier(s).
- 說明：M-plane 參數包括 `null-steering-control-method-supported`、`null-control-method`、`azimuth-angle`、`zenith-angle`、`null-width`、`null-freq`、`max-total-null-width`、`max-total-null-stripe-width`、`max-total-null-and-null-stripe-width`、`beam-id-range`、`target-first-beam-id`、`spare-beam-id-range`。細節見 MP §15.4.7。這些參數在 05_oran.md 的本地 YANG（2022-12-05 版）中未收錄（未查證）。

### [CUS-014] Weight-based dynamic beamforming（WDBF）的權重更新規則
- 出處：§12.4.3.1
- 原文：
  > Weight-based dynamic beamforming operates the same as predefined-beam beamforming, except that the O-DU shall convey beamforming weights to the O-RU. ... these are consistent with the principle that weights associated with a beamId when applied to applicable symbols in a slot shall be the same:
  > 1) If beamforming weights are to be updated for a slot, then the O-DU shall provide the new weights for the first occurrence of the given beamId in the slot.
  > 2) Weight updates (sending the same weights for a beamId is not considered a "weight update") shall not be provided more than once for a beamId in the slot. Where new beamforming weights are required in a single slot, a new beamId value shall be employed instead.
  > 3) For PRACH a "slot duration" as considered here is considered to be a PRACH sequence duration (see Figure 7.2.3.4-46).
- 說明：同一個 slot 內，一個 beamId 的權重最多只能更新一次；如果需要不同權重，就要換一個 beamId。

### [CUS-015] WDBF：beam-update-contention-control 與 beam-context-gap-period
- 出處：§12.4.3.2、Figure 12.4.3.2-79/-80
- 原文（節錄）：
  > for messages having the same startSymbolId within the same "context" (meaning with same numerology and array-carrier and direction (UL/DL)) within a slot, if beamforming weights are sent associated with a beamId in one C-Plane message, then any invocation of that same beamId in a subsequent C-Plane message having the same startSymbolId within the same slot shall also include the set of beamforming weights. ... this restriction applies only to Section Types 1 and 3.
  > for high-priority data sections with a repetition bit, only the data section with repetition bit = 0 shall contain the set of beamforming weights
  > O-RU shall report the M-Plane O-RU capability "beam-update-contention-control-limits-required" ... The O-DU may enable or disable this feature at an endpoint granularity using Boolean flag "beam-update-contention-control-enabled"; if set to FALSE (default) the above restriction shall not apply ... the O-RU shall report "max-beams-per-symbol-with-beam-contention-control" and "max-beam-updates-per-symbol-with-beam-contention" ... the O-DU shall ensure all endpoints have the same "beam-update-contention-control-enabled" value
  > the O-RU shall provide the beam-context-gap-period in microseconds as a 16-bit number, with the special value 0xFFFF meaning "infinite". Infinite means that for that O-RU, a beamId may not be reused at all in a different context (applicable only to weight-based dynamic beamforming). ... the beam-context-gap-period shall be set by the O-RU to be the same value across the entire O-RU.
- 位寬/值域：beam-context-gap-period 為 16 bit，單位 µs；0xFFFF 表示 infinite；0 表示接收窗完全對齊
- 說明：這一節是 05_oran.md ORAN-034 所說的「Weight-based dynamic beamforming」章節，也就是 ORAN-062（beam-update-contention-control-limits）的出處。「context」指 DL/UL、SCS 或 array-carrier 不同的訊息流。

### [CUS-016] WDBF：純頻域或純時域 BF 的 M-plane 自我描述
- 出處：§12.4.3.3
- 原文：
  > the beamId is treated the same: it points to a set of weights that control the array elements' gain and phase and the number of weights equals the number of array elements. ... The weight values prior to any compression will be fractional hence no I or Q value may exceed positive or negative unity.
  > 1) Beamforming type, possible choices are "frequency", "time" or "hybrid" ... 2) Maximum number of weight-based beamId values supported (could be zero): "numBeams" ... zero means no weight-based beamforming is supported by this tx-array or rx-array 3) Initial value of weight-based beamId supported: "initBeamId" ... 4) Frequency granularity of time-domain beamforming, enumerated as "per component carrier" or "per band" ... 5) Time granularity of time-domain beamforming, enumerated as "per-OFDM-symbol" or "per-slot"
  > The actual number of weights K in the frequency-domain or time-domain weight vectors will be clear from the O-RU antenna model
- 型別/值域：權重為複數，|I|、|Q| ≤ 1（壓縮前）；權重個數 = K（array element 數）
- 說明：beamId 的範圍劃分為 [initBeamId, initBeamId+numBeams−1]，不同範圍可分給 WDBF 或 PDBF；CUS 原文只寫 "Different ranges of beamId may support weight-based beamforming versus e.g. predefined beamforming"，區間公式是推論。M-plane 對應：ORAN-B05（beamforming-type）、B06（max-number-of-beam-ids / initial-beam-id）、B07（frequency-/time-granularity）。

### [CUS-017] WDBF hybrid：可更新的 FD + TD 權重（K、K'、p'）
- 出處：§12.4.3.4.2、Figure 12.4.3.4.2-81
- 原文：
  > The number of time-domain beamforming weights associated with a given beamId is the same as the number of array elements which is K, but the number of frequency-domain weights is less, being K'. p' represents the dimensionality of the time-domain beamforming operation, so that K = K' * p'. The total length of the beamforming weight vector, including both the K' frequency-domain weights and the K time-domain weights, is K' + K = K' + (K' * p') = K' * (p'+1). Figure 12.4.3.4.2-81 shows an example where K = 16, K' = 4 and p' = 4, and the length of the beamforming weight vector (frequency-domain and time-domain combined) is 20 complex weights.
  > Where a block-based beamforming weight compression is employed ..., the block size is a single beamforming weight vector (both frequency-domain and time-domain parts).
- 公式：K = K'·p'；權重向量長度 = K'·(p'+1)
- 說明：這是 05_oran.md 第 5 項「§12.4.3.4.2 參數 p'」的出處，對應 M-plane `p-dash`（ORAN-B10）。

### [CUS-018] WDBF hybrid：可更新的 FD 權重 + 固定的 TD beam
- 出處：§12.4.3.4.3、Figure 12.4.3.4.3-82
- 原文：
  > the beamforming weight vector is a composite of the frequency-domain weights and the time-domain beam numbers with the frequency-domain weights in the first half of the vector and the time-domain beam numbers in the second half of the vector. ... the frequency-domain weights may be compressed but the time-domain beam numbers shall not be compressed.
  > 6) For each of the time-domain beams (the number is known from the O-RU antenna model), beam attributes (see 12.4.2.2)
  > The number of time-domain beam numbers associated with a given beamId (K') will be the same as the number of frequency-domain beamforming weights for that beamId
- 說明：向量前 K' 個是 FD 複數權重（可以壓縮），後 K' 個是 TD beam 編號（整數，不壓縮）。

### [CUS-019] Hybrid BF 使用 Section Type 4 TIME_DOMAIN_BEAM_CONFIG
- 出處：§12.4.3.4.4、Figure 12.4.3.4.4-83/-2/-3；§7.2.9.2.1；§7.4.6 Table 7.4.6-3/-4/-5；§7.5.3.43/44/46/56
- 原文：
  > When the O-DU configures the O-RU using the M-Plane parameter 'st4-for-time-domain-beamforming-weights-enabled', to use Section Type 4 to specify time-domain beamforming information ..., all other extensions i.e. SE 1, 3, 10, 11 used for specifying beamforming information shall contain frequency-domain beamforming information only. Also as defined in M-Plane, hybrid beamId space, time-domain beam-id space, and frequency domain beamId space are independently defined in M-Plane.
  > Each time-domain beam number 'tdBeamNum' vector is identified by a 'tdBeamGrp'. ... The total number of time-domain beam numbers per 'tdBeamGrp' shall be equal to the number of frequency-domain weights K'.
  > Size of each time-domain beamforming vector is the number of antenna elements per frequency-domain beamforming port which is equal to p'. Value of p' shall be advertised by the O-RU as an M-Plane parameter 'p_dash'.
  > NOTE: K'= K is a special case when p'=1.
  > Because the values of beamforming weights never expire, the value of numSlots should be set to zero for this command type ... only cmdScope "ARRAY-COMMAND" is valid for this ST 4 command.（§7.2.9.2.1）
- 位寬/值域：
  - st4CmdType = 1
  - disableTDBFNs：1 bit（1 = 只帶 tdBeamGrp）
  - tdBeamGrp：15 bit（0–0x7FFF），識別長度為 K' 的 tdBeamNum 向量
  - disableTDBFWs：1 bit（1 = 只帶 tdBeamNum，不帶權重）
  - tdBeamNum：15 bit，每個對應一組 K/K' 個權重
  - TD 權重的壓縮使用 bfwCompHdr / bfwCompParam / bfWI / bfWQ（格式同 SE1），可以與 FD 權重使用不同的壓縮方式
- 說明：這是 05_oran.md 第 6 項（§12.4.3.4.4）的出處，對應 ORAN-004。

### [CUS-020] Attribute-based dynamic beamforming（ABBF）
- 出處：§12.4.4；Annex J.4
- 原文：
  > Attribute-based dynamic beamforming operates similarly to weight-based dynamic beamforming except that it is inherently a time-domain beamforming operation ... beam attributes associated with a specific beamId are sent instead from the O-DU to the O-RU in Section Extension 2.
  > 1) Beamforming type ... here will be "time". 2) Maximum number of beamId values supported (could be zero): "numBeams" 3) Initial value of beamId supported: "initBeamId" 4) Valid range of bfAzPt ... 5) Valid range of bfZePt ... 6) Valid range of bfAz3dd ... 7) Valid range of bfZe3dd ... 8) Valid range of bfAzSl ... 9) Valid range of bfZeSl
  > Some potential schemes are: beamforming phased array weights (analogue or digital), holographic beamforming, Butler matrices, lenses, and other known and emerging techniques.（J.4）
- 說明：ABBF 本質上是時域 BF。O-RU 需要回報六個屬性各自的有效範圍。M-plane 對應 `beamforming-trough-attributes-supported`（ORAN-B16）。至於六個屬性有效範圍對應的 YANG leaf，本地 YANG 未找到。

### [CUS-021] Channel-information-based beamforming（CIBF）
- 出處：§7.2.7；§12.4.5；Annex J.5
- 原文：
  > In the channel information based beamforming method, the O-DU shall provide channel information per ueId periodically (generally less often than every slot) using Section Type 6 C-Plane message(s) and then on a slot-by-slot basis the O-DU shall provide scheduling information using Section Type 5 C-Plane message which the O-RU shall use along with the channel information to calculate the proper beamforming weights for the specific slot with its co-scheduled UEs. To reduce peak bandwidth, the transmission/ reception window constraints shall not apply to a Section Type 6 message. The O-RU is expected to use the latest possible available channel information for a ueId ... available to the O-RU at the end of receive window of a Section Type 5 message.
  > As stated in clause 12.4.1, beamId is irrelevant and unused in the case of channel-information-based beamforming.（§12.4.5）
- 說明：ST6 傳送 H（週期性，不受收發窗限制）；ST5 傳送每個 slot 的 ueId 排程；權重由 O-RU 計算。對應 38.214 的 non-codebook / TDD reciprocity（SRS 通道估計）（推論）。M-plane 對應 `beamforming-trough-ue-channel-info-supported`（ORAN-B16）、`ue-specific-beamforming`（ORAN-B17）。

### [CUS-022] CIBF 權重計算公式（informative）
- 出處：Annex J.5
- 原文（公式以 docx 文字還原）：
  > For UL: ... a beamforming matrix W = [w1,...,wK] ∈ C^(L×K) is applied to the frequency domain IQ data of RE xi for L streams, K is the number of array elements ... H ≜ [h1,…,hL] ∈ C^(K×L) is defined as the UL channel estimates of RE x for the L streams, and hi is the channel matrix conveyed via the Section Type 6 message and is identified via ueId. When the C-Plane Section Extension = 16 is used, the UL channel for each stream is fetched according to the 'ueId' and the 'antMask' fields.
  > MRC: W = H^H/‖H‖ ; Zero-forcing: W = (H^H H)^-1 H^H ; Regularized zero-forcing/ MMSE: W = (H^H H + ξL)^-1 H^H, where ξL is a diagonal matrix with diagonal elements corresponding to regularization factors of each stream.
  > For DL: ... W = [w1, ..., wL] ∈ C^(K×L) ... Heff ≜ [heff,1^T,…,heff,L^T]^T ∈ C^(L×K) ... heff,i ∈ C^(1×K) is the channel matrix conveyed via the Section Type 6 message and is identified via ueId.
  > Zero-forcing: W = (1/Ψ) Heff^H (Heff Heff^H)^-1 ; Regularized zero-forcing/ MMSE: W = (1/Ψ) Heff^H (Heff Heff^H + ξL)^-1, ... the normalization parameter Ψ can be chosen to satisfy the total power constraint {W W^H} ≤ M.
  > Assuming Y users' channel matrices each transmitting multiple layers' data considering transmit antenna switching (TAS), ... Heff,Si = f(Hi) ∈ C^(Si×K) and Si ≤ Ni.
- 說明：
  - H 的維度：UL 為 K×L，DL 為每個 layer 一列 1×K，其中 K 是 array element 數。
  - ξ 由 SE8 regularizationFactor 下發。
  - 公式屬 informative，實際演算法由 O-RU 自選。
  - 原文的上下標在 docx 轉文字時已遺失，此處依數學結構還原（推論）。
  - 對應 38.214 MU-MIMO precoding（實作層）。

### [CUS-023] Weight-based dynamic BF 的數學模型（informative）
- 出處：Annex J.3
- 原文：
  > X = [x0 x1 …xP-1] represents the frequency domain IQ data in one data section, where P is the number of REs in the data section and xI is an RE, xi∈ C^(L×1), L is the number of streams. W = [w0 w1 …wP-1] represents the beamforming weights associated with the tx-array, where wI is a beamforming weight of RE xI, wI ∈ C^(K×L), K is the number of array elements. ... yi = wi xi ... yi ∈ C^(K×1).
  > Hybrid ... wI ∈ C^(K×K') ... wi' ∈ C^(K'×L) ... yi = wi wi' xi
- 說明：頻域 BF 以 section（或 PRB bundle）為單位；時域 BF 以整個 OFDM symbol 為單位；hybrid 則是兩者的乘積。對應 38.901 §7.3 的 array 輸出模型（推論）。

### [CUS-024] DMRS-based beamforming（DMRS-BF-EQ / DMRS-BF-NEQ）
- 出處：§7.2.10；§12.4.6；§12.6.1.1、Figure 12.6.1.1-1；§12.6.1.3.1.2
- 原文（節錄）：
  > DMRS based beamforming (DMRS-BF) is a beamforming method wherein the O-RU computes UE channel estimates based on the received UE UL DMRS symbols, then computes "weights" based on those channel estimates and applies the weights to the UE UL data. This beamforming method is applicable only to the NR PUSCH. There are two types of DMRS-BF: DMRS-BF-NEQ ... and DMRS-BF-EQ where the "weights" are beamforming weights that include an equalization function.
  > The DMRS-BF method, like WDBF and CIBF, is of value in Massive MIMO configurations, typically supported in CAT-B O-RUs.
  > 5) ... only one of the two beamforming methods may be used at a time in the whole O-RU
  > 8) For each slot, the O-DU shall issue C-Plane messages using ST 5 describing the scheduling decisions for each user group, which may use SE 10 ..., shall use SE 24 ..., may use SE 25 ... and may use SE 26 ...
  > The order of Section Extensions in the context of DMRS-BF shall be first SE 10, then SE 24, then SE 25, SE 26, SE 27 and SE 32 in any order.（§12.6.1.3.1.2）
  > When used in the context of DMRS-BF, the 15 bits in ueId are partitioned such that some number of least-significant bits enumerate layers per UE, and the remaining most-significant bits enumerate UEs. ... ueId = 0x7FFF is reserved ...
  > EXAMPLE: The O-RU may declare that the maximum number of bits assigned for indicating UE layers is 4. ... no UE may have more than 2^4 or 16 data layers, and there can be no more than 2^(15-4)-1 or 2047 UEs processed by the O-RU at a time
- 說明：
  - DMRS-BF 只適用於 NR PUSCH。EQ 與 NEQ 在整台 O-RU 內只能擇一。
  - user group 的定義（§3.1）：SU-MIMO 或 MU-MIMO 下使用相同 PRB/symbol 的一組 layer。
  - 其他 SE 與 ST 的角色：SINR 由 ST9 回報；RRM 量測由 ST10/ST11 處理；SE27 負責維度縮減；SE32 請求 rank/TPMI 量測。
  - 對應 38.211 §6.4.1.1（PUSCH DMRS）。
  - M-plane 參數：`ueid-max-layer-bits`、`ueid-layer-bits-configured`、`max-num-ues-supported`、`max-num-ueids`、`user-group-mode`、`supported-sinr-resolutions` 等；本地 YANG（2022-12 版）中未查證。

### [CUS-025] O-RU 內 beamId 的 selective transmission（Shared cell）
- 出處：§13.3.1
- 原文：
  > For the selective transmission and reception function using beamId: Predefined-beam beamforming is assumed. ... Use of the multiple beamId tables feature together with selective transmission is not permitted. The concept is to utilize the multiple O-RUs involved in a Shared Cell collectively as a single beamforming O-RU
- 說明：Shared cell 可以把多台 O-RU 視為一台 PDBF O-RU，用 beamId 選擇要由哪台發射或接收。

---

## C. Section Types

### [CUS-030] Section Type 總表
- 出處：§7.3.1、Table 7.3.1-1
- 原文：
  > 0 | Unused Resource Blocks or symbols in Downlink or Uplink | ...
  > 1 | Most DL/UL radio channels (NOTE) | Here "most" refers to channels not requiring time or frequency offsets such as are needed for mixed-numerology channels
  > 2 | Reserved for future use
  > 3 | PRACH and mixed-numerology channels (NOTE) | Channels requiring time or frequency offsets or different-than-nominal SCS values
  > 4 | Slot Configuration Control | Slot configuration for multiple eAxC_IDs with one or multiple Section Type 4 configuration commands
  > 5 | UE scheduling information (ueId assignment to section) | Provides scheduling information for ueIds
  > 6 | Channel information | Sends UE-specific channel information from the O-DU to the O-RU
  > 7 | LAA | ...
  > 8 | ACK/NACK Feedback | Sent from the O-RU to the O-DU ...
  > 9 | SINR reporting | Reporting of post-equalization SINR values to the ODU; applicable for DMRS-BF-EQ
  > 10 | RRM measurement reports | RRM measurement report sent from O-RU to O-DU. ...
  > 11 | Request RRM measurements | Sent by O-DU to request O-RU to perform one or more RRM measurements.
  > 12-255 | Reserved for future use
- 說明：與 beam 或 layer 相關的 Section Type 有：
  - ST1 / ST3：beamId 15 bit
  - ST4：TD beam 設定與 antMask
  - ST5：ueId 15 bit
  - ST6：ueId + H
  - ST9：每個 layer 的 SINR

### [CUS-031] Section Type 與可用 Section Extension 對照
- 出處：§7.3.2、Table 7.3.2-1
- 原文：
  > 0 | ... | 6, 7, 9, 12,22
  > 1 | Most DL/UL radio channels | 1-7, 9-13, 18-20, 22, 23, 29, 31
  > 3 | PRACH and mixed-numerology channels | 1-7, 9-13, 18-20, 22, 23, 29, 31
  > 4 | Slot Configuration Control | none
  > 5 | UE scheduling information (ueId assignment to section) | 4-6, 8, 9, 10, 12-18, 20-32
  > 6 | Channel information | 15, 21, 22
  > 7 / 8 / 9 | ... | none
  > 10 | RRM measurement reports | 6, 12, 20
  > 11 | Request RRM measurements | 6, 9, 12, 20, 22
- 說明：SE1、SE2、SE3、SE11、SE19 只能搭配 ST1 / ST3（屬於 beamId 類方法）；SE8、SE14、SE16、SE17、SE24～SE28、SE30、SE32 只能搭配 ST5（屬於 ueId 類方法）。SE15 與 SE21 可以搭配 ST5 或 ST6。

### [CUS-032] Section Type 1 / 3 的 beam 相關欄位
- 出處：§7.4.3（Table 7.4.3-1）、§7.4.5（Table 7.4.5-1）
- 原文：
  > Section Fields: sectionId ... 12 bits. rb ... 1 bit. symInc ... 1 bit. startPrbc ... 10 bits. numPrbc ... 8 bits. reMask ... 12 bits. numSymbol ... 4 bits. ef (extension flag) field: 1 bit. beamId (beam identifier) field: 15 bits.
  > （ST3 另有）freqOffset (frequency offset) field: 24 bits.
- 位寬：beamId 15 bit，與 ef 共用 2 octet
- 說明：同一 section 內的 PRB 與 RE 使用同一個 beamId（除非另帶 SE11 或 SE19）。

### [CUS-033] beamId（beam identifier）語意
- 出處：§7.5.3.9
- 原文：
  > This parameter defines the beam pattern to be applied to the U-Plane data. beamId = 0 means no beamforming operation will be performed. No beamforming operation implies that the O-RU shall not apply any phase or amplitude weights to the U-Plane data and that the resulting RF signal will be applied to all antenna elements in the group equally.
  > If the multiple beamId tables feature is not supported by the O-RU or it is not configured by O-DU via the M-Plane, it is intended that the beamId be global for the O-RU meaning there are 32767 possible beams shared within the O-RU for all eAxC_IDs and shared between UL and DL (beamId=0x0000 is reserved for no beamforming).
  > If the multiple beamId tables feature is configured ... then the beamId value (and the associated beam) is specific to the beamId table configured (via M-Plane parameter configured-[tr]x-beamId-table-index) for the array carrier associated with the eAxC receiving the beamId value.
  > An upper bound on the number of beamIds that can be addressed per eAxC or per sets of eAxCs, per symbol and per slot, for DL and for UL respectively, shall be conveyed via M-Plane messaging ...
  > Value range: {000 0000 0000 0001b-111 1111 1111 1111b; 000 0000 0000 0000b means no BF to be done}. Type: unsigned integer. Field length: 15 bits. Default Value: 0000 0000 0000 0000b (no beamforming).
- 位寬/值域：15 bit unsigned；0 = 不做 BF；1–32767 為有效 beam
- 說明：
  - 預設情況下，beamId 在全 O-RU 共用，DL 與 UL 也共用。
  - 啟用 multiple beamId tables 時，beamId 改為每個 array-carrier 各自解讀（MP §15.4.6）。
  - beamId 的範圍劃分（PDBF / WDBF / TD / FD / hybrid 各自的區段）由 M-plane 的 `initial-beam-id` 與 `max-number-of-beam-ids` 決定（ORAN-B06）。
  - 上限由 `endpoint-beam-capacity`（ORAN-060）回報。

### [CUS-034] Section Type 5（UE scheduling）欄位
- 出處：§7.4.7、Table 7.4.7-1
- 原文：
  > Section Type 5 is used for UE scheduling information ... ef (extension flag) field: 1 bit. ueId field: 15 bits.
- 說明：ST5 的 section header 與 ST1 相同，只是把 beamId 換成 ueId。ST5 是 CIBF 與 DMRS-BF 的每 slot 排程訊息。

### [CUS-035] ueId 語意
- 出處：§7.5.3.10
- 原文：
  > This parameter supports CIBF by providing a logical identifier for the set of channel information associated with a spatial stream of a UE sent via Section Type 6. ... This is just a label ...
  > If the O-DU sets the ueId in the section header in ST 5 to 0x7FFF, the O-RU shall interpret that the PRBs in the section description are not scheduled for the representative eAxC_ID（在 non-scheduled-ueId-supported / -enabled = TRUE 時）
  > In the context of use for CIBF, the value of ueId can be associated with at most one set of channel information ... Mapping of ueId value to a set of channel information is global per O-RU.
  > NOTE 1: ... there is a limit on the number of valid ueId values an O-RU can support, which is dictated by O-RU advertised M-Plane parameter 'max-number-ues-15bit', which applies to CIBF.
  > The "ueId space" mentioned above is the product of max-num-ues-supported and 2 to the power of ueid-layer-bits-configured.
  > Example: If the maximum number of UEs for DMRS-BF were declared to be 10 ..., and there are 3 bits configured for UE layers, then the permitted range of ueId (the "ueId" space) would be from 0 to 79
  > Value range: {000 0000 0000 0000b-111 1111 1111 1111b}. Type: unsigned integer. Field length: 15 bits.
- 位寬/值域：15 bit，0–0x7FFF；0x7FFF 在特定情況下代表「不排程」
- 說明：
  - 在 CIBF 中，一個 ueId 對應一個 UE 的一個 spatial stream 的通道資訊（等同 SRS port 或 layer 的通道）。
  - 在 DMRS-BF 中，ueId 的高位元代表 UE，低位元代表 layer。
  - M-plane 對應 `max-number-of-ues-15bit`（ORAN-B17）。

### [CUS-036] Section Type 6（Channel information）格式：H 矩陣
- 出處：§7.4.8、Table 7.4.8-1；§7.5.2.11；§7.5.3.13
- 原文：
  > Section Type 6 is used for sending channel information for a specific ueId
  > Common Header Fields: ... numberOfUEs (number of ueId-specific channel information data sets) field: 8 bits. ciCompHdr (channel information compression header) field: 8 bits.
  > Section Fields: ef ... 1 bit. ueId field: 15 bits. reserved ... 20 bits. rb ... 1 bit. Value = 0 shall be set. symInc ... 1 bit. startPrbc ... 10 bits. numPrbc ... 8 bits. ciCompParam ...: 0 or 8 bits. ciIsample ... field: 1-16 bits. ciQsample ... field: 1-16 bits.
  > （Table 7.4.8-1 內容順序）ciCompParam (for the first PRB or all PRBs ...), ciIsample (first PRB, first antenna), ciQsample (first PRB, first antenna), ciIsample (first PRB, second antenna) ... ciQsample (last PRB, last antenna), <padding with zeros to the next 4-byte boundary> may not be present (NOTE 2)
  > In absence of Section Extensions 21 and the M-Plane configuration ci-prb-group-size, the order of transmission shall be first Prbc for the first antenna to the last antenna, then second Prbc for the first to last antenna, and so on ... The bit-width per I and Q value shall be variable (determined by M-Plane configuration channel-information-bitwidth if channel information compression is not configured, and determined by ciCompHdr field ...)（§7.5.3.13）
  > Value range: {0000 0000 0000 0000b-1111 1111 1111 1111b} for each I and Q value. Type: signed integer, two's complement.
  > The value of this parameter [numberOfUEs] shall be equal to the value of numberOfsections（§7.5.2.11）
  > By default, Section Type 6 is 1-byte aligned instead of 4-byte aligned. ... "st6-4byte-alignment-required"（§7.3.1）
- 位寬/值域：
  - numberOfUEs：8 bit
  - ciIsample / ciQsample：1–16 bit，signed，two's complement
  - 通道資訊的維度：每個 ueId × numPrbc（或 PRB group 數）× 天線數（K），每個元素為一個複數
- 說明：
  - H 以「PRB 外層、天線內層」的順序展開，每個 ueId 各一段。
  - 「antenna」數等於 array element 數。原文未明寫；依 Annex J.5，heff,i ∈ C^(1×K) 推論而來。
  - 預設 1-byte 對齊；是否 4-byte 對齊由 M-plane `st6-4byte-alignment-required` 決定（ORAN-M07）。
  - 3GPP 對應：SRS 通道估計（38.211 §6.4.1.4）（推論）。

### [CUS-037] ciCompHdr / ciCompParam（通道資訊壓縮）
- 出處：§7.5.2.15、Table 7.5.2.15-1～-4；§7.5.3.32、Table 7.5.3.32-1
- 原文：
  > ciIqWidth | ciCompMeth | ciCompOpt （Table 7.5.2.15-1，共 8 bit）
  > 0000-1111b | value of ciIqWidth except a value of zero means 16 bits
  > 000b no compression / 001b block floating point / 010b block scaling / 011b µ-law / 100b–111b reserved
  > 0b compression per UE, one ciCompParam exists before the I/Q value of each UE / 1b compression per PRB, one ciCompParam exists before the I/Q value of each PRB
  > NOTE 2: When channel information compression is supported, O-RU shall support both compression per UE (ciCompOpt=0) and compression per PRB (ciCompOpt=1).
  > Default Value: 0000 0000b (no compression, 16-bit I and Q).
- 位寬：ciIqWidth 4 bit；ciCompMeth 3 bit；ciCompOpt 1 bit；ciCompParam 8 bit
- 說明：M-plane 對應 `channel-information-compression-method-supported`、`dynamic-channel-information-compression-supported`（ORAN-B17）。

### [CUS-038] Section Type 4：slot 層級命令（TD beam、TDD、TRX_CONTROL、ASM）
- 出處：§7.4.6、Table 7.4.6-1～-8；§7.5.2.17、Table 7.5.2.17-1；§7.5.3.38
- 原文：
  > st4CmdType = 1 ... TIME_DOMAIN_BEAM_CONFIG; st4CmdType = 2 ... TDD_CONFIG_PATTERN; st4CmdType = 3 ... TRX_CONTROL; st4CmdType = 4 ... Advanced Sleep Mode (ASM); st4CmdType = 5 ... TRX_CONTROL_BIDIR
  > cmdScope ... field: 4 bits. ... 0000b: ARRAY-COMMAND 0001b: CARRIER-COMMAND ...（O-RU-COMMAND = 0010b，見 §16.1）
  > EXAMPLE: If a group of eAxC_IDs: 1 to 20 are assigned to tx-array-0 in the O-RU, a Section Type 4 command with transport header eAxC_ID=1, 'dataDirection = 1', cmdScope = 'ARRAY-COMMAND (0000b)' shall apply to all eAxC_IDs: 1 to 20 associated with tx-array-0.
- 說明：這是 05_oran.md 第 13 項的出處。v21 的 cmdScope 定義位於 §7.5.2.17，與 YANG 所引用的章節號一致。對應 ORAN-051（`st4-supported-commands`、`st4-reception-mask`）。

### [CUS-039] Section Type 9（SINR 回報）
- 出處：§7.2.11；§7.3.1；Table 10.2.10-1
- 原文：
  > The ORU shall send layer specific SINR data to the ODU in C-Plane messages of Section Type 9 (see clause 7.4.11) using the eAxC specific to the layer.
  > The value of sinr-per-prb shall be an integer divisor of 12 (i.e. 1, 2, 3, 4, 6 or 12).
  > An entry in the M-Plane list supported-sinr-resolutions conveys combinations of sinr-per-prb and sinr-slot-mask values supported by the O-RU when number of data layers scheduled in any user group does not exceed a maximum value reported in sinr-max-data-layers.
- 說明：ST9 用在 DMRS-BF-EQ，每個 layer（eAxC）回報一次 post-EQ SINR，作用約等於 O-DU 做 LLR 時使用的 SINR。上限規則：SINR 解析度組合只在 layer 數 ≤ `sinr-max-data-layers` 時成立。

---

## D. Section Extension

### [CUS-040] Section Extension 全表（extType → 名稱 → 參數位寬）
- 出處：§7.6.1、Table 7.6.1-1
- 原文（逐列，格式為「extType | meaning | extLen | 參數（位寬）」）：
  > 1 | beamforming weights | var | bfwCompHdr(1) bfwCompParam(1) bfwI/bfwQ (var) per TRX 0…last
  > 2 | beamforming attributes | var | bfaCompHdr(2) bfAzPt bfZePt bfAz3dd bfZe3dd (var) bfAzSl(3b) bfZeSl(3b)
  > 3 | DL Precoding configuration parameters and indications | var (3 or 4 words) | codebookIndex(1) layerId(4b) txScheme(4b) numLayers(4b) crsReMask(12b) crsSymNum(4b) crsShift(1b) beamIdAP1(15b) beamIdAP2(15b) beamIdAP3(15b)
  > 4 | modulation compr. params | 1 | csf(1b) modCompScaler(15b)
  > 5 | modulation compression additional scaling parameters | var | mcScaleReMask(12b) csf(1b) mcScaleOffset(15b)
  > 6 | Non-contiguous PRB allocation | 2 | repetition(1b) rbgSize(3b) rbgMask(28b) priority(2b) symbolMask(14b)
  > 7 | Multiple-eAxC designation | 1 | eAxCmask(16b)
  > 8 | regularization factor | 1 | regularizationFactor(16b)
  > 9 | Dynamic Spectrum Sharing parameters | 1 | technology(1)
  > 10 | Multiple ports grouping | var | beamGroupType(2b) numPortc(6b) beamId (or ueId)(15b) portListIndex(1)
  > 11 | Flexible BF weights | var | disableBFWs(1b) RAD(1b) bundleOffset(6b) numBundPrb(1) bfwCompHdr(1) [bfwCompParam, beamId(2), bfwI/Q…] per bundle
  > 12 | non-contiguous PRB allocation with frequency ranges | var | priority(2b) symbolMask(14b) offStartPrb(r)(8b) numPrb(r)(8b)
  > 13 | frequency hopping | var | nextSymbolId(n)(4b) nextStartPrbc(n)(10b)
  > 14 | Null-layer Info. for CIBF | var | nullLayerInd(1)
  > 15 | Mixed-numerology Info. for CIBF | var | frameStructure(1) freqOffset(3) cpLength(2)
  > 16 | Antenna mapping for UE channel Info based UL beamforming | var | antMask(8) … | Bitmask of Max. 64 antenna
  > 17 | User port group indication | var | numUeId(4b)
  > 18 | Uplink Transmission Management | 2 | transmissionWindowOffset(16b) transmissionWindowSize(14b) toT(2b)
  > 19 | Compact multiple port beamforming information | var | disableBFWs(1b) repetition(1b) priority(2b) numPortc(6b) symbolMask(14b) bfwCompHdr(8b) [portReMask(12b) portSymbolMask(14b) bfwCompParam beamId(2) bfwI/Q] per port
  > 20 | Dedicated puncturing | var | numPuncPatterns(8b) [puncSymbolMask(14b) startPuncPrb(10b) numPuncPrb(10b) puncReMask(12b) rb(1b) rbgIncl(1b) rbgSize(3b) rbgMask(28b)] … multiSDScope(1b)…
  > 21 | Variable PRB group size for Channel Information | 1 | ciPrbGroupSize(1) prgSize(2b)
  > 22 | ACK/NACK request | 1 | ackNackReqId(2)
  > 23 | Multiple symbol modulation compression parameters | var | numSymPrbPattern(4b) symMask(14b) prbPattern(4b) numMcScaleOffset(4b) mcScaleReMask(12b) csf(1b) prbMode(1b) prbBlkSize(1) prbBlkOffset(1)
  > 24 | PUSCH DMRS configuration | var | aIpnPerSym(1b) antDmrsSnr(1b) userGroupSize(5b) userGroupId(8b) entryType(3b) dmrsPortNumber(5b) ...
  > 25 | Symbol reordering for DMRS-BF | var | txWinForOnAirSymbol0…13 (4b each)
  > 26 | Frequency offset feedback | var | numFoFb(7b) freqOffsetFb(16b)…
  > 27 | O-DU controlled dimensionality reduction | var | beamType(2b) numElements(6b) beamId(15b)…
  > 28 | O-DU controlled frequency resolution for SINR reporting | var | numUeSinrRpt(5b) numSinrPerPrb(3b)…
  > 29 | Cyclic delay | 1 | cdScgSize(4 bits) cdScgPhaseStep(8 bits)
  > 30 | PUSCH repetition indication | var | numRepUE(4b) isLastRep(1b) repIndex(6b) numReps(6b) repUeId(15b)
  > 31 | MCS information | var | mcsTable(4 bits) mcsIndex(6 bits)
  > 32 | Rank and TPMI measurement report | var | numCandRanks(4) uePrefRank(4) ueTpmiRankY(8) ueTpmiRankYSinrLX(16)
  > 0, 33-127 | reserved
- 注意（表內與內文的不一致，照原文記錄）：
  - SE27 的 numElements 在 Table 7.6.1-1 寫 6b，但 §7.7.27.3 寫 "Field length: 8 bits"、值域 0–255。
  - SE16 的 antMask 在表中欄位寫 8（octets），§7.7.16.2 寫 64 bits，兩者相符。
  - SE20 的 numPuncPatterns 在表中寫 8b，§7.7.20.2 的值域寫 {000000b-111111b}，但 Field length 為 8 bits。
  - SE32 的名稱在表中為「measurement report」，§7.7.32 標題為「measurement request」。
  - v21 中，**SE23 是 modulation compression，不是 mMIMO**；SE24 是 PUSCH DMRS 設定（屬於 DMRS-BF）。
- 共通欄位（§7.6.2）：extType 7 bit；ef 1 bit；extLen 以 4-byte word 為單位，一般為 8 bit，**SE11、SE19、SE20 為 16 bit**，值 0 保留。

### [CUS-041] SE1 Beamforming weights
- 出處：§7.7.1.1、Table 7.7.1.1-1；§7.7.1.2～7.7.1.5、Table 7.7.1.2-1～-3、Table 7.7.1.3-1
- 原文：
  > When Section Extension 1 is present in a section description, O-RU shall associate the set of beamforming weights conveyed in Section Extension 1 with the beamId conveyed in the section description. In subsequent C-Plane messages, the same beamId can be invoked without sending the beamforming weights again.
  > The parameter K is defined in clause 12.5.3. ... This Section Extension applies only to Section Types 1 and 3.
  > bfwCompHdr: ... For the block compression methods, the block size is the entire vector of beamforming weights, not some subset of them. ... Field length: 8 bits. Default Value: 0000 0000b (no compression, 16-bit I and Q).
  > bfwIqWidth: 0000-1111b | Value of bfwIqWidth except a value of zero means 16 bits.
  > bfwCompMeth: 0000b no compression / 0001b block floating point / 0010b block scaling / 0011b µ-law / 0100b beamspace compression type I / 0101b beamspace compression type II / 0110b - 1111b reserved
  > bfwCompParam: 0000b absent 0 octets / 0001b reserved(set to all zeros)|exponent (unsigned) 1 octet / 0010b blockScaler (unsigned, 1 integer bit, 7 fractional bits) 1 octet / 0011b compBitWidth | compShift 1 octet / 0100b activeBeamspaceCoefficientMask ceil(K/8) octets + blockScaler 1 octet / 0101b activeBeamspaceCoefficientMask ceil(K/8) octets + exponent 1 octet
  > NOTE 1: K is the number of elements in uncompressed beamforming weight vector ... K is ORU-specific and is calculated from parameters describing tx-array or rx-array, conveyed from the ORU to the ODU via the M-Plane
  > bfwI: ... The maximum number of weights in the Section Extension is O-RU-specific ... For bfwCompMeth indicating beamspace I and beamspace II the number of weights in the Section Extension is determined by activeBeamspaceCoefficientMask, for other bfwCompMeth values the number of weights in the Section Extension is always the maximum. Value range: {all zeros - all ones}. Type: signed integer, two's complement. Field length: 1-16 bits.
- 位寬/值域：
  - bfwCompHdr 共 8 bit，高 4 bit 為 bfwIqWidth，低 4 bit 為 bfwCompMeth（依 Table 7.6.1-1 的「IqWidth(3:0) | compMeth(3:0)」）
  - bfwI / bfwQ：1–16 bit，signed
  - 權重個數 = K（TRX 0 … K−1），beamspace 壓縮時例外
- 說明：
  - 權重會持久保存，之後只需帶 beamId 即可重用。
  - 權重的位元組順序見 Annex D.1；可選 little-endian（M-plane `little-endian-byte-order`，ORAN-002）。
  - M-plane 對應：`rt-bf-weights-update-support`（ORAN-B04）、`bf-compression-details`（ORAN-B08）。
  - 3GPP 對應：權重向量 w ∈ C^K，約等於 38.901 的 array steering 或 precoder（推論）。

### [CUS-042] SE2 Beamforming attributes
- 出處：§7.7.2.1、Table 7.7.2.1-1；§7.7.2.2（Table 7.7.2.2-1～-5）；§7.7.2.3～7.7.2.9；Annex F
- 原文：
  > Section Extension 2 applies only to Section Types 1 and 3.
  > bfaCompHdr：Reserved | bfAzPtWidth | bfZePtWidth (Octet 1)；Reserved | bfAz3ddWidth | bfZe3ddWidth (Octet 2)
  > For each of the four bitwidth values ... 000b = no bits, the field is not applicable (e.g. O-RU does not support it) or the default value shall be used. 001b = 2-bit bitwidth 010b = 3-bit ... 111b = 8-bit bitwidth (this is the highest bitwidth anticipated to be needed)
  > Field length: 16 bits (4 bits are reserved). Default Value: 0011 1111 0011 1111b (8-bit azimuth and zenith pointing angle and 8-bit azimuth and zenith beamwidth).
  > bfAzPt: ... the azimuth beamforming pointing angle in degrees. The valid range of values is O-RU-specific ... Type: signed integer, two's complement. Field length: 0-8 bits.
  > bfZePt: ... the zenith beamforming pointing angle in degrees. ... Type: unsigned integer. Field length: 0-8 bits.
  > bfAz3dd: ... the azimuth beamforming beamwidth in degrees. ... The value (000b) corresponds to the minimum valid beamwidth. Type: unsigned integer. Field length: 0-8 bits.
  > bfZe3dd: ... the zenith beamforming beamwidth in degrees. ... Type: unsigned integer. Field length: 0-8 bits.
  > bfAzSl: ... the azimuth beamforming sidelobe suppression value in dB. ... corresponds to a value of 10 dB for all zeros and increments in 5 dB steps (e.g. 001b corresponds to 15 dB ...). The value 111b corresponds to having a sidelobe suppression of 45 dB or more. Type: unsigned integer. Field length: 3 bits.
  > bfZeSl: （同上，zenith）Field length: 3 bits.
  > The beamforming attributes involving pointing angle (bfAzPt and bfZePt) specified in clause 7.7.2 are defined following 3GPP TR 38.901 [43], clause 7.1. ... The pointing parameter bfAzPt is defined as ϕ'. The pointing parameter bfZePt is defined as θ'. ... The beamwidth parameters bfAz3dd and bfZe3dd are defined as the angular widths at which the beam falls to 3 dB below the peak beam gain on both sides of the peak direction ... The sidelobe parameters bfAzSl and bfZeSl are defined as the suppression level of the highest sidelobe relative to the peak gain in the azimuth and zenith principal planes, respectively.（Annex F，normative）
- 位寬/量化：
  - 位寬編碼（4 個 3-bit 欄位）：000 = 不帶欄位，001～111 對應 2～8 bit
  - bfAzPt：signed，單位為度；bfZePt、bfAz3dd、bfZe3dd：unsigned，單位為度。**CUS 未規定度數的量化步距**，只寫「valid range is O-RU-specific，via M-Plane」（量化步距未找到）
  - bfAzSl / bfZeSl：3 bit，SL_dB = 10 + 5·code，111b 表示 ≥ 45 dB
- 說明：原 task 所寫的「bfAzSI / bfZeSI」，在規範中的正確拼寫是 bfAzSl / bfZeSl（Sl = sidelobe）。
  - 角度定義使用 **38.901 §7.1 的 LCS**：ϕ' 為方位角，θ' 為天頂角。
  - Annex F 引用 38.901 的 α（bearing）、β（downtilt）、γ（slant）作為 GCS→LCS 的旋轉參數。

### [CUS-043] SE3 DL precoding parameters（僅限 LTE TxD / LD-CDD）
- 出處：§7.2.4；§7.7.3.1～7.7.3.11、Table 7.7.3.1-1/-2、Table 7.7.3.4-1、Table 7.7.3.8-1；§8.3.4、Table 8.3.4-1；Annex I
- 原文：
  > Section Extension 3 applies only to Category B O-RU and to Section Types 1 and 3. Section Extension 3 may be used only for precoding schemes Transmit Diversity and Spatial Multiplexing with Large Delay CDD; for other LTE transmission modes and for NR, if there is precoding in the DL processing chain, precoding shall be included in the beamforming operation (that is, encoded in the beamforming weights).
  > LTE precoding schemes Transmit Diversity and Spatial Multiplexing with Large Delay CDD support two or four antenna ports, hence two or four beamIds are needed ... For Antenna Port 0, the beamId is contained in the C-Plane data section header, while the Antenna Ports 1-3 beamIds are contained in this Section Extension. When there are two antenna ports, ... ("extLen" = 0x3). When there are four antenna ports, ... ("extLen" = 0x4).
  > In the Transmit Diversity case the layerId shall be set to 1111b ("TxD").
  > For the non-zero layer number Rtcids, this Section Extension will still be provided to guide the precoding operation (provide the layer ID) but will not include beamIds (extLen = 0x1)
  > To create this association the O-DU shall use a unique eAxC_ID value for each data layer which shall not change within a slot.
  > codebookIndex: This parameter is not used and shall be set to zero. ... Field length: 8 bits.
  > layerID: {0000b-1111b}. 0000b implies layer0, 0001b implies layer1, 0010b implies layer2, 0011b implies layer3. (for Transmit Diversity, set to all ones) ... Field length: 4 bits. Default Value: 1111b
  > txScheme: 0000b Spatial Multiplexing with Large Delay CDD / 0001b Reserved / 0010b Transmit Diversity / 0011b-111b Reserved ... Field length: 4 bits.
  > numLayers: 0000b implies 1 layer, 0001 implies 2 layers, 0010 implies 3 layers, 0011b implies 4 layers. Field length: 4 bits.
  > crsReMask: ... Field length: 12 bits. crsSymNum: 0000b - 1101b: use symbol number 0 - 13 ...; 1110b - 1111b: reserved. Field length: 4 bits. crsShift: Value range: 0 or 1 ... Field length: 1 bit.
  > beamIdAP1/AP2/AP3: ... beamId = 0 means no beamforming operation ... Field length: 15 bits.
  > One way to implement precoding in the O-RU is via the beamId values, wherein a beamId points to a beamforming vector that also implements the precoding operation.（§7.2.4，NR）
- 位寬/值域：
  - codebookIndex：8b，固定為 0
  - layerID：4b，0–3，TxD 時為 0xF
  - txScheme：4b
  - numLayers：4b，實際 layer 數 = 值 + 1（1–4）
  - crsReMask：12b
  - crsSymNum：4b，0–13
  - crsShift：1b
  - beamIdAP1～AP3：各 15b
- 說明：**SE3 只適用於 LTE（TM2 TxD 與 TM3 LD-CDD）**，對應 36.211 §6.3.4（2/4 port）。NR 的 PMI（38.214 Type I/II）不經由 SE3 傳送，而是併入 BF 權重（SE1/SE11/SE19）。Table 10.2.10-1 的原文為 "While Category B is mandatory, it is possible to precode using beamforming so use of this extension is optional."

### [CUS-044] SE6 Non-contiguous PRB allocation（RBG mask）
- 出處：§7.7.6.1～7.7.6.6、Table 7.7.6.1-1、Table 7.7.6.2-1、Figure 7.7.6.3-1
- 原文（節錄）：
  > Section Extension 6 applies to Section Types 0,1, 3, 5, 10, and 11. It cannot be used with Section Extension 12 in the same section description.
  > O-DU shall set 'rb' bit to the value of zero. However, as an exception, if the O-RU supports the optional capability indicated by setting M-Plane feature flag "se6-rb-bit-supported", then the O-DU may use the "rb" bit. In this case, when the O-DU sets the "rb" bit to one, it shall also set the value of "rbgsize" to zero ...
  > lastRbgid = ceiling((numPrbc + (startPrbc mod rbgSize))/ rbgSize ) - 1.
  > f(0) = rbgSize - (startPrbc mod rbgSize); f(n) = rbgSize, where 0<n<lastRbgid; if (startPrbc + numPrbc) mod rbgsize > 0 then f(lastRbgid) = (startPrbc + numPrbc) mod rbgSize else f(lastRbgid) = rbgSize
  > The O-DU shall not use combinations of startPrbc, numPrbc and rbgSize leading to a value of lastRbgid larger than 27
  > MSB of rbgMask indicates the highest frequency resource block group.
  > symbolMask: ... LSB of symbolMask indicates symbol zero ... Field length: 14 bits. Default Value: 11 1111 1111 1111b
  > priority: Value range: {-1, 0, +1}. ... Field length: 2 bits. ... Value -2 is reserved
  > repetition: {0b=no repetition; 1b=repeated highest priority data section in the C-Plane message}. Field length: 1 bit.
- 位寬/值域：
  - rbgSize：3b（預設 001b；各值的 PRB 數見 Table 7.7.6.2-1，該表在 docx 中為圖形欄位，文字未能抽出）
  - rbgMask：28b（預設全 1）
  - symbolMask：14b
  - priority：2b，signed，值為 −1/0/+1
  - repetition：1b
- 說明：05_oran.md 第 17 項「requirement #3」在 v21 的文字版中是「O-DU shall set 'rb' bit…se6-rb-bit-supported」這一條。docx 轉出的文字沒有保留編號；依 §7.7.6.1 條列順序，這是第 3 條（第 1 條為 startSymbolId/rb/symInc/numSymbol，第 2 條為 symInc/numSymbol 可以任意設定）。對應 M-plane `se6-rb-bit-supported`（ORAN-M07）。3GPP 對應：38.214 §5.1.2.2.1 的 RBG（type 0）（推論）。

### [CUS-045] SE7 eAxC mask
- 出處：§7.7.7.1～7.7.7.2、Table 7.7.7.1-1
- 原文：
  > Section Extension 7 allows a specific C-Plane message to apply to multiple eAxC_ID values.
  > the O-RU shall apply the C-Plane message to configured eAxC_ID values matching the eAxC_ID value in the C-Plane message header with the matching operation checking only bits where the mask bits are non-zero.
  > if a single sector single band of the O-RU will be blanked ... the RU-Port-ID and CC-ID sub-field portions of the eAxCmask would be all zeros ("use this message for all layers/spatial streams and all component carriers")
- 位寬：eAxCmask 16b
- 說明：用一則訊息同時對多個 layer 或 CC 生效；適用於 ST0、ST1、ST3。

### [CUS-046] SE8 Regularization factor（MU-MIMO MMSE/RZF）
- 出處：§7.7.8.1～7.7.8.2、Table 7.7.8.1-1/-2；Annex J.5
- 原文：
  > This Section Extension is used for conveying value of regularization factor used for generating multi-user beamforming weight for the scheduled UEs in a slot. Regularization factor is the noise variance used in, for example, MMSE (Minimum Mean Square Error) and RZF (Regularized Zero-Forcing) computation of multi-user beamforming weights. The intended use case applies to Section Type 5 ...
  > The O-DU shall use Section Extension 8 to convey regularization factor to O-RU if the O-RU indicates support for Section Extension 8.
  > Section Extension 8 allows configuration of regularization factor per ueId ...
  > regularizationFactor: Value range: {0000 0000 0000 0000b - 1111 1111 1111 1111b}. Type: unsigned integer. Field length: 16 bits.
- 說明：這是 Annex J.5 公式中的 ξ。原文未定義 16-bit 值到雜訊變異數的換算（未找到）。M-plane 對應 `regularization-factor-se-supported` / `-configured`（ORAN-001、M07）。

### [CUS-047] SE10 Group configuration of multiple ports
- 出處：§7.7.10.1～7.7.10.4、Table 7.7.10.1-1/-2/-3、Table 7.7.10.4-1；§7.9.3；§13.5.4；§3.1「Port-list」
- 原文：
  > This Section Extension applies to Section Types 1, 3 and 5. In most cases, C-Plane section information for the multiple ports (i.e. layers or Tx/Rx paths) can be the same except beam IDs or UE IDs. When multiple ports share common section information within an O-RU, the C-Plane sections to be sent via corresponding ports are merged into one C-Plane section via a representative port using this Section Extension.
  > beamGroupType: 00b (common beam): the beamId in the section header is used as a common beamId for all the 'numPortc' ports which are grouped by M-Plane. This beamGroupType is not used for Section Type 5, and extLen = 0x01. 01b (beam matrix indication): the consecutive 'numPortc' beamIds subsequent to the beamId in the section header apply to the 'numPortc' ports. This beamGroupType is not used for Section Type 5 ... 10b (beam vector listing): the beamIds or ueIds listed in the Section Extension apply to the 'numPortc' ports. 11b (beamId/ueId listing with associated port-list index) ... Field length: 2 bits. Default Value: 00b
  > numPortc: This parameter indicates the number of eAxC ports indicated by the Section Extension. It can cover up to 64 ports. ... Value range: {000000b - 111111b}. 00 0000b expresses 64 ports. Field length: 6 bits.
  > portListIndex: ... Value range: {0000 0001b – 1111 1111b, 0000 0000b = Reserved}. Field length: 8 bits.
  > Port-list: Logical term which refers to M-Plane configured unique eAxC_ID list which is a union of {representative-tx-eaxc-id, member-tx-eaxc-id} or a union of {representative-rx-eaxc-id, member-rx-eaxc-id}（§3.1）
  > Unlike beamGroupType = 00b, 01b and 10b, support for beamGroupType=11b is explicitly advertised by the O-RU using the Boolean flag se-10-bgt-11b-supported. If an O-RU endpoint supports Section Extension 10 and supports beamforming method DMRS-BF then it shall support beamGroupType=10b and beamGroupType=11b.
  > SE1/SE11 ... can be used with Section Extension 10 only if the beamforming weights ... are the same for all streams (or layers). ... Section Extension 3 cannot be used with the Section Extension 10. ... Section Extension 7 cannot be used with Section Extension 10（Table 7.7.10.4-1）
- 位寬/值域：
  - beamGroupType：2b
  - numPortc：6b，範圍 1–64，其中 0 表示 64
  - 每個 port 的 beamId / ueId：15b
  - portListIndex：8b，0 保留
- 說明：用一個代表 eAxC 同時帶出多個 layer 的 beamId 或 ueId，是 MU-MIMO / mMIMO 下減少 C-plane 訊息量的主要工具。**上限：一次最多 64 個 port。** M-plane 對應 `eaxc-id-group-configuration`（ORAN-040）、`se10-member-candidate-list`、`se-10-bgt-11b-supported`。

### [CUS-048] SE11 Flexible beamforming weights（每個 PRB bundle 一組權重）
- 出處：§7.7.11.1～7.7.11.10、Table 7.7.11.1-1/-2；§7.9.4
- 原文：
  > This enables the ODU to provide different beamforming weights for different PRBs within one section to facilitate, e.g. zero-forcing precoding. The O-DU provides the numBundPrb parameter, which informs the O-RU how many PRBs are bundled together and share the same beamforming weights. ... This Section Extension applies only to Section Types 1 and 3.
  > bfwCompHdr: ... For the block compression methods, the block size is the vector of beamforming weights for a specific PRB bundle.
  > numBundPrb: ... When the division outcome is fractional value, one additional beamforming weight for each respective TRX is included to cover the orphan PRBs ... Value range: {all zeros - all ones}. The value zero is reserved. Field length: 8 bits.
  > bfwI/bfwQ: ... The total number of weights in the section depends on the number TRX at the O-RU and the number of bundled PRBs per beamforming weight. ... signed integer, two's complement. Field length: 1-16 bits.
  > disableBFWs: {0b=beamforming weights included in Section Extension; 1b= beamforming weights excluded}. Field length: 1 bit.
  > RAD: {0b = No reset; 1b = reset). Field length: 1 bit. Default Value: 1b
  > contInd: 0b = PRB region discontinuity ...; 1b = PRB region continuity ... Field length: 1 bit.（需 se11-continuity-flag-supported/enabled）
  > bundleOffset: ... the start of PRB bundle is given by startPrbc - bundleOffset. ... Value range: {000000b - 111111b}. Field length: 6 bits.（需 bundle-offset-in-se11-supported）
- 位寬/值域：
  - 共通欄位：disableBFWs 1b、RAD 1b、bundleOffset 6b、numBundPrb 8b、bfwCompHdr 8b
  - 每個 bundle：bfwCompParam、contInd 1b、beamId 15b、K 組 bfwI/Q
  - extLen 為 16 bit
- 說明：原文寫「up to L TRXs」；依 §7.7.11.5「depends on the number TRX」，L 指 TRX 數。數量關係：bundle 數 = ceil(PRB 數 / numBundPrb)。3GPP 對應：38.214 §5.1.2.3 PRG bundling（推論）。

### [CUS-049] SE12 Non-contiguous PRB allocation with frequency ranges
- 出處：§7.7.12.1～7.7.12.5、Table 7.7.12.1-1
- 原文：
  > Section Extension 12 applies to Section Types 0, 1, 3, 5, 10 and 11. It cannot be used with Section Extension 6 in the same section description.
  > startPrb(r) = startPrb(r-1) + numPrb(r-1) + offStartPrb(r) for r = 1, ..., R-1
  > Number of frequency ranges R shall be derived from extLen: R = (extLen - 1) × 2 + 1.
  > The number of frequency ranges R per section description shall be less than or equal to the value of optional M-Plane parameter "max-prb-ranges-per-sec-ext-12" if this parameter exists.
  > offStartPrb(r): Value range: 0 ... 255. Field length: 8 bits. numPrb(r): Value range: 0 ... 255. Field length: 8 bits.
- 位寬：priority 2b、symbolMask 14b、offStartPrb 8b、numPrb 8b
- 說明：以 PRB 範圍列表描述不連續的 PRB 配置。上限由 M-plane `max-prb-ranges-per-sec-ext-12` 決定。

### [CUS-050] SE13 PRB allocation with frequency hopping
- 出處：§7.7.13.1～7.7.13.3、Table 7.7.13.1-1
- 原文：
  > Section Extension 13 applies only to Section Types 1, 3 and 5. ... It is intended to be used for allocations with intra-slot frequency hopping.
  > Number of frequency hops R shall be derived from extLen: R = extLen × 2. ... The number of frequency hops R per section extension 13 shall be less than or equal to the value of optional M-Plane parameter "max-freq-hops-per-sec-ext-13"
  > nextSymbolId(n): Value range: {0000b-1111b}. Field length: 4 bits. nextStartPrbc(n): Value range: {00 0000 0000b-11 1111 1111b}. Field length: 10 bits.
- 說明：3GPP 對應：38.214 §6.3 的 PUSCH intra-slot frequency hopping（推論）。

### [CUS-051] SE14 Nulling layer information（CIBF）
- 出處：§7.7.14.1～7.7.14.2、Table 7.7.14.1-1/-2
- 原文：
  > This Section Extension applies to Section Type 5. This enables the O-DU to provide layer-by-layer indication, which denotes that the corresponding ueId is for nulling-layer indication.
  > O-RU generates beamforming weights considering all the ueIds, but once the beamforming weight is generated, O-RU shall set to zero weights for the layer(s) corresponding to those ueIds for which nullLayerInd is set to 0000 0001b.
  > nullLayerInd: 0000 0000b indicates the corresponding ueId is given for scheduled layer ... 0000 0001b indicates the corresponding ueId is given for making beam-nulling dimension, so this layer shall be nulled. ... Field length: 8 bits.
  > SE 14 shall carry (numPortc+1) nullLayerInd fields（與 SE10 併用時）
- 說明：MU-MIMO 干擾抑制的作法：把鄰區或非服務 UE 的通道納入 ZF 計算，但不實際傳送資料。

### [CUS-052] SE15 Mixed numerology information（CIBF）
- 出處：§7.7.15.1～7.7.15.4、Table 7.7.15.1-1
- 原文：
  > This Section Extension applies to Section Types 5 and 6. When this Section Extension is applied to Section Type 6, the value of FFT type in frameStructure and cpLength can be set as 0.
- 位寬：frameStructure 1 octet、freqOffset 3 octets、cpLength 2 octets（Table 7.6.1-1）

### [CUS-053] SE16 Antenna mapping in UE channel information based UL beamforming
- 出處：§7.7.16.1～7.7.16.2、Table 7.7.16.1-1/-2；Annex J.5
- 原文：
  > This Section Extension applies to Section Type 5. The Section Extension includes bitmask per RX endpoint to indicate the antennas to be pre-combined into the RX endpoint (i.e. eAxC_ID) ...
  > antMask: This parameter indicates the indices of antennas to be pre-combined per RX endpoint. Value range: {0x0000 0000 0000 0000 - 0xFFFF FFFF FFFF FFFF}. Each bit indicates whether the antenna corresponding to the bit is pre-combined (bit set to 1) or not (bit set to 0). The maximum number of antennas is 64. Type: unsigned integer. Field length: 64 bits. Default Value: 0x0000000000000000.
- 位寬/值域：64 bit；**上限為 64 個天線**
- 說明：UL CIBF 時，指定哪些天線要合併到某個 RX eAxC。這個 antMask 與 ST4 TRX_CONTROL 的 antMask（§7.5.3.54）是不同的欄位。

### [CUS-054] SE17 Indication of user port group
- 出處：§7.7.17.1～7.7.17.2、Table 7.7.17.1-1
- 原文：
  > This Section Extension applies to Section Extension 10 for beamGroupType=10b within Section Type 5 ... A user may have more than one ueIds (i.e. more than one channel information, for example if the UE supports Transmit Antenna Switching feature for SRS transmission ...). ... ueIds of each user are consecutive by exploiting the three reserved bits of ueId[2:0]. This means that the maximum number of ueIds per user that can be supported is 8.
  > numUeID: Value range: {0001b - 1000b}. {0000b; 1001b - 1111b} are reserved. Field length: 4 bits. Default Value: 100b (4 ueIds per user).
- 位寬/值域：4b，範圍 1–8；**每個 user 最多 8 個 ueId**
- 說明：3GPP 對應：38.214 §6.2.1 SRS antenna switching（1T2R/1T4R…）（推論）。

### [CUS-055] SE18 Uplink transmission management
- 出處：§7.7.18
- 位寬/值域：transmissionWindowOffset 16b（0–65535，單位 symbol）；transmissionWindowSize 14b（0–0x2710 µs）；toT 2b
- 說明：與天線或 BF 無關，列出只為完整。

### [CUS-056] SE19 Compact beamforming information for multiple port
- 出處：§7.7.19.1～7.7.19.14、Table 7.7.19.1-1、Table 7.7.19.14-1；§7.9.11
- 原文：
  > This Section Extension applies to Section Types 1 and 3. This Section Extension shall be used for sending compact beamforming information for multiple antenna ports (the term 'port' used henceforth in context of this Section Extension refers to logical antenna port). ... CSI-RS channel will benefit the most from using this extension, considering large number of CSI-RS ports and multiple CSI resource sets.
  > For section description with this extension, reMask in section header is an aggregate of portReMask for all ports specified in SE 19. Also, if section description has SE 19, the beamId in section header shall be ignored.
  > The first instance of this extension shall be used with 'repetition=0' and shall contain beamweights/beamIds for all ports in the range of startPrbc and numPrbc.
  > numPortc: ... this parameter indicates the number of logical antenna ports for which associated RE information and beamforming information is contained in this extension. It can cover up to 64 ports.
  > symbolMask: ... Value range: {00 0000 0000 0001b-11 1111 1111 1111b}. Field length: 14 bits.
  > portReMask: ... Each bit set in the portReMask indicates the RE associated with the port. MSB indicates the value for the RE of the lowest frequency in a PRB. Value range: {0000 0000 0001b-1111 1111 1111b}. Field length: 12 bits.
  > portSymbolMask: ... It is a subset of symbolMask ... Field length: 14 bits.
  > beamId (beam identifier for a port): refer to clause 7.5.3.9.
- 位寬/值域：
  - 共通欄位：disableBFWs 1b、repetition 1b、priority 2b、numPortc 6b（最多 64 個 port）、symbolMask 14b、bfwCompHdr 8b
  - 每個 port：portReMask 12b、portSymbolMask 14b、bfwCompParam、beamId 15b、K 組 bfwI/Q
  - extLen 為 16 bit
- 說明：一個 section 內可以讓不同 RE 使用不同的 port beam，適合 CSI-RS 資源集。3GPP 對應：38.211 §7.4.1.5 CSI-RS port（3000+）與 CDM 的 RE pattern。

### [CUS-057] SE20 Dedicated puncturing
- 出處：§7.7.20.1～7.7.20.12、Table 7.7.20.1-1；§7.9.12
- 原文（節錄）：
  > This Section Extension can be used with Section Types 1, 3, 5, 10, and 11. This extension specifies a puncturing pattern to be applied to the section description and optionally to sections following the section description in the same C-Plane message.
  > O-RU shall process the fields of the puncturing pattern and remove all the punctured REs from the current section description.
  > The number of puncturing patterns in Section Extension 20 and the number of highest priority sections in a C-Plane message together should be less than max-highest-priority-sec-per-cplane-message limits defined in M-Plane.
  > numPuncPatterns: Field length: 8 bits. puncSymbolMask: 14 bits. startPuncPrb: 10 bits. numPuncPrb: ... Field length: 8 bits. puncReMask: ... A value of '1' indicates presence of a puncturing RE ... Field length: 12 bits. rbgIncl: 1 bit. multiSDScope: {0b= ... current section description; 1b= ... current section description and following section descriptions within the C-Plane message}. Field length: 1 bit.
  > Section Extension 20 is compatible with all other Section Extensions.
- 位寬（依內文）：numPuncPatterns 8b、puncSymbolMask 14b、startPuncPrb 10b、numPuncPrb 8b（Table 7.6.1-1 寫 10b，兩處不一致）、puncReMask 12b、rb 1b、rbgIncl 1b、rbgSize 3b、rbgMask 28b、multiSDScope 1b；extLen 為 16 bit
- 說明：用來在 PDSCH section 中挖掉 CSI-RS、TRS 等其他 port 的 RE，避免重複描述。M-plane 參數：`se-20-full-prb-puncture-with-different-sectionId-supported`、`se-20-multi-sd-punc-pattern-suported`、`se-20-multi-sd-punc-pattern-enabled-tx/rx`。

### [CUS-058] SE21 Variable PRB group size for channel information / prgSize
- 出處：§7.7.21.1～7.7.21.3.4、Table 7.7.21-1、Figure 7.7.21.3.4-1
- 原文：
  > This Section Extension may be sent with Section Type 5 or Section Type 6. It enables the O-DU to send channel information with dynamic PRB group size ... SE 21 is applicable for CIBF.
  > ciPrbGroupSize: ... O-RU shall apply every pair of ciIsample/ciQsample for one PRB group received in Section Type 6 to ciPrbGroupSize number of continuous PRBs starting from index startPrbc + i × ciPrbGroupSize ... Value range: SE 21 with ST 5: {0}. SE 21 with ST 6: {2 – 254}, Value 1 and 255 are reserved for future use. Field length: 8 bits.
  > prgSize（with ST6）: 00b = if ciPrbGroupSize is 2 or 4, then precoding resource block group size = ciPrbGroupSize, otherwise precoding resource block group size = WIDEBAND, 01b = ... WIDEBAND, 10b = ... 2, 11b = ... 4.
  > prgSize（with ST5）: 00b = reserved, 01b = WIDEBAND, 10b = 2, 11b = 4. Field length: 2 bits
  > the offset between the start of the two grids shall be specified using the M-Plane parameter crb-to-prb-grid-offset ... This parameter specifies the value of 'offsetToCarrier' parameter as specified in the 3GPP TS 38.331
  > the O-DU shall enable only one of the features 'PRG-SIZE-SUPP-SE-21-WITH-ST6' or 'PRG-SIZE-SUPP-SE-21-WITH-ST5'.
- 位寬/值域：ciPrbGroupSize 8b（搭配 ST6 時為 2–254）；prgSize 2b
- 說明：H 可以按 PRB group 壓縮傳送。**prgSize 直接對應 38.214 §5.1.2.3 的 PRG size（2 / 4 / wideband）**；PRB grid 與 CRB grid 的偏移對應 38.331 的 offsetToCarrier。M-plane 對應：`channel-information-prb-group-configuration`（ORAN-035）、`ci-prb-group-size`。

### [CUS-059] SE22 ACK/NACK request
- 出處：§7.7.22
- 位寬：ackNackReqId 16b
- 說明：可搭配所有由 O-DU 送往 O-RU 的 ST；回覆以 ST8 傳回。與 BF 無直接關係。

### [CUS-060] SE23 Arbitrary symbol pattern modulation compression（與 MIMO 無關）
- 出處：§7.7.23.1
- 原文：
  > When SE 23 is used in a section description, the number of sets of {mcScaleReMask, csf, mcScaleOffset} values per symPrbPattern shall be limited by the M-Plane O-RU capability parameter 'max-mcscaleremask-per-prb'.
- 說明：這是 05_oran.md 第 14 項（§7.7.23.1，max-mcscaleremask-per-prb）的出處。**SE23 不是 mMIMO 相關的 SE。**

### [CUS-061] SE24 PUSCH DMRS configuration（DMRS-BF）
- 出處：§7.7.24.1～7.7.24.21、Table 7.7.24.1-1/-2
- 原文（節錄）：
  > The Section Extension 24 is used with Section Type 5 to convey PUSCH DMRS configuration used for DMRS-BF-EQ and DMRS-BF-NEQ beamforming methods.
  > userGroupSize: ... indicates number of UE data layers in the user group ... Value range: 0 – 12. Values 13 – 31 are reserved. Field length: 5 bits.
  > entryType: Value range: 0 – 3. Values 4 – 7 are reserved. Field length: 3 bits.
  > dmrsPortNumber: ... This parameter directly corresponds to p specified in 3GPP TS 38.211 v17.6 [55], clause 6.4.1.1.3. Value range: 0 – 11. Values 12 – 31 are reserved.
  > lambda: ... conveys a value of ⌊λ/2⌋, where λ is defined in 3GPP TS 38.211v17.6 [55], clause 6.4.1.1.1.1 ... Field length: 2 bits.
  > lowPaprType: ... See 3GPP TS 38.211v17.6 [55], clause 6.4.1.1.1.2
- 位寬/值域：
  - aIpnPerSym 1b、antDmrsSnr 1b
  - userGroupSize 5b（**每個 user group 最多 12 個 layer**）
  - userGroupId 8b、entryType 3b
  - dmrsPortNumber 5b（0–11，即 38.211 的 DMRS port，type 2 最多 12 個 port）
  - 其餘欄位：ueIdReset、dmrsSymbolMask、scrambling、nscid、dType、cdmWithoutData、lambda、lowPaprType、hoppingMode、firstPrb、lastPrb、posMeas（位寬見各子條，在此不逐一列出）
- 說明：各欄位直接對應 38.211 §6.4.1.1 的 PUSCH DMRS 參數。

### [CUS-062] SE25 / SE26 / SE28 / SE30 / SE31（DMRS-BF 輔助）
- 出處：§7.7.25、§7.7.26、§7.7.28、§7.7.30、§7.7.31
- 原文（SE25）：
  > The Section Extension 25 applies to Section Type 5 with dataDirection bit = 0 and shall only be used with Section Extension 24 which provides DMRS configuration information.
- 原文（SE26）：
  > This Section Extension is used with Section Type 5 to deliver the UE frequency offset from the O-DU to the O-RU and is valid only when dataDirection bit = 0 and when SE 24 is present
- 位寬：
  - SE25：txWinForOnAirSymbol0～13，各 4b
  - SE26：numFoFb 7b、freqOffsetFb 16b
  - SE28：numUeSinrRpt 5b、numSinrPerPrb 3b
  - SE30：見 Table 7.6.1-1
  - SE31：mcsTable 4b、mcsIndex 6b
- 說明：這些 SE 是 DMRS-BF 的輔助功能，與天線幾何無關。

### [CUS-063] SE27 O-DU controlled dimensionality reduction（DMRS-BF）
- 出處：§7.7.27.1～7.7.27.4、Table 7.7.27.1-1/-2
- 原文：
  > For beamType = 00b or 01b the Section Extension conveys a list of N beamId values or a range of N consecutive beamId values respectively and is an instruction for the O-RU to use the beamId values (conveyed as a list or a range) to reduce the dimension of input for DMRS-BF from K to N where N = numElements if numElements > 0 and N = 256 otherwise and K is the number of array elements. The Section Extension 27 shall only be used in sections with Section Extension 24
  > beamType: 00b – ... a list of beamId values. 01b – ... a range of beamId values. ... Field length: 2 bits.
  > numElements: ... Value range: {0 - 255}. Type: unsigned integer. Field length: 8 bits.
  > beamId: ... See clause 7.5.3.9 for further details of the value format.
- 位寬/值域：beamType 2b；numElements 8b（0 表示 256；Table 7.6.1-1 寫 6b，與內文不一致）；每個 beamId 15b
- 說明：由 O-DU 指定一組 beam（例如 DFT beamspace），把 K 維天線訊號降到 N 維。這是 mMIMO 在 beam 域處理的機制。**上限 N ≤ 256。**

### [CUS-064] SE29 Cyclic delay adjustment（CAT-B DL）
- 出處：§7.7.29.1～7.7.29.4、Table 7.7.29.1-1
- 原文：
  > Section Extension 29 applies only to Category B O-RUs and to Section Types 1, 3, and 5. Further, it is applicable to all downlink beamforming methods that involve or allow the operation of updating or calculating BF weights in real-time (see definition in Table 10.2.4-1, WDBF row). If an endpoint-type declares pdbf-cyclic-delay-supported as true, SE 29 is also applicable for PDBF ... used to control cyclic delay of a downlink user layer, e.g. to decorrelate DMRS ports for 3GPP Release 15 PDSCH DMRS.
  > EXAMPLE: ... cyclic-delay-scg-size = 48 subcarriers and cyclic-delay-phase-ramp-period-numsc-supported = {288, 612, 1596, 3276} corresponding to number of subcarriers for the supported carrier bandwidths (12×NRB in 3GPP TS 38.104 [8], clause 5.3.2).
- 位寬：cdScgSize 4b、cdScgPhaseStep 8b
- 說明：以每個 layer 的頻域相位斜坡實現 CDD，用來去相關 PDSCH DMRS port（38.211 §7.4.1.1）。M-plane 參數：`cyclic-delay-scg-period-combination(-supported)`、`cyclic-delay-scg-size`、`cyclic-delay-phase-ramp-period-numsc`。

### [CUS-065] SE32 Rank and TPMI measurement request
- 出處：§7.7.32.1～7.7.32.10、Table 7.7.32.1-1；§9.2.2.10
- 原文：
  > Section Extension 32 may be used in conjunction with Section Type 5 and Section Extension 24 to request provision of UE TPMI and uplink rank recommendation RRM measurement.
  > numOfUeAntPorts: ... corresponds to the quantity ρ defined in clause 6.3.1.5 of 3GPP TS 38.211 [55]. Value range: {2, 4}. Other values reserved. Field length: 4 bits.
  > tpmiIndex: ... the codebook UL TPMI index from the specific table defined in clause 6.3.1.5 of 3GPP TS 38.211 ... If the UL TPMI is not provided, the O-DU shall set the value of this parameter to 63 (0x3F). Value range: 0 – 27. 63 indicates no TPMI information. Field length: 6 bits.
- 位寬/值域：numOfUeAntPorts 4b（2 或 4）；tpmiIndex 6b（0–27，63 表示不提供）；其餘見子條款
- 說明：O-RU 從 DMRS 估算 UL rank 與 TPMI 建議。直接對應 38.211 §6.3.1.5 的 UL codebook（TPMI）與 38.214 §6.1.1.1。回報內容（uePrefRank、ueTpmiRankY 等）見 §7.5.3.75～78。

---

## E. 天線模型（§12.5）

### [CUS-070] 座標系（array 與 O-RU）
- 出處：§12.5.2、Figure 12.5.2-84
- 原文：
  > The array coordinate system is centred on the centre of the leftmost, bottom element of an array as presented in Figure 12.5.2-84. ... The diagram presents view from the front of array-panel (from UE).
  > x points towards broad-side
  > y increases to right, with antenna-array's columns
  > z points towards zenith
  > φ (phi) is azimuth angle, counter-clockwise rotation around z-axis, 0° points to broad-side, 90° points to y-axis
  > θ (theta) is zenith angle, counter-clockwise rotation around y-axis, 0° points to zenith, 90° points to horizon
  > ψ (psi) is angle, counter-clockwise rotation around x-axis, 0° points to horizon, 90° points to zenith
  > The O-RU coordinate system is identical to the array coordinate system of one of arrays in the O‑RU. The selection of the array used for the basis of the O‑RU coordinate system shall be fixed by the O-RU design.
- 說明：原點在左下元件的中心，x 軸為法線方向，y 軸朝右（沿 column），z 軸朝上。這與 38.901 §7.3 的 LCS 一致（x' 軸為 broadside），可直接對應：θ 同 38.901 的 zenith，φ 同 38.901 的 azimuth（推論；Annex F 另明示 SE2 的角度採用 38.901 §7.1）。ψ 用於極化角。這是 05_oran.md 第 1 項的出處，對應 ORAN-016/017、CCC tAzimuthAngle / tZenithAngle。

### [CUS-071] 天線模型參數（K、M、N、P、Q、dy、dz、極化、K'、h(k)）
- 出處：§12.5.1、§12.5.3
- 原文：
  > The following model is applicable for O-RU with one or more antennas, where each antenna has array of elements that are uniform (all elements have same properties) and organized into rectangular array (with rows and columns) that is planar (flat).
  > K - number of array elements in array (K = M × N × P × Q)
  > M - number of rows of array elements in array. M > 0; value 0 is reserved for future use.
  > N - number of columns of array elements in array. N > 0; value 0 is reserved for future use.
  > P - number of polarizations in array. P > 0, value 0 is reserved for future use.
  > Q - number of overlapping array elements (array-layers) in array. Each array-layer has M rows, N columns and P polarizations. Q>0; value 0 is reserved for future use. See Annex K for more information on array-layers.
  > x, y, z - position of centre of the leftmost, bottom element of array in O-RU coordinate system
  > φ, θ direction of normal vector perpendicular to array's surface in O-RU coordinate system (array's normal vector corresponds to x axis in array's coordinate system)
  > dy - mean distance between centres of nearby array elements in y direction in array coordinate system (distance between columns); value 0 is reserved for future use.
  > dz - mean distance between centres of nearby array elements in z direction in array coordinate system (distance between rows); value 0 is reserved for future use.
  > list of polarizations in array (this list has P elements, each representing p-th polarization); values ordered in ascending order of angle. Example: cross-polarized array having elements of one of two linear polarizations can be described by list: (-45°, +45°) indicating that array element with polarization index p=0 has linear polarization -45°, and array element with polarization index p=1 has linear polarization +45°.
  > independent power budget per layer - in case of an array with multiple layers, corresponding elements ... of different layers may have a shared power budget or have independent power budgets.
  > K' - number of frequency-domain beamforming weights φk' that can be applied within the array. 0<K'≤K; value 0 is reserved for array not supporting hybrid beamforming.
  > h(k) - mapping of array element k to frequency-domain beamforming weight φk' where k'=h(k). The mapping is represented as a list of lists: for every 0<k'<K' a list of K/K' numbers identifying array elements where frequency-domain beamforming weight φk' is applied.
  > The model assumes ... the elements corresponding to beamforming weights form a rectangular shape without overlapping i.e. every array element is linked with exactly one frequency-domain beamforming weight φk'.
  > horizonal plane half power (-3 dB) beam width of array element's radiation pattern / vertical plane half power (-3 dB) beam width ... / horizonal plane quarter power (-6 dB) beam width ... / vertical plane quarter power (-6 dB) beam width ...
  > ma,k - max rms power rating of array element of the array. Usage of max rms power rating is described in clause 8.1.3.3.
- 值域/規則：K = M·N·P·Q；M、N、P、Q 皆 > 0；0 < K' ≤ K；dy、dz 不為 0；極化列表依角度遞增排序
- 說明：這是 05_oran.md 第 2 項與第 4 項（極化索引 p）的出處。
  - 38.901 §7.3 的對應關係（推論）：M ≈ M（rows）、N ≈ N（cols）、P ≈ P、dy ≈ d_H、dz ≈ d_V；Q 是 O-RAN 特有的概念（overlapping array-layer）。
  - 元件方向圖：CUS 只要求回報 −3 dB 與 −6 dB 波束寬度，**沒有給出 38.901 Table 7.3-1 的方向圖公式**；CUS 也沒有提供 beam pattern 計算公式（未找到）。
  - M-plane 對應：ORAN-011（M）、012（N）、013（Q）、014（dy）、015（dz）、016/017（φ, θ）、018（x,y,z）、019（極化）、022（independent-power-budget）。

### [CUS-072] Array element 編號（identification and ordering）
- 出處：§12.5.4（公式為 docx 內的 OMML）
- 原文：
  > For purpose of identification and ordering a number k is assigned to each element of array by the function f(m,n,p,q):
  > f(m,n,p,q) = q∙P∙M∙N + p∙M∙N + m∙N + n
  > m - row (bottom to top), 0 ≤ m < M
  > n - column (left to right, view from the front of array), 0 ≤ n < N
  > p - polarization index, 0 ≤ p < P; polarization value of polarization index p is ψp (see ψ in clause 12.5.2)
  > q - array-layer, 0 ≤ q < Q
  > NOTE: For a rectangular array, the function f(m,n,p,q) can be inverted allowing to determine a "tuple" (m,n,p,q) of k-th element.
- 公式：k = q·P·M·N + p·M·N + m·N + n，0 ≤ k < K
- 說明：k 的排列順序由內到外為 column → row → polarization → layer，也就是「先極化分組，再由下而上逐 row、由左而右逐 column」。
  - 這個 k 同時是以下三者的索引：SE1/SE11/SE19 的 bfwI/Q 第 k 個 TRX、ST4 antMask 的第 k bit，以及 M-plane `array-element-id`（ORAN-021）。
  - 這是 05_oran.md 第 3 項（Identification and Ordering of Array Elements）的出處。
  - 與 38.901 §7.3 的元件索引方式不同（38.901 未規定編號順序），做數位孿生時需要自行轉換（推論）。

### [CUS-073] Array element 之間的關係（co-located / shared）
- 出處：§12.5.5
- 原文：
  > If element ka of array A and element kb of array B are in same position (same physical row and column) then ka and kb are co-located.
  > If element ka of array A and element kb of array B are co-located and share a power budget, then ka and kb are shared.
  > Relation of co-location is symmetric ... Relation of co-location is transitive ... Relation of sharing implies co-location
  > O-RU shall report via M-Plane relations between array elements. O-RU shall avoid reporting redundant relations ... In addition, the O-RU shall provide a concise representation of the common case of two arrays that have all elements in relation (e.g. rx-array of -45° polarization and corresponding rx-array of +45° polarization).
- 說明：M-plane 對應 `relations`（ORAN-024）。

### [CUS-074] 天線模型使用範例
- 出處：§12.5.6、Figure 12.5.6-85～-88
- 原文：
  > An O-RU that does not support beamforming can be represented with arrays having one element each. Note that a category B O-RU could be represented with an array with two elements to accommodate two polarizations while a category A O-RU would generally be represented with a tx-array with only one polarization (P=1).
  > if an O-RU does not support collecting the raw SRS by use of beams designed to mute signal from all elements except one then that O-RU - in addition to full rx-array - may expose rx-arrays with single elements
- 說明：非 BF 的 O-RU 可建模成 K=1（CAT-B 雙極化時可為 K=2）。為了讓 CIBF 取得 raw SRS，O-RU 可額外暴露單元件的 rx-array。

### [CUS-075] Array-layer（Q）範例
- 出處：Annex K（K.1～K.3，Figure K.1-1、K.2-1、K.3-1）
- 原文：
  > Figure K.1-1 shows an example of a rectangular array with 12 rows and 4 columns of array elements. There are four data converters ... Each data converter connects to all the 48 array elements (also known as the full-connection model in 3GPP). ... This type of connection creates four overlapping arrays ("array-layers") by reusing the same array elements.
  > Use case A ... the O-RU has 4 simple tx-arrays with 48 elements each. ... conveyed over the M-Plane as the array elements being "shared" according to clause 12.5.5.
  > Use case B ... O-RU has one tx-array with 4x48 elements. ... conveyed over the M-Plane as independent-power-budget being false according to clause 12.5.3.
- 說明：Q 對應 3GPP 的 full-connection hybrid 架構（38.901 / TR 36.897 的 full-connection 模型）（推論）。

### [CUS-076] TX 功率預算（CAT-A / CAT-B）
- 出處：§8.1.3.3
- 原文（節錄）：
  > In this clause, 𝑚a,k is the maximum rms power rating (in W) of tx-array element k of a tx-array a with K elements. ... The maximum rms power rating of array can be derived from 𝑚a,k by scaling linearly with the number of elements K (i.e. 𝑚a = K·𝑚a,k)
  > let 𝑔𝑐,𝑎,𝑘 be the gain [dB(mW/FS)] configured for tx-array element 𝑘 of tx-array 𝑎 for array carrier 𝑐. It is considered that the configured gain is same to every element ... the O-DU shall configure the O-RU by providing a value for 𝑔𝑐,𝑎,𝑘 in parameter 'gain' of tx-array-carrier.
  > 𝑔𝑐,𝑎 [dB(mW/FS)] = 𝑔𝑐,𝑎,𝑘 [dB(mW/FS)] + 10 × log10(K).
- 公式：m_a = K·m_{a,k}；g_{c,a} = g_{c,a,k} + 10·log10(K)
- 說明：這是 05_oran.md 第 8 項的出處（部分）。本節後段還有 CAT-A / CAT-B 的具體不等式，本次未逐條抽取。M-plane 對應：tx-array-carriers/gain（ORAN-071）、min-gain / max-gain（ORAN-022）。3GPP 對應：38.104 的 rated output power。

---

## F. Energy saving：antenna mask（§16）

### [CUS-080] Energy saving 總覽（TRX_CONTROL / ASM）
- 出處：§16.1、Table 16.1-1
- 原文：
  > TRX_CONTROL (st4CmdType = 3) involves the disabling of some or all antenna array elements for a period of time to save energy.
  > ASM (st4CmdType = 4) involves the disabling of all antenna array elements for a period of time to save energy.
  > There is no specific requirement for the O-RU to specifically power down anything in response to these commands
  > For both commands, startSymbolId shall be set to zero
  > For each of the two commands (TRX_CONTROL and ASM), there are four "sleep modes" that may be supported, each with a specific "wake-up duration" ... A defined-duration sleep command shall have a duration at least as long as the relevant wake-up duration.
  > By convention, the wake-up durations shall be arranged such that L < M < N (microseconds).
  > there shall be a separate set of declared supported sleep modes per tx-array and rx-array, and a separate set of declared sleep mode wake-up durations per tx-array and rx-array.
  > only sleep mode zero may be used when the symbolMask has a value other than all-zero or all-ones.
  > if an array carrier is deactivated while in an asleep condition, the carrier's asleep condition is "forgotten"
- 說明：sleep mode 0–3 對應的 wake-up duration 分別為 TRXC-mode0～3-wake-up-duration（M-plane）。這是 05_oran.md 第 19 項（§16、§16.1）的出處。

### [CUS-081] TRX_CONTROL / TRX_CONTROL_BIDIR：antenna mask 行為
- 出處：§16.2.1、§16.2.2、§16.2.3；§7.2.9.2.3
- 原文：
  > This is done using an antenna mask: the mask has as many bits as there are array elements, and the O-DU puts a "1" in a mask bit for each array element that is to be made or kept active, and a "0" in each array element that is to be made or kept inactive. ... the O-RU provides to the O-DU in a capability report a list of valid antenna masks. More specifically, every tx-array and rx-array shall have a specific list of valid antenna masks for that array
  > This example assumes O-RAN antenna model ordering, with the least significant mask bit (the rightmost bit) associated with the lower-left array element.
  > Each TRX_CONTROL command provided to the O-RU includes an antenna mask which replaces the previous mask
  > To simplify beam weight management, the O-DU shall send weights for all array elements even when a TRX_CONTROL has disabled some array elements. ... for the disabled array elements, the O-DU shall send zero values (both I and Q). For predefined-beam beamforming, a pre-stored weight vector shall be used that contains zero-value weights for the disabled array elements.
  > The TRX_CONTROL Section Type 4 command has only one valid cmdScope: ARRAY-COMMAND (0000b).
  > the activation of an array carrier does not change the asleep condition of the antenna array that array carrier is assigned to.
  > TRX_CONTROL_BIDIR ... shall be issued as a single ARRAY‑COMMAND instance that jointly applies to the associated tx‑array and rx‑array. The paired tx‑array and rx‑array shall have identical antenna element definitions, including physical X, Y, Z coordinates and polarization, and shall report the same set of valid antenna masks.
  > If the O-DU issues both TRX_CONTROL and TRX_CONTROL_BIDIR commands targeting the same antenna array or different arrays which are co-located, within the same slot, the behaviour of the O-RU is unspecified.
  > the largest overlapping array ..., not a sub-array of a larger overlapping array, shall be specified as the subject of the command（§7.2.9.2.3.2）
- 說明：
  - bit 值 1 表示元件開啟，0 表示關閉。
  - mask 必須屬於 O-RU 回報的 valid mask 列表。
  - 關閉的元件仍然要送權重，只是權重值為 0。
  - bit 的編號順序依 §12.5.4 的 k。
  - 這是 05_oran.md 第 19 項（§16.2）的出處；v21 的 §16.2 標題已改為 "TRX_CONTROL and TRX_CONTROL_BIDIR description"。
  - 3GPP / WG1 對應：NES 的 RF channel reconfiguration（ORAN-C03 antennaMask、WG1-008）。

### [CUS-082] antMask / log2MaskBits / sleepMode 欄位
- 出處：§7.5.3.51（Table 7.5.3.51-1）、§7.5.3.52、§7.5.3.54；Table 7.4.6-7
- 原文：
  > antMask: This parameter indicates which antenna array elements are commanded to enter or exit an energy-saving mode for a TRX_CONTROL command. The range of supported number of array elements is 2-16384, so the mask size can be as large as 16384 bits (2048 bytes) ...
  > The antMask parameter is integer bytes in size and is at least 2 bytes; ... array element zero (numbered according to the antenna model order) is associated with the least significant mask bit (bit 0). The O-DU should set the "extra" mask bits ... to zero.
  > A zero mask bit indicates an array-element that should be disabled ("put to sleep") while a one mask bit indicates an array-element that should be enabled ("woken up"). An all-zero antenna mask is valid and would disable all array elements ... This is not treated the same as an ASM command
  > When accompanied by an all-zero symbolMask ..., antMask shall be set by the O-DU to an all-ones state
  > Value range: {all zeros to all ones, no reserved values}. Type: bit mask. Field length: variable, 2 bytes - 2048 bytes.
  > log2MaskBits：0 reserved | 1→2 | 2→4 | 3→8 | 4→16 | 5→32 | 6→64 | 7→128 | 8→256 | 9→512 | 10→1024 | 11→2048 | 12→4096 | 13→8192 | 14→16384 | 15 reserved；NOTE 2: minimum antMask size is 16 bits
  > sleepMode: ... Value range: {0x0 - 0x3}. Field length: 2 bits.
- 位寬/值域：
  - log2MaskBits：4b，有效值 1–14，mask 位元數 = 2^值（最少 16 bit）
  - sleepMode：2b
  - antMask：2–2048 bytes
- **上限**：array element 數為 2–16384
- 說明：M-plane 對應 ORAN-051 / C03。

---

## G. 其他上限與規則（layers / antennas / ports）

### [CUS-090] 數量上限彙整
- 出處：見各條目
- 內容（皆為 CUS 原文值）：
  - 支援 CAT-A 的 O-DU：precoded streams 最少須支援到 8 個（§4.2.2.1）
  - beamId：15 bit，最多 32767 個 beam，0 = 不做 BF（§7.5.3.9）
  - ueId：15 bit；0x7FFF 在特定條件下保留（§7.5.3.10、§12.6.1.3.1.2）
  - eAxC_ID：16 bit（§5.1.3.2.7）
  - SE10 / SE19 numPortc：最多 64 個 port（§7.7.10.3、§7.7.19.4）
  - SE16 antMask：最多 64 個天線（§7.7.16.2）
  - SE17：每個 user 最多 8 個 ueId（§7.7.17.1）
  - SE24 userGroupSize：每個 user group 最多 12 個 layer；dmrsPortNumber 0–11（§7.7.24.6、§7.7.24.9）
  - SE27：降維後的 N ≤ 256（§7.7.27.3）
  - SE3 LTE：最多 4 layer、2 或 4 個 antenna port（§7.7.3）
  - ST4 antMask：array element 數為 2–16384（§7.5.3.54）
  - DMRS-BF ueId 的 layer bits：例如 4 bit 時，每個 UE 最多 16 layer、最多 2047 個 UE（§12.6.1.3.1.2 EXAMPLE）
  - SE32 numOfUeAntPorts：2 或 4；tpmiIndex 0–27（§7.7.32）
  - SINR 解析度：sinr-per-prb 必須是 12 的因數，適用條件為 layer 數 ≤ sinr-max-data-layers（§7.2.11）
  - 每個 endpoint 與每則 C-plane 訊息的 beam 數、PRB range 數、highest-priority section 數，由 O-RU 透過 M-plane 回報，O-DU 必須遵守（§7.8.2.1、§7.8.2.2；MP §15.8）
- 說明：這些上限可直接作為 schema 的 range constraint。

### [CUS-091] O-RU 每個 endpoint 的處理上限與 PRB range 計算方式
- 出處：§7.8.2.1.1、§7.8.2.1.2、§7.8.2.2
- 原文：
  > certain limits may be imposed by the O-RU per endpoint e.g. endpoint-section-capacity, endpoint-beam-capacity, endpoint-prb-capacity. When such limits are imposed by the O-RU, the O-DU shall comply with the limits
  > The total number of PRB ranges in all section descriptions in a symbol shall not exceed the value reported by the O-RU in the M-Plane parameter "max-prb-ranges-per-symbol". ... Number of PRB ranges in a symbol is the smallest number of sections without section extensions that could represent the beamforming configuration requested for the symbol.
  > The defined limits are the maximum number of beams, maximum number of highest priority sections and maximum number of PRB ranges per highest priority section with Section Extension 12 within a C-Plane message. Refer to clause 15.8 of the M-Plane Specification [7]
- 說明：這是 05_oran.md 第 15 項（§7.8.2.1.2）的出處，對應 ORAN-060、061 與 endpoint-prb-capacity。

### [CUS-092] C-plane / U-plane 耦合方法
- 出處：§7.8.1.1～7.8.1.5
- 原文：
  > Selected types of C-Plane messages (Section Types 1, 3 and 5) carry data section descriptions that convey information applicable to data sections carried in U-Plane messages.
  > [Coupling via sectionId value] This method of C-Plane and U-Plane coupling shall be used by default. The O-DU may configure the O-RU to use the other methods via the M-Plane.
- 說明：共有四種耦合方法：sectionId（預設）、frequency and time、frequency and time with priorities、以及 with priorities (optimized)。這是 05_oran.md 第 11 項的出處，對應 ORAN-M11 coupling-methods。

### [CUS-093] U-plane only DL mode（無 C-plane）
- 出處：§8.2.2
- 原文：
  > In addition, IQ data transfer without C-Plane may be applied to DL U-Plane data. This is applicable to deployment use cases where the O-RU is a category A O-RU without beamforming. When the feature is supported by the O-RU as indicated via the M-Plane feature UPLANE-ONLY-DL-MODE and enabled via the M-Plane parameter uplane-only-dl-mode-enable the O-DU may omit sending DL C-Plane messages to the O-RU.
  > In the present document this procedure is applicable to eAxCs assigned to receive a subset of uplink signals and channels - specifically PRACH and SRS
- 說明：只適用於不做 BF 的 CAT-A O-RU。這是 05_oran.md 第 9 項的出處，對應 ORAN-003；static PRACH/SRS 的 beam-id 對應 ORAN-063。

---

## (a) 回覆 05_oran.md「H. 需人工下載確認的章節」CUS 部分（#1～#21）

| # | 項目 | 是否確認 | 內容摘要 | v21 出處 |
|---|---|---|---|---|
| 1 | §12.5.2 座標系、azimuth/zenith | 已確認 | 原點在左下元件中心；x 為 broadside、y 朝右、z 朝上；φ 繞 z 軸，0° 為 broadside；θ 繞 y 軸，0° 為天頂；ψ 用於極化角 | §12.5.2、Fig 12.5.2-84（CUS-070） |
| 2 | §12.5.3 陣列幾何 M/N/Q、間距、左下元件位置、極化 p/P | 已確認 | K=M·N·P·Q；各參數 >0；dy、dz 為平均間距；極化列表依角度遞增；另含 K′、h(k)、元件 −3/−6 dB 波束寬度、m_{a,k} | §12.5.3（CUS-071） |
| 3 | Identification and Ordering of Array Elements | 已確認 | k = q·P·M·N + p·M·N + m·N + n | §12.5.4（CUS-072） |
| 4 | Polarisation index | 已確認 | p 的範圍 0 ≤ p < P；p 的極化值為 ψp；例如 (−45°, +45°) 對應 p=0 與 p=1 | §12.5.3、§12.5.4 |
| 5 | §12.4.3.4.2 參數 p′ | 已確認 | K = K′·p′；權重向量長度 = K′(p′+1) | §12.4.3.4.2（CUS-017） |
| 6 | §12.4.3.4.4 ST4 TIME_DOMAIN_BEAM_CONFIG | 已確認 | 由 `st4-for-time-domain-beamforming-weights-enabled` 啟用；tdBeamGrp 對應 K′ 個 tdBeamNum；每個 TD 向量長度為 p′（`p_dash`） | §12.4.3.4.4、§7.2.9.2.1、Table 7.4.6-3～5（CUS-019） |
| 7 | 「Weight-based dynamic beamforming」 | 已確認 | 更新規則，以及 beam-update-contention-control、beam-context-gap-period（16 bit µs，0xFFFF 表示 infinite） | §12.4.3.1～12.4.3.2（CUS-014/015） |
| 8 | §8.1.3.3 TX power budget | 部分確認 | m_a = K·m_{a,k}；g_{c,a} = g_{c,a,k} + 10log10K；CAT-A/B 的具體不等式未逐條抽取 | §8.1.3.3（CUS-076） |
| 9 | §8.2.2 U-plane only DL mode | 已確認 | 僅適用非 BF 的 CAT-A；由 UPLANE-ONLY-DL-MODE / uplane-only-dl-mode-enable 控制 | §8.2.2（CUS-093） |
| 10 | ecpriRtcid / ecpriPcid | 已確認 | 16 bit；DU_Port / BandSector / CC / RU_Port 的位寬由 M-plane 設定；1 個 eAxC 對應 1 個 spatial stream（CAT-B 為 1 個 layer） | §5.1.3.2.7、Table 5.1.3.2.7-2（CUS-003/004） |
| 11 | methods of coupling of C-plane and U-plane | 已確認 | 四種方法，sectionId 為預設 | §7.8.1（CUS-092） |
| 12 | frameStructure | 已確認 | 8 bit，前 4 bit 為 FFT size，後 4 bit 為 µ/SCS | §7.5.2.13、Table 7.5.2.13-1～3 |
| 13 | §7.5.2.17 ST4 cmdScope | 已確認 | 4 bit；0000b ARRAY、0001b CARRIER、0010b O-RU | §7.5.2.17、Table 7.5.2.17-1（CUS-038） |
| 14 | §7.7.23.1 max-mcscaleremask-per-prb | 已確認 | 限制每個 symPrbPattern 的 {mcScaleReMask, csf, mcScaleOffset} 組數；SE23 屬於調變壓縮 | §7.7.23.1（CUS-060） |
| 15 | §7.8.2.1.2 Limits on number of PRB ranges | 已確認 | 每個 symbol 的 PRB range 總數 ≤ max-prb-ranges-per-symbol，並附計數規則 | §7.8.2.1.2（CUS-091） |
| 16 | Elements for the C-Plane Protocol（ST6 4-byte 對齊） | 已確認 | ST6 預設 1-byte 對齊；st6-4byte-alignment-required=true 時需加 padding | §7.3（§7.3.1 內文）（CUS-036） |
| 17 | SE6 requirement #3 | 已確認（編號依條列順序推定） | rb 必須為 0；若 O-RU 支援 se6-rb-bit-supported，O-DU 可設 rb=1，同時 rbgSize=0 | §7.7.6.1（CUS-044） |
| 18 | freqOffset、cp-length | 已確認 | freqOffset 24 bit signed，frequency_offset = freqOffset × Δf × 0.5；CP_length = cpLength × Ts；cp-length 用於 symbol 0 與 7×2^µ，cp-length-other 用於其他 symbol | §7.5.3.11、§7.5.2.14 |
| 19 | §7.4.6、§16、§16.1、§16.2 TRX control / antenna mask | 已確認 | ST4 cmdType 3/5；antMask 為 1=on、0=off，LSB 對應 k=0；需使用 valid mask 列表；關閉的元件權重送 0；只能用 ARRAY-COMMAND | §7.4.6 Table 7.4.6-7、§16.1、§16.2.1～16.2.3、§7.5.3.51/52/54（CUS-080～082） |
| 20 | ST1/3/4/5/6 與 SE1/2/3/10/19/20 等完整定義 | 已確認 | 見 C、D 兩節；SE↔ST 對照見 Table 7.3.2-1；支援要求見 Table 10.2.10-1 | §7.3～§7.7、§10.2.10（CUS-030～065） |
| 21 | Shared cell / SE10 cascade | 已確認（摘要） | Shared cell 可用 SE10，但所有相關 O-RU 與 FHM 都必須支援；FHM 需設定 UL eAxC group，並回報 eaxc-id-group-capability | §13.5.4；另見 §7.9.3（SE10 optimization） |
| 22–30 | MP 章節（§15.2.4、§14.4、§20.3、§9.1.3、§4.8、Table 5、beamforming 檔案格式、新版 YANG、Table A.1-1） | 不在本文件範圍 | 屬於 O-RAN.WG4.MP，本次未查證。CUS 內提到的 MP 章節有：§15.4.6（multiple beamId tables）、§15.4.7（null steering）、§15.8（per C-plane message limits） | — |

---

## (b) Beamforming 方法 ↔ Section Type ↔ Section Extension ↔ M-plane capability 對照表

| BF 方法（CUS §12.4） | 使用識別 | Section Type | 必要/主要 SE | 可搭配 SE | 支援要求（Table 10.2.4-1 / 10.2.10-1） | M-plane capability / config leaf（YANG 名稱沿用 05_oran.md 的 ORAN 編號；CUS 內文提到的名稱另外標示） |
|---|---|---|---|---|---|---|
| 不做 BF | beamId = 0 | ST1 / ST3（或 U-plane only） | — | — | 非 BF 的 O-RU 必須收到 beamId=0 | `uplane-only-dl-mode-enable`（ORAN-003，CAT-A 非 BF） |
| PDBF（Predefined-beam） | beamId（15b） | ST1、ST3 | 無（只帶 beamId） | SE6/7/10(00b,01b,10b,11b)/12/13/19(disableBFWs=1)/20；SE29（需 pdbf-cyclic-delay-supported） | O-DU M；O-RU CM | `static-properties/beamforming-type`（B05）、`max-number-of-beam-ids` / `initial-beam-id`（B06）、`beam-information/beamforming-properties`、`beam-type`、`beam-group-id`、`coarse-fine-*`、`neighbour-beams-*`（B11～B15）、`predefined-beam-tilt-offset`（B20～B22）；CUS 提到的：NULL-STEERING 等、`configured-[tr]x-beamId-table-index`（multiple beamId tables，本地 YANG 未查證） |
| WDBF（Weight-based dynamic）：頻域或時域 | beamId + 權重 | ST1、ST3 | **SE1**（權重）或 **SE11**（每個 PRB bundle 一組權重）或 **SE19**（多 port） | SE10（僅在各 layer 權重相同時）；SE3 不可與 SE10 併用；SE29（CAT-B） | O-DU CM；O-RU CM（凡是內部計算權重者） | `rt-bf-weights-update-support`（B04）、`beamforming-type` frequency/time（B05）、`max-number-of-beam-ids` / `initial-beam-id`（B06）、`frequency-granularity` / `time-granularity`（B07）、`bf-compression-details`（B08）、`beam-update-contention-control-enabled`（O34）、`endpoint-beam-capacity`（O60）、`beam-update-contention-control-limits`（O62）、`little-endian-byte-order`（O02）；CUS 提到的：`beam-context-gap-period`、`se11-continuity-flag-supported/enabled`、`bundle-offset-in-se11-supported`（本地 YANG 未查證） |
| WDBF hybrid（FD+TD） | beamId（hybrid 空間） | ST1、ST3 + **ST4 cmdType 1**（TIME_DOMAIN_BEAM_CONFIG，可選） | SE1 / SE11（啟用 ST4 時只帶 FD 權重） | 同上 | 同上；ST4 TD config 為 Optional | `beamforming-type` = hybrid（B05）、`p-dash`（B10）、`st4-for-time-domain-beamforming-weights-enabled`（O04）、`supported-section-type4-config`（O51） |
| ABBF（Attribute-based） | beamId + 屬性 | ST1、ST3 | **SE2** | SE10（僅在各 layer 屬性相同時） | O-DU O；O-RU O | `beamforming-trough-attributes-supported`（B16）；bfAzPt 等六個屬性有效範圍對應的 YANG leaf 未找到 |
| CIBF（Channel-information-based） | ueId（15b） | **ST6**（H，週期性）+ **ST5**（每 slot 排程） | ST6：SE15 / SE21 / SE22；ST5：**SE8**（O-DU 為 CM）、SE10、SE14、SE16、SE17、SE21 | SE6/12/13/18/20 | O-DU O；O-RU O；ST5 與 ST6 為 CM；SE8 的 O-DU 為 CM | `beamforming-trough-ue-channel-info-supported`（B16）、`ue-specific-beamforming`：`max-number-of-ues-15bit`、`channel-information-compression-method-supported`、`dynamic-channel-information-compression-supported`（B17）、`channel-information-prb-group-configuration`（O35）、`st6-4byte-alignment-required`、`regularization-factor-se-supported`（M07）、`regularization-factor-se-configured`（O01）、`eaxc-id-group-configuration`（O40）；CUS 提到的：`channel-information-bitwidth`、`ci-prb-group-size`、`prg-size-supp-se-21-with-st5/st6-enabled`、`crb-to-prb-grid-offset`、`non-scheduled-ueId-supported/enabled` |
| DMRS-BF（EQ / NEQ，僅 NR PUSCH） | ueId（UE 位元 + layer 位元） | **ST5**（+ ST9 SINR、ST10/ST11 RRM；ST8 可選） | **SE24**（必要）、SE10（多 layer 時，需支援 bgt 10b/11b） | SE25、SE26、SE27（降維）、SE28、SE30、SE31、SE32 | DMRS-BF：O-DU O / O-RU O；EQ 與 NEQ 的 O-DU 為 CM；SE24 為 CM；ST9 在 O-RU 為 CM（EQ） | 本地 YANG（2022-12）未收錄。CUS 提到的：delay-profile（BF method）、`ueid-max-layer-bits`、`ueid-layer-bits-configured`、`max-num-ues-supported`、`max-num-ueids`、`user-group-mode`、`supported-user-group-self-assembly-modes`、UEID-PERSISTENCE / `ueid-persistence-enabled`、`supported-symb-reorder-capability`、`up-symbolId-type-supported`、`se26-usage-enabled`、`supported-sinr-resolutions`、`sinr-per-prb`、`sinr-slot-mask`、`sinr-max-data-layers`、`se10-member-candidate-list`、`se-10-bgt-11b-supported` |
| LTE DL precoding（CAT-B，TxD / LD-CDD） | beamId（AP0）+ beamIdAP1～3 | ST1、ST3 | **SE3** | 不可與 SE10 併用 | O-DU O；O-RU O | `ru-supported-category`（M01）；SE3 無專屬 leaf，屬於 `supported-section-extensions`（O50） |
| Energy saving（antenna mask） | antMask（array element 層級） | **ST4 cmdType 3 / 5**（TRX_CONTROL / _BIDIR）、cmdType 4（ASM） | —（ST4 不可帶 SE） | ST8 ready / ACK（SE22 不適用於 ST4，ST4 自帶 ackNackReqId） | O-DU O；O-RU O | `supported-section-type4-config` / `st4-reception-mask`（O51）；CUS 提到的：valid antenna masks 列表、TRXC-mode0～3-wake-up-duration（per array）；NES 對應 O-NESPolicy antennaMask（C03） |

通用 capability leaf：各 endpoint 支援的 ST / SE 由 `endpoint-types/supported-section-types/{section-type, supported-section-extensions}`（ORAN-050）回報，**SE 編號對照即上方 CUS-040（Table 7.6.1-1）**。

備註：
- 表中 M = Mandatory、CM = Conditional Mandatory、O = Optional。
- 「CUS 提到的」leaf 名稱逐字取自 CUS v21 內文，**未在本地 YANG 中查證其是否存在或其確切路徑**。
