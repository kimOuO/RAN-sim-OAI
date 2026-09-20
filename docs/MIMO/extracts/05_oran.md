# 05 — O-RAN（RU 端）天線 / Beamforming / MIMO 規則抽取

> 範圍：O-RAN WG4 M-plane YANG（O-RU）、WG1 Use Cases、WG3 E2SM-CCC（交叉對照）、Gemini Notebook 投影片（非規範性）。
> 規則：每個欄位都附出處；原文逐字保留；找不到的寫「未找到」。

## 0. 來源清單

| 代號 | 檔案 | 版本 / 說明 |
|---|---|---|
| Y-UP | `specs/oran-yang/o-ran-uplane-conf@2022-12-05.yang` | namespace `urn:o-ran:uplane-conf:1.0`；O-RAN SC 鏡像 `scp-oam-modeling/data-model/yang/published/o-ran/ru-fh/`，此鏡像最新的 revision 是 2022-12-05（對應 ORAN-WG4.M.0-v11.00） |
| Y-BF | `specs/oran-yang/o-ran-beamforming@2022-12-05.yang` | revision 2022-12-05 "version 11.0.0 — 1) introduce p-dash parameter"，reference "ORAN-WG4.M.0-v11.00" |
| Y-MC | `specs/oran-yang/o-ran-module-cap@2022-12-05.yang` | 2022-12-05 |
| Y-PE | `specs/oran-yang/o-ran-processing-element@2022-08-15.yang` | 2022-08-15 |
| Y-HW | `specs/oran-yang/o-ran-hardware@2022-12-05.yang` | 2022-12-05 |
| Y-CF | `specs/oran-yang/o-ran-compression-factors@2021-12-01.yang` | 2021-12-01 |
| WG1 | `O-RAN.WG1.TS.Use-Cases-Detailed-Specification-R005-v20.00.docx` | 用 soffice 轉成純文字後查閱 |
| CCC | `O-RAN.WG3.TS.E2SM-CCC-R005-v07.00.docx` | 引用 [9] = O-RAN.WG4.CUS.0-R003-v15.00；[10] = O-RAN.WG4.MP.0-R003-v15.00 |
| PAPER | `AI_Powered_O-RAN_MIMO_Optimization.pdf` | **非規範性**。共 11 頁，是 Gemini Notebook 產生的圖片型投影片（標題「智慧化賦能：O-RAN 架構下的 MIMO 最佳化技術 (WG1 技術規範解析)」），PDF 沒有文字層，內容由頁面影像人工判讀 |

YANG 路徑記法：`module : /data-node/...`（省略 prefix）。grouping 以 `grouping X` 標示，並寫出它被 `uses` 的位置。

**YANG 結構說明**
- `/user-plane-configuration` 由 `uses uplane-conf-group; uses general-config;` 組成（Y-UP L4039–4043）。
- `/beamforming-config` 是 `config false`，由 `uses beamforming-config; uses beamforming-supported-type; container beam-tilt` 組成（Y-BF L833–846）。
- `/module-capability` 含 `ru-capabilities`（config false）、`band-capabilities`（list，config false）、`rw-sub-band-info`（Y-MC）。

---

## A. o-ran-uplane-conf（Y-UP）

### A.1 general-config

### [ORAN-001] general-config/regularization-factor-se-configured
- 出處：Y-UP : `/user-plane-configuration/general-config/regularization-factor-se-configured`（grouping general-config，L418）
- 原文：`type boolean; default false;` "Informs if regularization factor in section extension is configured(true) or not(false), this leaf indicates whether the O-DU will send the regularization factor in section extension. If the O-RU does not support regularization-factor-se-supported in o-ran-module-cap.yang, this leaf is ignored."
- 型別/範圍/單位：boolean；default false；非 mandatory
- 說明：O-DU 是否在 section extension 中送出 regularization factor（MMSE 類預編碼的正則化因子）。前提是 O-RU 能力 ORAN-M07 為真。對應 3GPP：無直接對應，屬於 fronthaul 實作參數。

### [ORAN-002] general-config/little-endian-byte-order
- 出處：Y-UP : `/user-plane-configuration/general-config/little-endian-byte-order`（L429）
- 原文：`type boolean; default false;` "If little endian byte order for C/U plane data flows is supported by the O-RU, indicates if the O-RU should use little endian byte order for all UL and DL C/U plane data flows. If little endian byte order is NOT supported, this node is ignored (and the default bigendian byte order used)"
- 型別：boolean；default false
- 說明：C/U-plane 位元組序。與天線模型無關，列出來只是為了完整。

### [ORAN-003] general-config/uplane-only-dl-mode-enable
- 出處：Y-UP : `/user-plane-configuration/general-config/uplane-only-dl-mode-enable`（L442；`if-feature feat:UPLANE-ONLY-DL-MODE`）
- 原文：`type boolean; default false;` "If set to true, enable IQ data transfer without C-Plane in DL for all endpoints as specified in the CUS specification clause 8.2.2."
- 型別：boolean；default false
- 說明：DL 不送 C-plane（因此沒有 beamId 等控制資訊），只傳 IQ。間接出處：CUS §8.2.2。

### [ORAN-004] general-config/st4-for-time-domain-beamforming-weights-enabled
- 出處：Y-UP : `/user-plane-configuration/general-config/st4-for-time-domain-beamforming-weights-enabled`（L451；`if-feature feat:ST4-SLOT-CONFIG-MSG-SUPPORT`）
- 原文：`type boolean; default false;` "If O-RU indicates support for Section Type 4 command 'TIME_DOMAIN_BEAM_CONFIG' , O-DU may configure the O-RU to use Section Type 4 TIME_DOMAIN_BEAM_CONFIG command by setting this flag to 'true'. In which case, O-DU shall use only Section Type 4 TIME_DOMAIN_BEAM_CONFIG for specifying time-domain beam information. refer to clause 12.4.3.4.4 of CUS-Plane spec."
- 型別：boolean；default false
- 說明：啟用後，時域（hybrid）beam 資訊一律改用 Section Type 4 的 TIME_DOMAIN_BEAM_CONFIG 下達。間接出處：CUS §12.4.3.4.4。

### A.2 天線陣列參數：grouping `parameters`（tx-arrays 與 rx-arrays 共用）

> `list tx-arrays { key "name"; config false; uses parameters; ... }`（L3400）與 `list rx-arrays { key "name"; config false; uses parameters; ... }`（L3444）都使用這個 grouping。
> 以下 [ORAN-010]～[ORAN-022] 的路徑同時適用 `/user-plane-configuration/tx-arrays/...` 與 `/user-plane-configuration/rx-arrays/...`。
> **3GPP 對應**：一個 tx-array/rx-array 約等於 TR 38.901 §7.3 的天線面板（panel）。面板以 (M, N, P) 描述，O-RAN 另外多了陣列層數 Q。CCC 9.3.34 把幾何定義指向 CUS §12.5.2 與 §12.5.3。

### [ORAN-010] name
- 出處：Y-UP : `/user-plane-configuration/{tx,rx}-arrays/name`（grouping parameters，L661）
- 原文：`type string; mandatory true;` "Unique name of array antenna"
- 型別：string；mandatory；list key
- 說明：陣列 ID，供 endpoint（ORAN-040）、beamforming（ORAN-B03）與 relations 參照。

### [ORAN-011] number-of-rows
- 出處：Y-UP : `/user-plane-configuration/{tx,rx}-arrays/number-of-rows`（L667）
- 原文：`type uint16; mandatory true;` "Number of rows array elements are shaped into - M"
- 型別：uint16；mandatory（CCC 9.3.34 寫成 INTEGER (1..65535)）
- 說明：列數 M，對應 TR 38.901 的 M（每行的垂直元件數）。

### [ORAN-012] number-of-columns
- 出處：Y-UP : `.../number-of-columns`（L673）
- 原文：`type uint16; mandatory true;` "Number of columns array elements are shaped into - N"
- 型別：uint16；mandatory（CCC：1..65535）
- 說明：行數 N，對應 TR 38.901 的 N（水平元件數）。

### [ORAN-013] number-of-array-layers
- 出處：Y-UP : `.../number-of-array-layers`（L679）
- 原文：`type uint8; mandatory true;` "Number of array layers array elements are shaped into - Q"
- 型別：uint8；mandatory（CCC：1..255）
- 說明：陣列層數 Q，是 O-RAN 特有的維度。TR 38.901 沒有直接對應（38.901 只有 M, N, P, Mg, Ng）。Q 的精確語意見 CUS §12.5.3，需人工確認。

### [ORAN-014] horizontal-spacing
- 出處：Y-UP : `.../horizontal-spacing`（L685）
- 原文：`type decimal64 { fraction-digits 5; } units Meter;` "Average distance between centres of nearby AE in horizontal direction (in array coordinates system)"
- 型別：decimal64（5 位小數）；單位 Meter；非 mandatory
- 說明：水平元件間距 d_H。TR 38.901 用波長 λ 為單位，O-RAN 用公尺，換算時要除以 λ。

### [ORAN-015] vertical-spacing
- 出處：Y-UP : `.../vertical-spacing`（L694）
- 原文：`type decimal64 { fraction-digits 5; } units Meter;` "Average distance between centres of nearby AE in vertical direction (in array coordinates system)"
- 型別：decimal64（5 位小數）；Meter
- 說明：垂直間距 d_V，對應 TR 38.901 的 d_V（同樣需換算成 λ）。

### [ORAN-016] normal-vector-direction/azimuth-angle
- 出處：Y-UP : `.../normal-vector-direction/azimuth-angle`（L707）；container 描述為 "Counter-clockwise rotation around z and y axis."
- 原文：`type decimal64 { fraction-digits 4; } units Degrees;` "Azimuth angle, counter-clockwise rotation around z-axis. Value 'zero' points to broad-side, value '90' points to y-axis"
- 型別：decimal64（4 位小數）；Degrees
- 說明：陣列法向量的方位角（在 O-RU 座標系中），約等於 TR 38.901 §7.1.3 的座標旋轉角 α（bearing）。CCC 對應欄位 tAzimuthAngle 指向 CUS §12.5.2。

### [ORAN-017] normal-vector-direction/zenith-angle
- 出處：Y-UP : `.../normal-vector-direction/zenith-angle`（L715）
- 原文：`type decimal64 { fraction-digits 4; } units Degrees;` "Zenith angle, counter-clockwise rotation around y-axis. Value 'zero' points to zenith, value '90' points to horizon"
- 型別：decimal64（4 位小數）；Degrees
- 說明：法向量的天頂角，90° 表示水平。與 TR 38.901 的 downtilt β 關係為 β ≈ zenith − 90°（此換算屬推論，需依 CUS §12.5.2 確認座標定義）。

### [ORAN-018] leftmost-bottom-array-element-position/{x,y,z}
- 出處：Y-UP : `.../leftmost-bottom-array-element-position/x|y|z`（L725–752）；container 描述為 "Structure describing position of leftmost, bottom array element."
- 原文：x/y/z 各為 `type decimal64 { fraction-digits 4; } units Meter;`，描述分別是 "X dimension of position of leftmost, bottom array element"、"Y dimension of position of leftmost, bottom array element"、"Z dimension of position of leftmost, bottom array element"
- 型別：decimal64（4 位小數）；Meter
- 說明：陣列左下角元件在 O-RU 座標系的位置，CCC 的描述為 "Position of centre of the leftmost, bottom element of array in O-RU coordinate system. See O-RAN WG4.CUS [9] clause 12.5.3"。對應 TR 38.901 的元件位置向量 d̄（以第一個元件為原點）。

### [ORAN-019] polarisations (list) / p / polarisation
- 出處：Y-UP : `.../polarisations`（L754），`.../polarisations/p`（L762），`.../polarisations/polarisation`（L769）；typedef `polarisation_type`（L365）
- 原文：
  ```yang
  list polarisations { key "p"; min-elements 1; max-elements 2;
    description "List of supported polarisations.";
    leaf p { type uint8; mandatory true; description "Polarisation index. See CUS-plane"; }
    leaf polarisation { type polarisation_type; mandatory true;
      description "Type of polarisation supported by array."; } }
  typedef polarisation_type { type enumeration {
    enum MINUS_45; enum ZERO; enum PLUS_45; enum PLUS_90; }
    description "Type definition for polarisations"; }
  ```
- 型別：list，1..2 筆；p 為 uint8；polarisation 為 enum {MINUS_45, ZERO, PLUS_45, PLUS_90}
- 說明：list 筆數就是極化數，對應 TR 38.901 的 P（1 表示單極化，2 表示雙極化）。±45 對應 38.901 Model-2 的 ζ=±45°；ZERO/PLUS_90 對應 0°/90°（V/H）。p 的索引語意在 CUS 中定義，CCC 引用 §12.5.3。

### [ORAN-020] band-number（array 的頻段）
- 出處：Y-UP : `.../{tx,rx}-arrays/band-number`（L775）
- 原文：`type leafref { path "/mcap:module-capability/mcap:band-capabilities/mcap:band-number"; } mandatory true;` "This parameter informing which frequency band particular antenna array is serving for. Intended use is to deal with multiband solutions."
- 型別：leafref → ORAN-M20；mandatory（CCC 寫成 INTEGER (1..1024)）
- 說明：這個陣列服務的頻段，對應 3GPP operating band（TS 38.104）。

### [ORAN-021] related-o-ru-connectors (list) / name / array-element-id
- 出處：Y-UP : `.../related-o-ru-connectors`（L786）
- 原文：`list related-o-ru-connectors { key name;` leaf name：`type leafref { path '/hw:hardware/hw:component/hw:name'; } must "derived-from-or-self(deref(current())/../hw:class, 'or-hw:O-RU-ANTENNA-CONNECTOR')";` "Referenced name of O-RU connector used by the antenna array."；leaf-list array-element-id：`type uint16;` "Identifiers of array element(s) related to specific O-RU connector. Allowed values and semantic - as per CUS-Plane spec, clause 'Identification and Ordering of Array Elements'"；list 描述 "List of unique names that identify instances of O-RU's connectors the external [tr]x-array is reachable through."
- 型別：list；array-element-id 為 uint16
- 說明：外接天線時，記錄陣列元件與 O-RU 天線接頭的對應，接近 TR 38.901 的 TXRU 與元件對應（connection）。相關 identity 見 Y-HW：`O-RU-ANTENNA-CONNECTOR`（"...connector capable of interfacing between an O-RU and some antenna function."），子類有 `O-RU-FEEDER`、`O-RU-BF-CAL`（"beamforming calibration"）；augment 另有 `connector-label`（string, config false）。

### [ORAN-022] tx-arrays/min-gain、max-gain、independent-power-budget、capabilities
- 出處：Y-UP : `/user-plane-configuration/tx-arrays/min-gain`（L3408）、`/max-gain`（L3418）、`/independent-power-budget`（L3429）、`/capabilities`（L3437）
- 原文：
  - min-gain：`decimal64 {fraction-digits 4;} units dB;` "Min gain of RF path linked with array element (maximum over elements of array) or array layers"
  - max-gain：`decimal64 {fraction-digits 4;} units dB; mandatory true;` "Max gain of RF path linked with array element (minimum over elements of array) or array layers"
  - independent-power-budget：`type boolean; mandatory true;` "If true then every element of array has own, power budget independent from power budget of other elements. Else all elements of array that are at same row and column and have same polarisation share power budget"
  - capabilities：`list capabilities { description "List of capabilities related to this tx-array"; uses mcap:support-for-dl; }`
- 型別：dB（decimal64/4）；boolean
- 說明：每個元件 RF 路徑的增益範圍，以及功率預算是否可跨元件共享。min/max gain 取代了已 deprecated 的 max/min-power-per-pa-antenna（ORAN-M08）；TX 功率預算限制見 CUS §8.1.3.3。對應 3GPP：每個 TRX 的功率上限（TS 38.104 rated output power per TAB connector）。

### [ORAN-023] rx-arrays/gain-correction-range/{max,min}、capabilities
- 出處：Y-UP : `/user-plane-configuration/rx-arrays/gain-correction-range/max|min`（L3450–3470）、`/rx-arrays/capabilities`（L3472）
- 原文：max：`decimal64 {4} units dB; mandatory true;` "Array gain correction factor - maximum allowed value"；min："Array gain correction factor - minimum allowed value"；container 描述 "Array gain correction factor"；capabilities 為 `uses mcap:support-for-ul;`
- 型別：dB
- 說明：UL 增益校正允許的範圍，限制 ORAN-052 與 ORAN-043 兩者相加的結果。

### [ORAN-024] relations（陣列元件關係）
- 出處：Y-UP : `/user-plane-configuration/relations`（L3479）
- 原文：`list relations { key "entity"; config false; description "Structure describing relations between array elements";` 子節點 entity(uint16)、array1/array2（`uses array-choice`：tx-array-name / rx-array-name leafref）、`list types { key relation-type; leaf relation-type { enum SHARED; enum COALOCATED; } list pairs { key element-array1; leaf element-array1 (uint16) "Tells about id of element from array1"; leaf element-array2 (uint16) "Tells about id of element from array2"; } }`
- 型別：enum {SHARED, COALOCATED}（原文拼字就是 COALOCATED）
- 說明：描述 TX 與 RX 陣列的元件是共用還是同位置，可用於 TDD 互易性（reciprocity）判斷。

### A.3 Endpoint（eAxC 端點）與 link

> **3GPP 對應**：low-level-tx/rx-endpoint 以 eAxC ID 定址，約等於 fronthaul 上的一個「空間串流 / 天線埠」。Y-UP 的 eaxc 描述寫明 "one eAxC contains only one spatial stream (i.e. one beam per subcarrier) at a time"。
> CAT-A（O-RU 不做預編碼）時，eAxC 約等於 TR 38.901 的 TXRU／TS 38.214 的天線埠（port）；CAT-B（O-RU 做預編碼）時，eAxC 約等於 layer。

### [ORAN-030] grouping eaxc（e-axcid container）
- 出處：Y-UP : `/user-plane-configuration/low-level-tx-endpoints/e-axcid/*` 與 `/low-level-rx-endpoints/e-axcid/*`（grouping eaxc，L602）
- 原文（grouping description）："One eAxC identifier (eAxC ID) comprises a band and sector identifier (BandSector_ID), a component-carrier identifier (CC_ID) and a spatial stream identifier (RU_Port_ID). In this version of the specification, one eAxC contains only one spatial stream (i.e. one beam per subcarrier) at a time. Bit allocation is subdivided as follows: * O_DU_Port_ID: Used to differentiate processing units at O-DU * BandSector_ID: Aggregated cell identifier * CC_ID: distinguishes Component Carriers * RU_Port_ID: Used to differentiate spatial streams or beams on the O-RU The bitwidth of each of the above fields is variable this model is supposed to check if we are occupying bits continuously, but we do not have to occupy all 16 bits"
  - `o-du-port-bitmask` uint16 mandatory "mask for eaxc-id bits used to encode O-DU Port ID"
  - `band-sector-bitmask` uint16 mandatory "mask for eaxc-id bits used to encode the band sector ID"
  - `ccid-bitmask` uint16 mandatory "mask for eaxc-id bits used to encode the component carrier id"
  - `ru-port-bitmask` uint16 mandatory "mask for eaxc-id bits used to encode the O-RU Port ID"
  - `eaxc-id` uint16 mandatory "encoded value of eaxcid to be read by CU-Plane"
- 型別：五個欄位都是 uint16 且 mandatory（16-bit eAxC）
- 說明：RU_Port_ID 用來區分空間串流或 beam，約等於 TS 38.211/38.214 的 antenna port 或 layer 索引（取決於 CAT-A/B）；CC_ID 約等於 component carrier；BandSector_ID 約等於 cell/sector。欄位語意見 CUS 的 "ecpriRtcid / ecpriPcid" 條文（Y-MC 描述中有引用）。

### [ORAN-031] static-low-level-tx-endpoints（config false）
- 出處：Y-UP : `/user-plane-configuration/static-low-level-tx-endpoints`（L2552）
- 原文：
  - `name` string "Unique name of static-low-level-tx-endpoints object."
  - `restricted-interfaces` leaf-list leafref if:interface "Optionally used to indicate that a low-level link is constrained to operate only via a subset of the available interfaces."
  - `array`：`type leafref { path "/user-plane-configuration/tx-arrays/name"; } mandatory true;` "Contains distname of tx-arrays, particular low-level-tx-endpoints is in hardware dependency with. Note: single instance of tx-arrays can be referenced by many instances of low-level-tx-endpoints (e.g. to allow DU to handle multiple fronthauls and multiple component carriers)."
  - `endpoint-type`：leafref `../../endpoint-types/id` "Reference to endpoint type capabilities list element supported by this endpoint"
  - `capacity-sharing-groups`：leaf-list leafref "Reference to capacities of sharing-groups supported by this endpoint"
  - `supported-reference-level`（if-feature TX-REFERENCE-LEVEL）：list id / min / max（decimal64/4, dB, mandatory）"Informs about supported ranges for gain reference level."
  - `compression/dynamic-compression-supported`、`realtime-variable-bit-width-supported`（boolean）、`supported-compression-set-id`（leafref）
  - `uses endpoint-tdd-pattern-support`
- 型別：如上
- 說明：O-RU 本身定義的 TX 端點（一個端點約等於一個 TX port）。`array` 把端點綁到 tx-array（panel）。

### [ORAN-032] static-low-level-rx-endpoints（config false）
- 出處：Y-UP : `/user-plane-configuration/static-low-level-rx-endpoints`（L2667）
- 原文：欄位與 ORAN-031 相同，但 `array` 指向 `/user-plane-configuration/rx-arrays/name`（mandatory，"Contains distname of rx-arrays, particular low-level-rx-endpoints is in hardware dependency with. ..."）。另有 `prach-group`（leafref, require-instance false, "An optional leaf used for those rx endpoints that support PRACH, indicating the group id describing the set of of PRACH preambles supported"）、`uses endpoint-static-config-support`、`transmission-order`／`transmission-order-group`（uint32，if-feature ORDERED-TRANSMISSION）
- 說明：RX 端點約等於 RX port。

### [ORAN-033] low-level-tx-endpoints（config true）
- 出處：Y-UP : `/user-plane-configuration/low-level-tx-endpoints`（L2780）
- 原文：list 描述為 "Object model for low-level-tx-endpoints configuration - augmented static-low-level-tx-endpoints by local-address which cannot be added to static low-level-tx-endpoints as we cannot have modifiable element in static object"。子節點：`name`（leafref → static-low-level-tx-endpoints/name, mandatory）、`uses tx-endpoint-compression-grouping`、`uses scs-config`、`container e-axcid { uses eaxc; description "Contains local address of low level TX endpoint offered by NETCONF server."; }`、`uses coupling-methods`、`cplane-message-processing-limits-enabled`、`beam-update-contention-control-enabled`、`channel-information-prb-group-configuration`
- 說明：由 O-DU 設定 eAxC ID、壓縮方式、SCS 的可寫端點。

### [ORAN-034] low-level-tx-endpoints/beam-update-contention-control-enabled（rx 端點亦同，L3029）
- 出處：Y-UP : `/user-plane-configuration/low-level-tx-endpoints/beam-update-contention-control-enabled`（L2843；if-feature feat:BEAM-UPDATE-CONTENTION-CONTROL）
- 原文：`type boolean; default false;` "TRUE: O-DU shall support beam update contention control feature of O-RU.Thus requiring O-DU to comply with beam updates restrictions defined in CUS-Plane Spec Section 'Weight-based dynamic beamforming'. In this case applicable beam limits defined in 'beam-update-contention-control-limits' shall apply. FALSE: O-DU shall not support beam update contention control feature of O-RU. Applicable beam limits defined in 'endpoint-beam-capacity' shall apply"
- 說明：決定 beam 更新受哪一組上限約束（ORAN-062 或 ORAN-060）。間接出處：CUS「Weight-based dynamic beamforming」條文。

### [ORAN-035] low-level-tx-endpoints/channel-information-prb-group-configuration
- 出處：Y-UP : `.../low-level-tx-endpoints/channel-information-prb-group-configuration`（L2855；if-feature feat:CHANNEL-INFORMATION-PRB-GROUP）
- 原文：`enable-ci-prb-group`：boolean "Informs whether or not to enable channel information PRB group in the O-RU, if its value is set to true, the O-RU shall receive and process channel information (e.g., ST6) with PRB group size of configured ci-prb-group-size."；`ci-prb-group-size`：`uint8 { range "2..254"; }` "The configured channel information PRB group size. If enable-ci-prb-group is configured as TRUE, and the IE ciPrbGroupSize doesn't exsit in a section description for channel information, the parameter ci-prb-group-size shall be used for this section description. If the IE ciPrbGroupSize exsits in a section description for channel information, no matter whether enable-ci-prb-group is configured as TRUE, the IE ciPrbGroupSize shall be used for this section description."
- 型別：boolean；uint8 2..254（單位為 PRB）
- 說明：UE 通道資訊（ST6，用於 CAT-B 的 O-RU 端預編碼）的頻域顆粒度，約等於 TS 38.214 的 precoding resource group（PRG）概念。

### [ORAN-036] tx-endpoint-compression-grouping 中與 beamforming / 通道資訊相關的節點
- 出處：Y-UP : `.../low-level-tx-endpoints/compression/...`（grouping tx-endpoint-compression-grouping，L1701–1838）
- 原文（摘錄）：`channel-information-iq-bitwidth`（L1753）描述 "I/Q bitwidth for channel information in Section Type6."；`channel-information-bitwidth`（L1765）描述 "I/Q bitwidth for channel information in Section Type6."；另有 `list channel-information-compressions`（id, channel-information-compression-method, iq-bitwidth）與 `list bf-weights-compressions`（id, bf-weights-compression, iq-bitwidth）。完整 leaf 定義未逐字展開，請見原檔 L1753–1838。
- 說明：ST6 通道資訊與 beamforming 權重的位元寬度及壓縮方式。rx 側（L1840–1921）也有 bf-weights-compressions。

### [ORAN-037] low-level-rx-endpoints（config true）
- 出處：Y-UP : `/user-plane-configuration/low-level-rx-endpoints`（L2882）
- 原文：`name`、`uses rx-endpoint-compression-grouping`、`uses scs-config`、`list ul-fft-sampling-offsets`、`container e-axcid { uses eaxc; description "Contains local address of low level RX endpoint offered by NETCONF server."; }`、`eaxc-gain-correction`、`non-time-managed-delay-enabled`、`uses coupling-methods`、static PRACH/SRS 設定、`uses u-plane-transmission-control`、`ordered-transmission`、`cplane-message-processing-limits-enabled`、`beam-update-contention-control-enabled`
- 說明：可寫的 RX 端點。

### [ORAN-038] low-level-rx-endpoints/eaxc-gain-correction
- 出處：Y-UP : `/user-plane-configuration/low-level-rx-endpoints/eaxc-gain-correction`（L2949；if-feature EAXC-GAIN-CORRECTION）
- 原文：`type decimal64 { fraction-digits 4; } units dB; default 0;` "eAxC specific part of overall gain_correction. gain_correction = common array-carrier gain-correction + eAxC-gain-correction."
- 型別：dB；default 0
- 說明：每個 UL port 的增益校正分量，與 ORAN-052 相加得到總校正值。

### [ORAN-039] low-level-tx-links / low-level-rx-links
- 出處：Y-UP : `/user-plane-configuration/low-level-tx-links`（L1990）、`/low-level-rx-links`（L2076）
- 原文：tx-link 的子節點有 `name`（string, "Unique name of low-level-tx-link object."）、`processing-element`（leafref `/o-ran-pe:processing-elements/o-ran-pe:ru-elements/o-ran-pe:name`, mandatory, "Contains name of processing-element to be used as transport by low-level-tx-link, ..."）、`transport-session-type`（enum ETH-INTERFACE/UDPIP-INTERFACE/ALIASMAC-INTERFACE）、`transport-qualified-processing-element`、`tx-array-carrier`（leafref, mandatory, "Contains name of tx-array-carriers MO to be used as transport by low-level-tx-link"）、`low-level-tx-endpoint`（leafref, mandatory, "Contains name of low-level-tx-endpoints MO to be used as transport by low-level-tx-link"）。rx-link 的結構對稱，另多 `user-plane-uplink-marking` 與 `enhanced-user-plane-uplink-marking`。
- 說明：一條 link 同時綁定三者：{端點(eAxC)} × {array-carrier(載波)} × {processing-element(傳輸流)}。這就是 TX port 在載波上的實例化，概念上約等於「cell 的某個天線埠在某個 CC 上」。

### [ORAN-040] eaxc-id-group-configuration（Section Extension 10 分組）
- 出處：Y-UP : `/user-plane-configuration/eaxc-id-group-configuration`（L3540；if-feature mcap:EAXC-ID-GROUP-SUPPORTED）
- 原文：`max-num-tx-eaxc-id-groups` 等 4 個 leafref 指向 mcap eaxcid-grouping-capabilities。`list tx-eaxc-id-group { key "representative-tx-eaxc-id"; ...` 描述 "This is a list of the groups of the eAxC IDs assigned to low-level-tx-endpoints. Each group is a union of the 'member-tx-eaxc-id's and a 'representative-tx-eaxc-id'. The low-level-tx-endpoint associated to 'representative-tx-eaxc-id' is able to process the DL C-plane information for all the low-level-tx-endpoints associated to 'member-tx-eaxc-id's."；`representative-tx-eaxc-id` uint16 "This parameter contains eAxC_ID that populates content of C-Plane section extension 10 to eAxC_IDs configured in the group as 'member-tx-eaxc-id'(s)."；`member-tx-eaxc-id` leaf-list uint16 ordered-by user "... the parameters in the SE10 are applied to the eaxc-ids based on the order of eaxc-ids in the list when the section extension conveys unique parameters (beamId/ueId) per eaxc-id."。rx 側對稱（rx-eaxc-id-group）。
- 說明：多個 port／layer 共用一則 C-plane 訊息（SE10），並可依 port 順序分別帶入 beamId 或 ueId，適用於多層 MIMO。

### A.4 Endpoint 能力（endpoint-types，config false）

### [ORAN-050] endpoint-types/supported-section-types（section-type, supported-section-extensions）
- 出處：Y-UP : `/user-plane-configuration/endpoint-types/supported-section-types`（L2203）
- 原文：`list supported-section-types { key "section-type"; description "Indicates section types and extensions endpoints of this type support"; leaf section-type { type uint8; description "This parameter determines the characteristics of U-plane data to be transferred or received from a beam with one pattern id."; } leaf-list supported-section-extensions { type uint8; description "This parameter provides the extension types supported by the O-RU which provides additional parameters specific to the subject data extension"; } }`
- 型別：uint8 / leaf-list uint8
- 說明：端點支援的 Section Type（例如 1/3/4/5/6）與 Section Extension 編號。beamforming 方法（SE1 權重、SE2 屬性、SE3 DL precoding、SE19/20 等）是否支援，都由此回報。各 SE 的定義在 CUS 規範中，本地 YANG **沒有**逐一列出 SE 編號與方法的對應（未找到），需到 CUS 查證。
- 本地 YANG 中直接提到的 SE 編號：SE6、SE12（non-contiguous PRB，L1240/1251/1270/1449）、SE13（freq hops，L1284）、SE10（port grouping，L3592）、SE22（ACK/NACK request，Y-MC L585）；另有 regularizationFactor SE（ST5，見 ORAN-M07）。

### [ORAN-051] endpoint-types/supported-section-type4-config（st4-supported-commands, st4-reception-mask）
- 出處：Y-UP : grouping supported-section-type4-config（L1923），在 `/user-plane-configuration/endpoint-types` 中以 `uses`（if-feature ST4-SLOT-CONFIG-MSG-SUPPORT）引入
- 原文：`list st4-supported-commands` 描述 "This parameter specifies the list of Section Type 4 command types supported by O-RU."；`leaf st4-command-type` 描述 "Section Type 4 command types supported by O-RU."；`list st4-reception-mask` 描述 "List of symbol mask per command scope, specifying the O-RU capability to receive Section Type 4 message for a ... If the O-RU receives a Section Type 4 message with associated command for a symbol whose bit value is set to '0' in this bitmask, the O-RU shall reject the Section Type 4 message"；`cmd-scope` 的描述引用 "CUS-Plane specification, clause 7.5.2.17"
- 說明：ST4（slot 設定訊息）支援哪些 command，例如 TIME_DOMAIN_BEAM_CONFIG（見 ORAN-004）。enum 完整清單請見原檔 L1930–1944（本檔未逐字展開）。

### [ORAN-060] grouping endpoint-beam-capacity（max-beams-per-symbol / -per-slot / max-beam-updates-per-slot / -per-symbol）
- 出處：Y-UP : `/user-plane-configuration/endpoint-types/{max-beams-per-symbol, max-beams-per-slot, max-beam-updates-per-slot, max-beam-updates-per-symbol}`，以及 `/user-plane-configuration/endpoint-capacity-sharing-groups/...`（grouping endpoint-beam-capacity，L1300；在 L2281 與 L2457 被 uses）
- 原文：四個 leaf 都是 `type uint16 { range "min .. 32767"; }`
  - max-beams-per-symbol："Max number of beams within one symbol that can be processed by endpoint or processed collectively by group of endpoints sharing capacity If the parameter is absent or if value 0 is reported for the parameter, then the endpoint does not support beamforming operation."
  - max-beams-per-slot："Max number of beams within one slot that can be processed by endpoint or processed collectively by group of endpoints sharing capacity ..."（後半句同上）
  - max-beam-updates-per-slot："Max number of beams within one slot that can be updated by endpoint or processed collectively by group of endpoints sharing capacity ..."
  - max-beam-updates-per-symbol："Max number of beams within one symbol that can be updated by endpoint or processed collectively by group of endpoints sharing capacity ..."
  - grouping description："Parameters describing beam capacity where number of beams is understood as number of different beamId values. Parameters defined for beam updates shall be used to put a maximum limit on number of beam/beamIds which can be updated every slot/symbol. Note: This parameter does not put any restriction on which beams/beamIds can be updated. If the parameters defining beam capacity and beam updates are absent or if value 0 is reported for the parameters defining beam capacity and beam updates, then the endpoint does not support beamforming operation."
- 型別：uint16，範圍 0..32767（15 位元 beamId 空間）
- 說明：每個 symbol 或 slot 可同時使用或更新的不同 beamId 數量上限。值為 0 或缺少此欄位，代表該端點不支援 beamforming。對應 3GPP：沒有直接的 RAN1 參數，但會限制同一 symbol 內能 FDM 的 beam 數。

### [ORAN-061] grouping per-cplane-message-limits（beam 相關部分）
- 出處：Y-UP : grouping per-cplane-message-limits（L1401），在 endpoint-types（L2365）與 sharing groups 中被 uses
- 原文：只列出 leaf 名稱：`max-beams-per-cplane-message`（L1402）、`max-beams-per-slot-with-cplane-limits`（L1422）等。完整描述未逐字抽取，請見原檔 L1401–1468。
- 說明：啟用 C-plane 訊息處理限制時（`cplane-message-processing-limits-enabled`）適用的 beam 上限。

### [ORAN-062] grouping beam-update-contention-control-limits
- 出處：Y-UP : L1469；leaf `max-beams-per-symbol-with-beam-contention-control`（L1470）、`max-beams-updates-per-symbol-with-beam-contention-control`（L1478）
- 原文：只記錄 leaf 名稱，描述未逐字抽取（請見原檔 L1469–1490）。
- 說明：ORAN-034 為 TRUE 時適用的 beam 上限。

### [ORAN-063] static PRACH / SRS 的 beam-id
- 出處：Y-UP : `/user-plane-configuration/static-prach-configurations/prach-patterns/occasion-parameters/beam-id`（grouping static-prach-configuration，L3782）；`/user-plane-configuration/static-srs-configurations/srs-patterns/beam-id`（grouping static-srs-configuration，L3873）
- 原文：`type uint16 { range "min .. 32767"; } mandatory true;` "This parameter defines the beam pattern to be applied to the U-Plane data. beamId = 0 means no beamforming operation will be performed."
- 型別：uint16 0..32767；mandatory
- 說明：**beamId 語意的明確定義**：beamId=0 代表不做 beamforming。PRACH/SRS 若採靜態設定，beam 也直接寫在設定中。對應 3GPP：PRACH occasion 與 SSB 的關聯（TS 38.213 §8.1），但此處的 beamId 是 O-RU 內部的 beam pattern 索引，不等於 SSB index（此點為推論，未在原文中找到兩者的對應）。

### A.5 Array carriers

### [ORAN-070] tx-array-carriers 共同欄位（grouping tx-common-array-carrier-elements）
- 出處：Y-UP : `/user-plane-configuration/tx-array-carriers/{center-of-channel-bandwidth, channel-bandwidth, active, state, type, duplex-scheme, ...}`（L932）
- 原文：
  - center-of-channel-bandwidth：`uint64 units Hz; mandatory true;` "Centre frequency of channel bandwidth in Hz. Common for all numerologies. center-of-channel-bandwidth is the FREF translated from absolute-frequency-center (NREF) as per 3GPP TS 38.104. ..."
  - channel-bandwidth：`uint64 units Hz; mandatory true;` "Width of carrier given in Hertz"
  - active：`enumeration { INACTIVE "carrier does not provide signal - transmission is disabled"; SLEEP "carrier is fully configured and was active but is energy saving mode"; ACTIVE "carrier is fully configured and properly providing the signal"; } default INACTIVE;` "Indicates if transmission is enabled for this array carriers. ..."
  - state：enum DISABLED / BUSY / READY / ...（L988）
  - absolute-frequency-center：`uint32; status deprecated;`
- 說明：一個 tx-array-carrier 約等於「某 panel 上的一個 CC」，對應 3GPP 的 carrier（ARFCN/BW，TS 38.104）。

### [ORAN-071] tx-array-carriers/gain
- 出處：Y-UP : `/user-plane-configuration/tx-array-carriers/gain`（L3196）
- 原文：`type decimal64 { fraction-digits 4; } units dB; mandatory true;` "Transmission gain in dB. Value applicable to each array element carrier belonging to array carrier. The value of tranmsmission gain shall meet the constraints defined in CUS-Plane, clause 8.1.3.3."
- 型別：dB；mandatory
- 說明：每個元件的 TX 增益，約等於每個 TRX 的發射功率設定（受 ORAN-022 限制）。
- 備註：需求中提到的「downlink-radiation-offset」在本地 YANG **未找到**。實際存在的是 `downlink-radio-frame-offset`（L3209，`uint32 range 0..12288000`，"This parameter is used for offsetting the starting position of 10ms radio frame. ... Note2: Unit is 1/1.2288e9 s."）與 `downlink-sfn-offset`（L3221，`int16`，"Unit is in 10ms."），兩者都是時序偏移，與輻射無關。

### [ORAN-072] tx-array-carriers/reference-level、t-da-offset
- 出處：Y-UP : `/user-plane-configuration/tx-array-carriers/reference-level`（L3248；if-feature TX-REFERENCE-LEVEL）、`/t-da-offset`（L3233；if-feature EXT-ANT-DELAY-CONTROL）
- 原文：reference-level：`decimal64 {4} units dB; default 0;` "Allows to adjust reference level for sum of IQ signal power over eAxCs in this array-carrier."；t-da-offset：`uint32 units Tc; default 0;` "the time difference between the output of DL signal at the antenna connector of O-RU and the transmission over the air. units are Tc=~0.5ns=1/1.96608GHz. ..."
- 說明：對所有 eAxC 的 IQ 總功率做參考位準調整；外接天線的延遲補償。

### [ORAN-073] rx-array-carriers/gain-correction、n-ta-offset、t-au-offset
- 出處：Y-UP : `/user-plane-configuration/rx-array-carriers/gain-correction`（L3350）、`/n-ta-offset`（L3363）、`/t-au-offset`（L3372）
- 原文：gain-correction：`decimal64 {4} units dB; mandatory true;` "Gain correction of RF path linked with array element or array layers. Common part of overall gain_correction. gain_correction = common array-carrier gain-correction + eAxC gain correction."；n-ta-offset：`uint32 units Tc; mandatory true;` "Value of configurable N-TA offset units are Tc=~0.5ns=1/1.96608GHz"；t-au-offset：`uint32 units Tc default 0` "the time difference between the reception over the air and the input of UL signal at the antenna connector of O-RU. ..."
- 說明：n-ta-offset 對應 TS 38.211/38.133 的 N_TA,offset。

---

## B. o-ran-beamforming（Y-BF）

> 模組說明原文："This module defines the beamforming capabilities of an O-RU. Only O-RUs that support beamforming shall support this module."
> Feature：`MODIFY-BF-CONFIG`（"...supports an optional feature to modify beamforming configuration information"）、`BEAM-TILT`（"...allows to shift beam characteristic of all predefined-beams in elevation and/or azimuth direction (i.e. changing the service area or sector coverage) while preserving the beam adjacency among the beams within the service area "）。
> **本地 revision 中找不到的名稱**：`static-beams`、`pattern-idx`、`beamforming-trough-attributes` 以外的「method 1–4」列舉，以及 SE19/SE20 的任何字樣，在 o-ran-beamforming@2022-12-05.yang 中都**未找到**。這些名稱可能屬於更新版的 WG4 M-plane YANG（O-RAN SC 鏡像未收錄），需從 specifications.o-ran.org 取得新版 YANG 或 MP 規範才能確認。

### [ORAN-B01] beamforming-config（頂層 container）
- 出處：Y-BF : `/beamforming-config`（L833）
- 原文：`container beamforming-config { config false; description "A set of configuration data for the O-RU's beam forming functionality"; uses beamforming-config; uses beamforming-supported-type; container beam-tilt { if-feature BEAM-TILT; ... uses beam-tilt-state; uses beam-tilt-report; } }`
- 說明：唯讀的能力與狀態樹。

### [ORAN-B02] per-band-config（deprecated） / capabilities-groups
- 出處：Y-BF : `/beamforming-config/per-band-config`（L534）、`/beamforming-config/capabilities-groups`（L542）
- 原文：per-band-config：`list per-band-config { key band-number; config false; status deprecated; description "beamforming information per band"; uses per-band-config-element; }`；capabilities-groups：`list capabilities-groups { key capabilities-group; description "Capabilities groups identification number assigned to be referenced by operations and notifications. This also help to group particular beamforming capabilities and bind it with arrays"; leaf capabilities-group { type uint16; description "Capabilities group identification number. Number which is used just for reference in RPC and notification"; } uses per-band-config-element; }`
- 型別：capabilities-group 為 uint16（key）
- 說明：自 v2.0.0（2019-07-03）起改為以 capabilities-group 為單位（revision 描述："re-designed/switched from per band to per capabilities-group for addition flexibility"）。

### [ORAN-B03] per-band-config-element：band-number、tx-array、rx-array
- 出處：Y-BF : `/beamforming-config/capabilities-groups/{band-number, tx-array, rx-array}`（grouping band-num L409、array-lists L232）
- 原文：band-number：`leafref "/mcap:module-capability/mcap:band-capabilities/mcap:band-number"` "band information for the beamforming information related to the band number of module capabilities"；tx-array：`leaf-list ... leafref "/up:user-plane-configuration/up:tx-arrays/up:name"` "tx arrays belonging to this band number"；rx-array：同上，指向 rx-arrays，描述 "rx arrays belonging to this band number"
- 說明：把 beam 能力綁定到 panel（見 ORAN-010）。

### [ORAN-B04] static-properties/rt-bf-weights-update-support
- 出處：Y-BF : `/beamforming-config/capabilities-groups/static-properties/rt-bf-weights-update-support`（grouping static-properties，L254）
- 原文：`type boolean;` "The parameter informs if O-RU supports real time beamforming weights update through C-Plane messaging"
- 說明：為 true 時，O-DU 可在 C-plane 即時下發權重（weight-based dynamic BF，SE1），choice beamforming-type 的各 container 也才會出現。對應 3GPP：沒有直接 RAN1 參數，屬於 gNB 內部 BF 實作能力。

### [ORAN-B05] static-properties/beamforming-type（choice：frequency / time / hybrid）
- 出處：Y-BF : `/beamforming-config/capabilities-groups/static-properties/{frequency-domain-beams | time-domain-beams | hybrid-beams}`（L260）
- 原文：
  ```yang
  choice beamforming-type {
    case frequency { container frequency-domain-beams { when "../rt-bf-weights-update-support = 'true'";
        uses beamforming-parameters; uses cf:bf-compression-details;
        list additional-compression-method-supported { uses cf:bf-compression-details; ... } }
      description "Set of parameters valid for O-RU, that supports beamforming in frequency domain."; }
    case time { container time-domain-beams { when ...; uses beamforming-parameters; uses granularity-parameters;
        uses cf:bf-compression-details; list additional-compression-method-supported {...} }
      description "Set of parameters valid for O-RU, that supports beamforming in time domain."; }
    case hybrid { container hybrid-beams { when ...; uses beamforming-parameters; uses granularity-parameters;
        uses cf:bf-compression-details; list additional-compression-method-supported {...} }
      description "Set of parameters valid for O-RU, that supports hybrid beamforming - in both time and frequency domain."; }
    description "This value indicates beamforming type supported by O-RU"; }
  ```
- 說明：頻域（數位，每個 PRB 可用不同權重）、時域（類比，每個 symbol 或 slot 一組權重）、混合。對應 TR 38.901／38.817 的 digital / analog / hybrid beamforming 架構。

### [ORAN-B06] beamforming-parameters：max-number-of-beam-ids、initial-beam-id
- 出處：Y-BF : `.../{frequency-domain-beams|time-domain-beams|hybrid-beams}/max-number-of-beam-ids`、`/initial-beam-id`（grouping beamforming-parameters，L174）
- 原文：max-number-of-beam-ids：`uint16 { range "min .. 32767"; } mandatory true;` "Maximum number of supported Beam ID assigned to domain beamforming control"；initial-beam-id：`uint16 { range "min .. 32767"; } mandatory true;` "First Beam ID that can be used for addressing of domain beams"
- 型別：uint16 0..32767；mandatory
- 說明：每個 domain（頻域、時域或混合）可用的 beamId 區段 = [initial-beam-id, initial-beam-id + max − 1]（此公式為推論）。

### [ORAN-B07] granularity-parameters：frequency-granularity、time-granularity
- 出處：Y-BF : `.../time-domain-beams|hybrid-beams/frequency-granularity`、`/time-granularity`（L197）
- 原文：frequency-granularity：`enumeration { CC "Frequency granularity: per Component Carrier"; BAND "Frequency granularity: per band"; } mandatory true;` description "Supported time granularity of time-domain beamforming."（原文描述如此，與欄位名稱不一致）；time-granularity：`enumeration { SLOT "Time granularity: per slot"; SYMBOL "Time granularity: per symbol"; } mandatory true;` "Supported time granularity of time-domain beamforming."
- 說明：類比 beam 的切換顆粒度，可為每個 CC 或每個頻段，時間上可為每個 slot 或每個 symbol。

### [ORAN-B08] bf-compression-details（Y-CF）
- 出處：Y-CF : grouping bf-compression-details（L298），在 ORAN-B05 的三個 container 中被 uses
- 原文：`iq-bitwidth` uint8 "Bitwidth to be used in compression"；`compression-type` compression-type-def mandatory "Compression type that O-DU wants to be supported"；`bitwidth` uint8 deprecated；`compression-method` bf-compression-method-def "Compression method which can be supported by the beamforming"。typedef bf-compression-method-def（L147）的列舉值包含 NO_COMPRESSION, BLOCK_FLOATING_POINT, BLOCK_SCALING, U_LAW, BEAMSPACE, ...（其餘列舉值請見原檔 L147 之後）
- 說明：C-plane 權重（SE1）的壓縮格式。

### [ORAN-B09] static-properties/number-of-beams
- 出處：Y-BF : `/beamforming-config/capabilities-groups/static-properties/number-of-beams`（L320）
- 原文：`type uint16;` "This value indicates the max number of beam patterns O-RU can generate and apply to the signal of each O-RU port (both DL and UL). This value is equivalent to the maximum number of used beam IDs."
- 型別：uint16
- 說明：每個 O-RU port 可套用的 beam pattern 數量上限，約等於 GoB 的碼本大小（預定義 beam 數）。對應 3GPP：沒有直接對應；SSB beam 數 L_max（TS 38.213 §4.1）是 cell 層級的另一個概念，兩者不應混用。

### [ORAN-B10] static-properties/p-dash
- 出處：Y-BF : `/beamforming-config/capabilities-groups/static-properties/p-dash`（L327；revision 2022-12-05 新增）
- 原文：`type uint16;` "This parameters specifies the dimesionality of the time-domain beamforming operation. Refer to description of parameter p' in clause 12.4.3.4.2 of CUS-Plane specification. This parameter is required to define the size of time-domain beamforming vector in case of hybrid/time-domain beamforming is supported by O-RU"
- 說明：時域（類比）BF 向量的維度 p'。間接出處：CUS §12.4.3.4.2。

### [ORAN-B11] beam-information/number-of-beamforming-properties、beamforming-properties/beam-id
- 出處：Y-BF : `/beamforming-config/capabilities-groups/beam-information/number-of-beamforming-properties`（L456）、`/beam-information/beamforming-properties`（L462）、`.../beamforming-properties/beam-id`（grouping beamforming-properties-element，L392）
- 原文：number-of-beamforming-properties：`uint16` "This parameter indicates the number of beamFormingProperties entries."；list 描述："Array for the beamforming properties at O-RU. These parameters can be used by the beamforming control by the NETCONF client. 'numberOfBeamformingProperties' indicates the size of the array."（key beam-id）；container 描述 "Beam information which exposes beamforming related O-RU capabilities."；beam-id：`uint16 { range "min .. 32767"; }` "This value indicates the beam ID whose beamforming properties are described in the container."
- 說明：以 beam 為單位列出屬性表（GoB 中每個 beam 的描述）。

### [ORAN-B12] beamforming-property/beam-type
- 出處：Y-BF : `.../beamforming-properties/beamforming-property/beam-type`（grouping beamforming-property，L340）
- 原文：`enumeration { enum COARSE { description "the beam-id corresponds to a coarse beam"; } enum FINE { description "the beam-id corresponds to a fine beam"; } }` "This value indicates the beam resolution."
- 說明：粗、細兩層 beam。概念上接近 3GPP 的 P1（寬 SSB beam）與 P2/P3（窄 CSI-RS beam）beam management 流程（TR 38.802 §6.1.6.1），此對應屬推論。

### [ORAN-B13] beamforming-property/beam-group-id
- 出處：Y-BF : `.../beamforming-property/beam-group-id`（L353）
- 原文：`type uint16;` "Beams with same beamGroupsID can be transmitted simultaneously."
- 說明：同一 group 的 beam 可以同時發射，可作為 MU-MIMO／多 beam 同時排程的限制條件。

### [ORAN-B14] coarse-fine-beam-relation（deprecated）/ coarse-fine-beam-capability-based-relation
- 出處：Y-BF : `.../beamforming-property/coarse-fine-beam-relation`（L359）、`.../coarse-fine-beam-capability-based-relation`（L374）
- 原文：前者：`leaf-list { type beam-reference; status deprecated; description "List of related coarse/fine beam."; }`；後者：`leaf-list { type beam-capabilities-reference; description "List of related coarse/fine beam."; }`。typedef beam-capabilities-reference 為 leafref "/o-ran-bf:beamforming-config/o-ran-bf:capabilities-groups/o-ran-bf:beam-information/o-ran-bf:beamforming-properties/o-ran-bf:beam-id"
- 說明：記錄粗 beam 與其下細 beam 的階層關係，屬於 GoB 的樹狀結構。

### [ORAN-B15] neighbour-beams（deprecated）/ neighbour-beams-capability-based
- 出處：Y-BF : `.../beamforming-property/neighbour-beams`（L366）、`.../neighbour-beams-capability-based`（L380）
- 原文：兩者描述都是 "A list of neighbour beams which might restrict co-scheduling due to interference."；前者 status deprecated
- 說明：同時排程時會互相干擾的鄰近 beam，是 MU-MIMO 配對的約束條件。

### [ORAN-B16] beamforming-supported-type：beamforming-trough-attributes-supported、beamforming-trough-ue-channel-info-supported
- 出處：Y-BF : `/beamforming-config/beamforming-trough-attributes-supported`（L514）、`/beamforming-config/beamforming-trough-ue-channel-info-supported`（L522）
- 原文：前者：`type boolean; config false;` "Informs if beamforming can be controlled providing attributes to O-RU (like angles, beamwidth)."；後者：`type boolean; config false;` "Informs if beamforming can be controlled by UE information."
- 說明：分別代表以屬性控制 BF（角度、波束寬度，對應 CUS SE2，「beam attribute based」方法）與以 UE 通道資訊控制 BF（ST5/ST6，「channel-information based」方法）。SE 編號與方法編號的對應在本 YANG 中**未明寫**，屬推論，需以 CUS 規範確認。

### [ORAN-B17] ue-specific-beamforming（ST6 能力）
- 出處：Y-BF : `/beamforming-config/ue-specific-beamforming`（L558）
- 原文：`presence "Indicates that the O-RU supports optional Section Type '6' Fields (used for sending channel information for a specific UE)"; config false;` 描述 "Information related to support by the O-RU of Section Type 6 for signalling UE-specific channel information to the O-RU"
  - `max-number-of-ues`：`uint8; status deprecated;` "... Leaf is deprecated as it only enabled a maximum of 255 UEs to be supported, compared with ST5 and ST6 which supports a 15 bit value. NETCONF client instead uses max-number-ues-15bit schema node"
  - `max-number-of-ues-15bit`：`uint16 { range "1 .. 32767"; }` "Indicates the maximum number of UE -specific channel information data sets supported by the O-RU, It is restricted to 15 bits value because of the 15bits ueId field in ST5 and ST6"
  - `channel-information-compression-method-supported`（if-feature CHANNEL-INFORMATION-COMPRESSION）：leaf-list cf:ci-compression-method-def "list of channel information compression methods supported by the O-RU"
  - `dynamic-channel-information-compression-supported`（同一 feature）：boolean "Informs if dynamic channel information compression supported by the O-RU, if its value is true, the compression method and IQ bit width can be dynamic in ciCompHdr; if its value is false, only static configuration compression configuration is supported, and ciCompHdr shall be set to a fixed value corresponding to the static configured compression method and IQ bit width."
- 說明：O-RU 端可依 UE 通道（例如 SRS 通道估計）計算預編碼，屬 CAT-B 的 reciprocity BF。對應 TS 38.214 的 non-codebook／TDD 互易性。

### [ORAN-B18] operational-properties（if-feature MODIFY-BF-CONFIG）
- 出處：Y-BF : `/beamforming-config/operational-properties/{number-of-writeable-beamforming-files, update-bf-non-delete, persistent-bf-files}`（L474、L606）
- 原文：number-of-writeable-beamforming-files：`uint8 { range "1 .. max"; } mandatory true;` "This leaf indicates the maximum number of writable beamforming files containing beamweights and/or attributes that the O-RU can store, taking into account the maximum number of beam-IDs as defined by 3GPP TS38.214 v15.x.x"；update-bf-non-delete：`boolean default false;` "When set to TRUE, indicates that an O-RU supports the capability to apply the modified beamforming weight information by using RPC activate-beamforming-weight without deletion of tx-array-carriers and rx-array-carriers in advance, i.e., to a deactivated carrier"；persistent-bf-files：`boolean default false;` "When set to TRUE, indicates that the O-RU supports the capability to store the modified beamforming weight information file in the reset persistent memory"；container 描述 "properties for dynamic beam weight/attribute support"
- 說明：GoB 權重檔（beam pattern table）是否可以上傳並替換，這是 Non-RT 層級 GoB 最佳化（WG1-001）在 M-plane 上的落地點。

### [ORAN-B19] RPC activate-beamforming-config / activate-beamforming-config-by-capability-group
- 出處：Y-BF : `rpc activate-beamforming-config`（L849）、`rpc activate-beamforming-config-by-capability-group`（L890）；兩者皆 if-feature MODIFY-BF-CONFIG
- 原文：描述為 "RPC to activate beamforming config information by indicating the file stored in the folder o-ran/beamforming in advance"；input：`beamforming-config-file`（string, mandatory, "file name stored in o-ran/beamforming folder is indicated"），再加上 `band-number`（前者）或 `capabilities-group`（後者，mandatory）；output：`status` enum {ACCEPTED "O-RU has accepted the beamforming weight/attribute file", REJECTED "O-RU has rejected the beamforming weight/attribute file. The O-RU should then use the default beamforming file."}，以及 `error-message`（when REJECTED）"Detailed error Message when the status is rejected, e.g., because new beam forming file is attempted to be applied to a carrier which is still active, or the beam-id does not exist."
- 說明：切換 GoB 權重或屬性檔。檔案格式在 MP 規範的附錄中定義，本地**未找到**。
- 相關 notification：`beamforming-information-update`（uses band-num）"this notification indicates that the beamforming properties are updated for particular band"；`capability-group-beamforming-information-update`（uses cap-group）。

### [ORAN-B20] beam-tilt：predefined-beam-tilt-offset（RPC 輸入）
- 出處：Y-BF : `rpc modify-predefined-beam-tilt-offset / input / predefined-beam-tilt-offset`（grouping beam-tilt-configuration，L615；if-feature BEAM-TILT）
- 原文：`list predefined-beam-tilt-offset { key capabilities-group; description "Configuration of the predefined-beam-tilt-offset per capabilities-group"; ...`
  - `capabilities-group`：leafref（require-instance false），mandatory
  - `elevation-tilt-offset-angle`：`int16 { range "-90..90"; } units degrees; default 0;` "Value 0 represents the default service area of the predefined-beams in elevation domain, i.e. no tilt offset. Values smaller than 0 represents an up-shift of the default service area towards the zenith (i.e., corresponding to a decrease in zenith angle) and values larger than 0 represent a down-shift of the default service area away from the zenith (i.e., corresponding to an increase in zenith angle). If the value is greater than the maximum supported angle, then the maximum angle is used for configuration. If the value is less than the minimum supported angle, then the minimum angle is used for configuration. The actual angle used is (angle DIV granularity) * granularity. Any O-RU which is reset using the o-ran-operations:reset RPC shall reset its offset angle to its default value."
  - `azimuth-tilt-offset-angle`：`int16 { range "-90..90"; } units degrees; default 0;` "Value 0 represents the default service area of the predefined-beams in azimuth domain, i.e., no tile offset. Azimuth tilt offset angle, represents counter-clockwise rotation around z-axis. I.e., assuming view from the UE (observation of the O-RU from the front), value larger than 0 and smaller than 0 respectively represent right-shifted and left-shifted of the default service area in azimuth domain. If the value is greater than the maximum supported angle, ...（後文同 elevation）"
  - output：`status` ACCEPTED / REJECTED（"O-RU has accepted the predefind beamtilt offset configuration" / "O-RU has rejected the predefind beamtilt offset configuration."）；`error-message` "... e.g., used when 'run-time-tilt-offset-supported' is FALSE and the NETCONF client is attempting to modify the beam tilt on a band where one or more array-carriers are still ACTIVE."
- 型別：int16，-90..90，單位 degrees，default 0；實際套用的角度 = (angle DIV granularity) × granularity
- 說明：**這是 O-RU 端唯一的 GoB 整體數位傾角與方位角偏移控制**，約等於 WG1 cell shaping 中的「Digital tilt」（WG1-012），也近似於 TR 38.901 的 electrical downtilt θ_etilt 的整體偏移（對應關係屬推論）。正值代表往下傾（zenith 角變大）。

### [ORAN-B21] beam-tilt-state：predefined-beam-tilt-offset-information
- 出處：Y-BF : `/beamforming-config/beam-tilt/predefined-beam-tilt-offset-information`（grouping beam-tilt-state，L683）
- 原文：`key capabilities-group; config false;` "Information which exposes predefined-beam-tilt-offset related O-RU capabilities."
  - `elevation-tilt-offset-granularity`：`uint8 { range "0..30"; } units Degrees; mandatory true;` "Indication of the supported granularity for the predefined-beam-tilt-offset in elevation domain. Value 0 represents that the O-RU doesn't support the predefined-beam-tilt-offset in elevation domain."
  - `azimuth-tilt-offset-granularity`：`uint8 { range "0..30"; } units Degrees; mandatory true;`（描述同上，改為 azimuth，並寫 "Value '0' represents that the O-RU doesn't support ..."）
  - `minimum-supported-elevation-tilt-offset`：`int16 { range "-90..0"; } units Degrees; mandatory true;` "The minimum value which can be configured for 'elevation-tilt-offset-angle'."
  - `maximum-supported-elevation-tilt-offset`：`int16 { range "0..90"; } ...` "The maximum value which can be configured for 'elevation-tilt-offset-angle'."
  - `minimum-supported-azimuth-tilt-offset`：`int16 { range "-90..0"; }`；`maximum-supported-azimuth-tilt-offset`：`int16 { range "0..90"; }`（描述比照 elevation）
  - `run-time-tilt-offset-supported`：`boolean; mandatory true;` "If 'run-time-tilt-offset-supported' is FALSE, changing the values in 'predefined-beam-tilt-offset' for a specific band shall be allowed only if all 'tx-array-carriers' and 'rx-array-carriers' corresponding to the band are INACTIVE."
- 說明：傾角調整的能力範圍與步進；可作為 WG1「Supported coverage combinations」類輸入的一部分（此對應屬推論）。

### [ORAN-B22] beam-tilt-report：predefined-beam-tilt-state
- 出處：Y-BF : `/beamforming-config/beam-tilt/predefined-beam-tilt-state`（L784）；notification `predefined-beam-tilt-offset-complete` 也會帶出這組資料（L980，描述 "this notification indicates that the re-generation of the predefined beams is completed"）
- 原文：`elevation-tilt-offset-angle` 與 `azimuth-tilt-offset-angle`：`int16 { range "-90..90"; } units Degrees; mandatory true;`，描述為 "Value 'zero' represents the default service area of the predefined-beams in elevation domain. ..."（方位角描述同 ORAN-B20）
- 說明：目前實際生效的傾角偏移。

---

## C. o-ran-module-cap（Y-MC）

> `/module-capability/ru-capabilities`（config false，uses ru-capabilities）；`/module-capability/band-capabilities`（list key band-number，config false）。

### [ORAN-M01] ru-supported-category
- 出處：Y-MC : `/module-capability/ru-capabilities/ru-supported-category`
- 原文：`enumeration { enum CAT_A { description "Informs that precoding is not supported in O-RU"; } enum CAT_B { description "Informs that precoding is supported in O-RU"; } }` "Informs about which category O-RU supports"
- 型別：enum {CAT_A, CAT_B}（注意是底線，不是連字號）
- 說明：CAT-B 代表預編碼在 O-RU 內執行（layer→port 映射在 RU 端），對應 TS 38.214 precoding 所在的節點。

### [ORAN-M02] number-of-ru-ports（deprecated）
- 出處：Y-MC : `/module-capability/ru-capabilities/number-of-ru-ports`
- 原文：`type uint8; status deprecated;` "Assuming all endpoints support time-managed traffic AND non-time-managed traffic (choice is as per configuration) - the number of O-RU ports is the product of number of spatial streams (leaf number-of-spatial-streams) and number of numerologies O-RU supports. For example, if the number of spatial streams is 4 then the number of O-RU ports is 8 when PUSCH and PRACH are processed in the different endpoints. In case there are specific endpoints that support non-time-managed traffic only - the number of O-RU ports calculated with above mentioned equation is extended by number of endpoints supporting only non-time-managed traffic."
- 說明：已由 M03/M04 取代。

### [ORAN-M03] number-of-ru-ports-ul
- 出處：Y-MC : `/module-capability/ru-capabilities/number-of-ru-ports-ul`
- 原文：`type uint8;` "Assuming all endpoints support time-managed traffic AND non-time-managed traffic AND static channel configuration (choice is as per configuration) - the upper bound of the number of O-RU ports for uplink which is derived from number of spatial streams or layers (leaf number-of-spatial-streams) and associated numerology O-RU supports. Numerology capability per spatial stream or layer is based on eaxc id description in CUS specification section entitled 'ecpriRtcid / ecpriPcid (real time control data / IQ data transfer message series identifier)' For example, if O-RU supports for each of 'N' spatial streams or layers 'M' numerologies (as it applies to PUSCH and PRACH), number of ports is N * M. In case there are specific endpoints that support non-time-managed traffic only - the number of O-RU ports calculated is extended by number of endpoints supporting only non-time-managed traffic. Additionally, if there are specific endpoints that support static channel configuration only(e.g. static PRACH) - the number of O-RU ports calculated above is further extended by number of endpoints supporting static channel configuration only."
- 型別：uint8
- 說明：UL O-RU port 數的上限 = N（空間串流）× M（numerology），再加上特殊端點數。O-RU port 約等於 eAxC 端點數。

### [ORAN-M04] number-of-ru-ports-dl
- 出處：Y-MC : `/module-capability/ru-capabilities/number-of-ru-ports-dl`
- 原文：`type uint8;` "Assuming all endpoints support time-managed traffic AND non-time-managed traffic (choice is as per configuration) - the upper bound of the number of O-RU ports for downlink which is derived from number of spatial streams or layers (leaf number-of-spatial-streams) and associated numerology O-RU supports. Numerology capability per spatial stream or layer is based on eaxc id description in CUS specification section entitled 'ecpriRtcid / ecpriPcid (real time control data / IQ data transfer message series identifier)' For example, if O-RU supports for each of 'N' spatial streams or layers 'M' numerologies, number of ports is N * M. In case there are specific endpoints that support non-time-managed traffic only. - the number of O-RU ports calculated with above mentioned equation is extended by number of endpoints supporting only non-time-managed traffic"
- 說明：DL port 上限。

### [ORAN-M05] number-of-spatial-streams
- 出處：Y-MC : `/module-capability/ru-capabilities/number-of-spatial-streams`
- 原文：`type uint8;` "This value indicates the number of spatial streams supported at O-RU for DL and UL. For DL, it is same as the number of antenna ports specified in 3GPP TS38.214, Section 'UE procedure for reporting channel state information (CSI)' and 3GPP TS36.213, Section 'UE procedure for reporting Channel State Information (CSI)'."
- 型別：uint8
- 說明：**YANG 原文明確寫出的 3GPP 對應**：DL 空間串流數 = TS 38.214 CSI 章節中的天線埠數（即 CSI-RS port 數，例如 Type I codebook 的 N1·N2·2）。

### [ORAN-M06] max-num-bands
- 出處：Y-MC : `/module-capability/ru-capabilities/max-num-bands`
- 原文：`type uint16;` "maximum number of bands supported by the O-RU"

### [ORAN-M07] format-of-iq-sample 中與 BF 相關的欄位
- 出處：Y-MC : `/module-capability/ru-capabilities/format-of-iq-sample/{regularization-factor-se-supported, st6-4byte-alignment-required, se6-rb-bit-supported, ...}`（grouping format-of-iq-sample）
- 原文：regularization-factor-se-supported：`boolean` "Informs if regularizationFactor in section type 5 is supported(true) or not(false)"；st6-4byte-alignment-required：`boolean default false` "An optional flag indicating whether O-RU requires 4-byte aligned Section Type 6 or not. ... as described in clause 'Elements for the C-Plane Protocol' of the CUS-Plane specification."；se6-rb-bit-supported：`boolean default false` "If this leaf node has a value 'true', then O-DU may use the 'rb' bit, ... Refer 'SE 6: Non-contiguous PRB allocation in time and frequency domain' requirement #3 of the CUS-Plane specification."；其他欄位：dynamic-compression-supported、realtime-variable-bit-width-supported、compression-method-supported（list, uses cf:compression-details, 另含 fs-offset）、variable-bit-width-per-channel-supported、syminc-supported、little-endian-supported
- 說明：與 ST5/ST6（UE 通道資訊預編碼）相關的能力。

### [ORAN-M08] max-power-per-pa-antenna / min-power-per-pa-antenna（deprecated）
- 出處：Y-MC : `/module-capability/ru-capabilities/max-power-per-pa-antenna`、`/min-power-per-pa-antenna`
- 原文：`type decimal64{ fraction-digits 4; } status deprecated;` "This value indicates Maximum Power per PA per antenna. Value unit is dBm. The parameter is deprecated. min-gain and max-gain define constraints related to TX power budget, as defined in CUS-Plane, clause 8.1.3.3."（min 版本的描述相同，只是改為 "Minimum"）
- 型別：dBm（decimal64/4）；deprecated
- 說明：改由 ORAN-022 取代。band-capabilities 下另有 `max-power-per-antenna`、`min-power-per-antenna`（per band，同樣 deprecated，描述相同但改為 "per band per antenna"）。

### [ORAN-M09] fronthaul-split-option
- 出處：Y-MC : `/module-capability/ru-capabilities/fronthaul-split-option`
- 原文：`type uint8 { range "7"; }` "This value indicates the Fronthaul Split Option, i.e., 2 or 7 in this release."
- 型別：uint8，range 只允許 7（描述寫「2 or 7」，但 range 限定為 7）
- 說明：7-2x split，對應 3GPP TR 38.801 的 Option 7。

### [ORAN-M10] eaxcid-grouping-capabilities
- 出處：Y-MC : `/module-capability/ru-capabilities/eaxcid-grouping-capabilities/*`（if-feature EAXC-ID-GROUP-SUPPORTED）
- 原文：`max-num-tx-eaxc-id-groups` uint8 "Maximum number of configurable tx-eaxc-id-group supported by O-RU."；`max-num-tx-eaxc-ids-per-group` uint8 "Maximum number of eAxC IDs per tx-eaxc-id-group supported by O-RU, where each group is a union of the 'member-tx-eaxc-id's and a 'representative-tx-eaxc-id'."；`max-num-rx-eaxc-id-groups` uint8 "the maximum number of groups with the eAxC IDs those are assigned to low-level-rx-links."；`max-num-rx-eaxc-ids-per-group` uint8 "Maximum number of eAxC IDs per rx-eaxc-id-group supported by O-RU, ..."
- 說明：SE10 分組能力（見 ORAN-040）。

### [ORAN-M11] coupling-methods、support-only-unique-ecpri-seqid-per-eaxc、nack-supported、ext-ant-delay-capability
- 出處：Y-MC : `/module-capability/ru-capabilities/...`
- 原文（摘錄）：coupling-via-frequency-and-time "Coupling via frequency and time; see methods of coupling of C-plane and U-plane in CUS-Plane specification"；support-only-unique-ecpri-seqid-per-eaxc `boolean default false` "Parameter informs if O-RU expects unique eCPRI sequence id for eAxC_IDs serving for UL and DL for the same Component Carrier. ..."；nack-supported "... If O-RU reports supporting section extension for ACK/NACK request (section extension 22) and ACK/NACK feedback (section type 8), ..."；ext-ant-delay-capability enum {PER-ARRAY-CARRIER, PER-ARRAY, PER-O-RU}
- 說明：與 eAxC 相關的附帶能力。

### [ORAN-M20] band-capabilities/band-number、support-for-dl、support-for-ul
- 出處：Y-MC : `/module-capability/band-capabilities/band-number`，以及 `/module-capability/band-capabilities/{max-supported-frequency-dl, min-supported-frequency-dl, max-supported-bandwidth-dl, max-num-carriers-dl, max-carrier-bandwidth-dl, min-carrier-bandwidth-dl, supported-technology-dl}` 與對應的 `*-ul`（grouping support-for-dl / support-for-ul；tx-arrays/capabilities 與 rx-arrays/capabilities 也重用這兩個 grouping）
- 原文：band-number `uint16` "Band number"；max-supported-frequency-dl `uint64` "This value indicates Maximum supported downlink frequency. Value unit is Hz."；min-supported-frequency-dl "This value indicates Minimum supported downlink frequency. Value unit is Hz."；max-supported-bandwidth-dl "This value indicates Maximum total downlink bandwidth in module. Value unit is Hz."；max-num-carriers-dl `uint32` "This value indicates Maximum number of downlink carriers in module."；max-carrier-bandwidth-dl "This value indicates Maximum bandwidth per downlink carrier. Value unit is Hz."；min-carrier-bandwidth-dl "This value indicates Minimum bandwidth per downlink carrier. Value unit is Hz."；supported-technology-dl `leaf-list enum {LTE, NR, DSS_LTE_NR}; min-elements 1;` "This list provides information regarding technologies supported in DL path"（UL 版本對稱，只是改為 uplink）
- 型別：Hz（uint64）
- 說明：頻段與頻寬能力，對應 TS 38.104 的 operating band。

### [ORAN-M21] band-capabilities/max-num-component-carriers、max-num-sectors
- 出處：Y-MC : `/module-capability/band-capabilities/max-num-component-carriers`、`/max-num-sectors`
- 原文：`uint8` "maximum number of component carriers supported by the O-RU. This parameter is the cumulative value of 'max-num-carriers-dl' and 'max-num-carriers-ul'"；`uint8` "maximum number of sectors supported by the O-RU"
- 說明：sector 對應 eAxC 中的 BandSector_ID（見 ORAN-030）。

### [ORAN-M22] band-capabilities/codebook-configuration_ng / _n1 / _n2（deprecated）
- 出處：Y-MC : `/module-capability/band-capabilities/codebook-configuration_ng|_n1|_n2`
- 原文：`type uint8; status deprecated;` "This parameter informs the precoder codebook_ng that are used for precoding. Parameter deprecated since antenna topology already specified in [tr]x-array"（_n1、_n2 的描述相同，只換參數名）
- 說明：**這是 TS 38.214 Type I/II codebook 的 (N_g, N1, N2) 在 O-RAN 中的直接對應**。已 deprecated，改由 tx-array 的 (M, N, P) 推導。

### [ORAN-M23] 未找到的項目
- `beamforming` 相關 capability 在 module-cap 中**未找到**（beamforming 能力位於 o-ran-beamforming；ru-capabilities 中只有 CAT_A/CAT_B 一項）。
- `compression` 在 module-cap 中只有 format-of-iq-sample（見 ORAN-M07）。

---

## D. o-ran-processing-element（Y-PE，只摘要 eAxC 相關部分）

### [ORAN-P01] processing-elements（頂層）
- 出處：Y-PE : `/processing-elements`（L466 附近）
- 原文：`container processing-elements { description "a model defining the mapping between transport flows and arbitrary O-RAN processing elements. A processing element may be then defined for handling connectivity or delay procedures, or defined with a corresponding eaxcid for CU plane operations"; uses pe-group; }`
- 說明：處理單元（processing element）是 eAxC 流量的傳輸通道。low-level-tx/rx-links 透過 `processing-element` leafref 指向 `/processing-elements/ru-elements/name`（見 ORAN-039）。整體對應鏈為：eAxC(endpoint) → link → ru-element → VLAN/MAC 或 UDP/IP。

### [ORAN-P02] ru-elements、transport-session-type、enhanced-uplane-mapping
- 出處：Y-PE : `/processing-elements/ru-elements`（L371，key name，string length 1..255）；`transport-session-type` enum {ETH-INTERFACE "VLAN based CUS Transport ", UDPIP-INTERFACE, ALIASMAC-INTERFACE, SHARED-CELL-ETH-INTERFACE "VLAN based CUS Transport used for Shared Cell scenario"}，default ETH-INTERFACE；`enhanced-uplane-mapping/uplane-mapping`（key up-marking-name）"a mapping between up-link name and o-ran-interfaces:up-marking-name"
- 說明：只與傳輸層有關，不影響天線模型。YANG 內**沒有**「eAxC → ru-element」的直接欄位，這個對應關係由 uplane-conf 的 link 負責。

---

## E. E2SM-CCC（WG3）交叉對照（O-RU 天線資訊經 E2 回報）

### [ORAN-C01] O-RUInfo（REPORT）
- 出處：E2SM-CCC R005-v07.00 §8.8.2.8
- 原文：`oruUserPlaneConfiguration` REPORT, FALSE, 9.3.33："The oruUserPlaneConfiguration is a list of user plane configurations supported by the O-RU from the o-ran-uplane-conf.yang module."；`oruCapabilities` REPORT, FALSE, 9.3.37："The oruCapabilities contains O-RU capability related information supported by the O-RU from the o-ran-module-cap.yang module."
- 說明：Near-RT RIC 可透過 E2 取得 tx/rx-array 幾何資訊（唯讀，不可寫）。

### [ORAN-C02] txArrayList / rxArrayList
- 出處：E2SM-CCC §9.3.34 / §9.3.35
- 原文（摘錄）："Corresponds to the list "tx-arrays" in the o-ran-uplane-conf.yang YANG module provided by the O-RU. See O-RAN WG4.MP [10] clause 15.2.4"；欄位與型別：tName M STRING；tNumberOfRows M INTEGER (1..65535) "... – M. See O-RAN WG4.CUS [9] clause 12.5.3"；tNumberOfColumns M INTEGER (1..65535) "– N"；tNumberOfArrayLayers M INTEGER (1..255) "– Q"；tHorizontalSpacing / tVerticalSpacing O NUMBER "... See O-RAN WG4.CUS [9] clause 12.5.3. Represented as decimal 64 with 5-digits fraction."；tAzimuthAngle O NUMBER "Azimuth angle - j (phi) - in degrees, counter-clockwise rotation around z-axis. ... See O-RAN WG4.CUS [9] clause 12.5.2."；tZenithAngle O NUMBER "Zenith angle - q (theta) ... See O-RAN WG4.CUS [9] clause 12.5.2."；tLeftmostBottomArrayElementPosition O "Position of centre of the leftmost, bottom element of array in O-RU coordinate system. See O-RAN WG4.CUS [9] clause 12.5.3"（tXAxis/tYAxis/tZAxis）；tPolarizationList M 1..<maxnoofTxPolarizations>（tPolarizationIndex INTEGER (0..255) "Index (p) identifying the polarization out of the total P polarizations"；tPolarizationType ENUMERATED (MINUS_45, ZERO, PLUS_45, PLUS_90)）；tBandNumber M INTEGER (1..1024)；tMaxGain M；tMinGain O；tIndependentPowerBudget M BOOLEAN。Range bound：maxnoofTxArrays = 256；maxnoofTxPolarizations = 2。rx 版本欄位以 r 開頭，結構對稱。
- 說明：**這份文件給出了 YANG 陣列欄位所依據的 CUS 章節（§12.5.2 座標與角度、§12.5.3 陣列幾何），以及 MP §15.2.4**，並提供了 YANG 沒有寫出的數值上下界。

### [ORAN-C03] O-NESPolicy：antennaMaskName / antennaMask（TRX control）
- 出處：E2SM-CCC §8.8.2.6（屬性表）、§9.3.23、§9.3.24
- 原文：antennaMaskName："corresponds to the selected "mask-name" in the list, "supported-trx-control-masks", provided by O-RU, see clause 20.3.1.2 of [10]."；antennaMask："Antenna mask contains an octet string mask value indicating which antenna element to be switched off/on, see clause 16.2 of [9]. It is used if supported antenna mask list is not reported by the O-RU, which means the O-RU supports any mask value (see 20.3.1.2 of [10])."（REPORT, CONTROL；writable TRUE）
- 說明：唯一可經由 E2 寫入的 O-RU 天線元件開關控制，用於節能（NES）。CUS §16.2、MP §20.3.1.2 需人工確認。
- 查無項目：E2SM-CCC 中 **未找到** O-RU tilt、MIMO mode、SSB beam 配置、beamwidth 的可配置參數。SSB 只有 cell 層級的 ssbFrequency、ssbPeriodicity、ssbSubCarrierSpacing、ssbOffset、ssbDuration（都引用 TS 28.541 §4.4.1），與 beam 無關。

---

## F. WG1 Use Cases（O-RAN.WG1.TS.Use-Cases-Detailed-Specification-R005-v20.00）

### [WG1-001] §4.6 Massive MIMO optimization — 共通背景
- 出處：WG1 §4.6、§4.6.1.1
- 原文（摘錄）："Grid of Beams (GoB) with the corresponding beam sweeping has been introduced to allow beamforming the control channels used during initial access ... The codebook and the GoB define the span of the beams, namely the horizontal and vertical aperture in which beamforming is supported, and therefore the coverage area and the shape of the cell. ... different vendors can have different implementations in terms of the number of beams, the horizontal/vertical beam widths, azimuth and elevation range, to achieve the desired coverage." 另有："the coverage area itself is defined by (vendor specific) fixed mMIMO system parameters such as the azimuth and elevation angle range, or the GoB parameters. Hence ... the mMIMO cell can suffer from e.g. 1) High inter-cell interference 2) Unbalanced traffic between neighboring cells 3) Low performance of cell edge users 4) Poor handover performance"
- 說明：列出的控制維度有 beam 數、水平與垂直波束寬度、方位角與仰角範圍、GoB 參數。

### [WG1-002] §4.6.2.1 / §4.6.3.1 Non-RT massive MIMO GoB beam forming optimization — 控制參數（輸出）
- 出處：WG1 §4.6.2.1 1)c)、§4.6.3.1 Table 4.6.3.1-1 Step 3
- 原文："The massive MIMO configurable parameters includes horizontal beam width, vertical beam width, beam azimuth and downtilt, maximum and average transmitted power per beam/direction as specified in 3GPP TS 28.541 [5]."；Step 3 (M)："Upon trigger from Non-RT RIC with the optimized beam parameters, SMO configures the parameters towards the RAN via O1 interface. The relevant parameters can include: a) horizontal beam width, vertical beam width, beam azimuth and downtilt b) maximum and average transmitted power per beam/direction"
- 輸出參數清單：horizontal beam width、vertical beam width、beam azimuth、downtilt、每個 beam 或方向的最大與平均發射功率
- 介面：O1（SMO → RAN）；執行者：Non-RT RIC（rApp）；流程圖中有 "UE-specific Beam ID"（輸入）、"Beam Pattern Configuration Table"、"Updated M-MIMO Configuration"
- 說明：3GPP 對應為 TS 28.541 的 NRM（例如 CommonBeamformingFunction / Beam IOC；具體 IOC 名稱需到 28.541 確認，WG1 未寫出）。在 O-RU 端可落地的部分是 ORAN-B18/B19（權重檔）與 ORAN-B20（tilt 偏移）。

### [WG1-003] §4.6.4.1 Non-RT GoB optimization — 所需資料（輸入）
- 出處：WG1 §4.6.4.1
- 原文："1) Environment data: Cell site information (location), inter-site distance, BS system configuration, (e.g. operating frequency, bandwidth, frame structure, transmit power, default beam weight configuration); complete set of massive MIMO configurations, i.e., horizontal beamwidth adjustable range, vertical beamwidth adjustable range, azimuth angle adjustable range, elevation angle adjustable range. 2) From RAN to SMO and/or Near-RT RIC a) Measurement reports with RSRP/RSRQ/CQI/SINR per beam information for the UEs in cells of interest; the time granularity of data collection shall be configurable and satisfy the requirement of the AI/ML model. b) Network KPIs: e.g., cell downlink/uplink traffic load, RRC connection attempts, average RRC connected UE, maximum RRC connected UE, average active connections (downlink/uplink), DL/UL throughput, DL/UL spectral efficiency, NI (Noise Interference); beam resource usage (transmitted power per beam/directions and associated PRB usage), beam based handover and beam failure statistics 3) From application to SMO a) User location related information, e.g., GPS coordinates ..."
- 資料清單：
  - 環境與配置：站點位置、站距、工作頻率、頻寬、訊框結構、發射功率、預設 beam 權重配置；可調範圍包括水平與垂直波束寬度、方位角、仰角
  - 量測：每個 beam 的 RSRP/RSRQ/CQI/SINR（時間顆粒度可設定）
  - KPI：DL/UL 負載、RRC 連線嘗試與連線 UE 數、throughput、頻譜效率（SE）、NI、每個 beam 的功率與 PRB 使用量、beam-based 換手與 beam failure 統計
  - 應用層：UE GPS 位置

### [WG1-004] §4.6.2.2 / §4.6.3.2 / §4.6.4.2 Near-RT beam-based mobility robustness optimization（bMRO）
- 出處：WG1 §4.6.2.2、Table 4.6.3.2-1、§4.6.3.2 後段說明、§4.6.4.2
- 原文（摘錄）：SMO 需 "Send GoB beam pattern related information (beam pattern configuration, beam pattern configuration list, beam pattern configuration switch timing/condition, beam pattern identifier etc.) to the Near-RT RIC."；Near-RT RIC 需 "predict the optimal configuration of mobility parameters (e.g., beam individual offsets for beam mobility) for each cell/beam pair ..." 並 "Send the optimal beam mobility parameter configurations to E2 nodes as specified in 3GPP TS 28.541 [5]."；E2 nodes 需 "Apply L3 beam mobility parameter configuration ..."；Pre-condition："Active Grid-of-Beams beam pattern is defined."；Step 3："Near-RT RIC configures optimized parameters in E2 nodes (e.g., bCIO-s)."；§4.6.4.2："1) Beam-specific handover related KPMs, as specified in 3GPP TS 28.552 [6] and in 3GPP TS 28.622 [8] from E2 nodes, similar to: a) Too early handovers b) Too late handovers c) Attempted handovers d) Successful handovers e) Failed handovers f) The time granularity is an integer multiple of 1 second as specified in 3GPP TS 28.622 [8]. 2) The beam pattern information supplied externally is not defined in the present document."
- 輸入：GoB beam pattern 資訊（配置、配置清單、切換時機與條件、pattern ID）；每個 beam 的 HO KPM（過早、過晚、嘗試、成功、失敗；顆粒度為 1 秒的整數倍）
- 輸出：beam individual offset（bCIO），屬 L3 beam mobility 參數
- 說明：bCIO 約等於 3GPP 的 beam 層級 CIO，屬 TS 28.541 NRM，詳細欄位需人工確認。WG1 明寫「beam pattern information ... is not defined in the present document」。

### [WG1-005] §4.6.2.3 / §4.6.3.3 / §4.6.4.3 NR cell shaping optimization
- 出處：WG1 §4.6.1（cell shaping 背景）、§4.6.2.3、Table 4.6.3.3-1、Table 4.6.4.3-1
- 原文（背景）："Cell shaping ... allows the adjustment of cell footprint by adjusting by configuring the vertical and horizontal coverage width of the common beam into combinations to describe a valid supported shape as driven by O-RU capabilities and then refined through further adjustments with the tilt." 以及 "Cell shaping optimizes the shape of the cell and/or sector carrier via different configuration combinations of electrical tilt and/or digital tilt, horizontally and/or vertically, as well as through adjustments of the beam width."；§4.6.2.3 1)b："Configure the optimized cell shape per cell level for MIMO beam parameters and tilt via the O1 interface."；Step 8-12 (M)："The SMO communicates the new O1 settings to the O-DU and O-RU as driven by hybrid or hierarchical management options - via O1 and M-plane."
- Table 4.6.4.3-1（Req ID | 類別 | 參數 | Source | 介面 | Reference；類別皆為 Network Configuration Management；空白代表原表未填）：

| Req | 參數 | Source | 介面 | Reference |
|---|---|---|---|---|
| Req-4.6.001 | Node Id: Node identification | O-DU | O1 | 3GPP TS 28.541 [5], clause 4.3.1, gnbId + gnbDUId |
| Req-4.6.002 | Sector Id: Sector identification | O-DU | O1 | （空） |
| Req-4.6.003 | Cell Id: Cell identification | O-DU | O1 | 3GPP TS 28.541 [5], clauses 4.3.1, 4.3.5, gnbId + cellLocalId |
| Req-4.6.004 | Antenna Latitude | O-DU | O1 | （空） |
| Req-4.6.005 | Antenna Longitude | O-DU | O1 | （空） |
| Req-4.6.006 | Antenna Azimuth (direction) | O-DU | O1 | （空） |
| Req-4.6.007 | Antenna Elevation (Height) | O-DU | O1 | 3GPP TS 28.662 [41], clause 4.3.2 |
| Req-4.6.008 | Antenna – Remote Electrical Tilt subunit mapping | O-DU/O-RU | O1 | （空） |
| Req-4.6.009 | Antenna – Remote Electrical Tilt subunit mapping | O-DU/O-RU | OFH MP | O-RAN.WG4.MP [28], clause 14.4.2 |
| Req-4.6.010 | Remote Electrical Tilt per antenna | O-DU/O-RU | O1 | 3GPP TS 28.662 [41], clause 4.3.2, retTiltValue |
| Req-4.6.011 | Remote Electrical Tilt per antenna | O-DU/O-RU | OFH MP | O-RAN.WG4.MP [28], clause 14.4.3 and AISG specifications |
| Req-4.6.012 | Digital tilt per antenna | O-DU/O-RU | O1 | （空） |
| Req-4.6.013 | Digital tilt per antenna | O-DU/O-RU | OFH MP | O-RAN.WG4.MP [28], clause 14.4.3 and AISG specifications |
| Req-4.6.014 | Broadcast and Cellular Broadcast (BCB) per cell level | O-DU | O1 | 3GPP TS 28.541 [5], clause 4.3.1, gnbId + gnbDUId |
| Req-4.6.015 | Horizontal coverage width | O-DU | O1 | （空） |
| Req-4.6.016 | Horizontal coverage width | O-DU | OFH MP | （空） |
| Req-4.6.017 | Vertical coverage width | O-DU | O1 | （空） |
| Req-4.6.018 | Vertical coverage width | O-DU | OFH MP | （空） |
| Req-4.6.019 | Supported coverage combinations of vertical / horizontal options (radio specific capabilities) | O-RU | O1 | （空） |
| Req-4.6.020 | 同上 | O-RU | OFH MP | （空） |
| Req-4.6.021 | Digital tilt per carrier | O-DU/O-RU | O1 | （空） |
| Req-4.6.022 | Digital tilt per carrier | O-DU/O-RU | OFH MP | （空） |

- 說明：MP §14.4.2/§14.4.3 屬於 ALD/RET（AISG）章節，本地的 YANG 子集沒有收錄 o-ran-ald 模組，因此**未查證**。「Digital tilt per carrier」最接近的本地 YANG 是 ORAN-B20（predefined-beam-tilt-offset，以 capabilities-group 為單位，不是以 carrier 為單位）。WG1 中「Horizontal/Vertical coverage width」的 OFH MP 欄位在本地 YANG **未找到**對應 leaf。

### [WG1-006] §4.14 Massive SU/MU-MIMO grouping optimization
- 出處：WG1 §4.14
- 原文："Void"
- 說明：R005-v20.00 中此 use case 已刪除，沒有內容可抽取。

### [WG1-007] §4.22 MU-MIMO optimization（Near-RT）
- 出處：WG1 §4.22.1–§4.22.4、Table 4.22.3.1-1
- 原文（摘錄）："an application in the Near-RT RIC that can use information collected from the E2 nodes to calculate and send to the E2 nodes user selections and applicable precoding coefficients in a near real time loop."；§4.22.2："d) Use the retrieved information to select the UEs to be spatially multiplexed per frequency and time resources and for each selection calculate the relevant MCS and precoder coefficients ... e) Send the recommended UE selections with their resource assignments, MCS, and precoding coefficients to the E2 nodes."；E2 nodes 需 "b) Apply the configurations received from the Near-RT RIC for DL channel estimation reporting and UL SRS transmissions c) Apply MU-MIMO parameters following Near-RT RIC recommendations (while handling time critical events separately)."；Step 9 (M)："Near-RT RIC sends optimized MU-MIMO parameters (UE selections with their resource assignments, MCS, and precoding coefficients) to E2 nodes."；§4.22.4："1) Cell configuration information (e.g., frequency and BW, FDD/TDD, SCS, UL-DL configuration) 2) List of connected UEs 3) UE connection updates (setup, release, handover) 4) UE RRC state changes (connected, inactive, idle) 5) UL channel information (e.g., SRS, ACK/NACK counts) 6) DL channel information (e.g., CQI, RI, PMI, ACK/NACK counts) 7) DL PDCP and RLC buffer status and UL BSR"
- 輸入：cell 配置、UE 清單與狀態、UL 通道（SRS、ACK/NACK）、DL 通道（CQI/RI/PMI、ACK/NACK）、緩衝區狀態
- 控制與輸出：UE 分組（每個時頻資源）、資源指派、MCS、預編碼係數；DL CSI 回報配置與 UL SRS/DMRS 配置
- 3GPP 對應：CQI/RI/PMI 見 TS 38.214 §5.2；SRS 見 TS 38.211 §6.4.1.4 與 TS 38.214 §6.2.1。O-RU 端的落地點是 ST5/ST6 或 SE（見 ORAN-B17），但 WG1 沒有寫出。

### [WG1-008] §4.21.3.2 / §4.21.4.2 RF channel reconfiguration（TRx control）for network energy savings
- 出處：WG1 §4.21.3.2、Table 4.21.3.2.1-1、§4.21.4.2.1（Table 4.21.4.2.1-1/-2）、§4.21.4.2.2
- 原文（摘錄）："This feature aims at reducing power consumption of O-RU by reconfiguring the RF channels [27], [28]. ... As example, one can switch off 32 out of 64 RF channels in digital massive MIMO architecture or reduce the number of layers and/or number of multi-user scheduled UEs in a hybrid architecture. The O-RU reconfiguration can be performed using the open fronthaul M-plane from E2 node or SMO."；Step（M）："E2 node sends appropriate commands to the O-RU via open fronthaul M-plane or C-plane to configure (activate) RF channel reconfiguration (TRx control) feature to the specific O-RU, i.e., O-DU configures a specific antenna mask on O-RU." 引用 "O-RAN.WG4.MP [28], clause 20.3.2.3; O-RAN.WG4.TS.CUS.0-R004 [51], clauses 7.4.6, 16, 16.1, and 16.2"；Step 9："O-RU adjusts its antenna array configuration(s) based on the E2 node provided configuration."；Exceptions："O-RU/E2 node reports failure or resource is ineligible (e.g., all SSB/PRACH beams masked)."
- 與 MIMO 相關的 Req（摘錄 Table 4.21.4.2.1-1/-2）：
  - Req-4.21.4.2.019 / .020：PDSCH/PUSCH PRB Usage per cell for MIMO — O-DU — 3GPP TS 28.552 [6] clause 5.1.1.2.11 / 5.1.1.2.12 — O1
  - Req-4.21.4.2.023：Intra-NRCell SSB Beam switch Measurement — O-DU — TS 28.552 clause 5.1.1.21 — O1
  - Req-4.21.4.2.026：SSB beam related Measurement — Beam (O-DU) — TS 28.552 clauses 5.1.1.28 — O1
  - Req-4.21.4.2.027：Transmit power utilization measurements — NRCellDU (O-DU) — TS 28.552 clauses 5.1.1.29 — O1
  - Req-4.21.4.2.028：SS-RSRQ distribution per SSB — Beam (O-DU) — TS 28.552 clauses 5.1.1.31.2 — O1
  - Req-4.21.4.2.029：MU-MIMO related measurements — NRCellDU (O-DU) — TS 28.552 clauses 5.1.1.30 — O1
  - Req-4.21.4.2.014：Site location and orientation per cell（siteLatitude, siteLongitude, Azimuth / orientation）— O-DU — TS 28.623 [40] — O1
  - Req-4.21.4.2.034：Supported TRx Control masks (antenna masks) (capabilities) by O-RU (TRx Control via Open Fronthaul C-Plane) — O-RU — O-RAN.WG4.MP [28], clause 20.3.1.2 — Open FH M-plane
  - Req-4.21.4.2.035：同上（via Open Fronthaul M-Plane）— O-RAN.WG4.MP [28], clause 20.3.2.2
  - Req-4.21.4.2.008–.010：TRx Control activation / activation failure / Cumulative Activity time — O-DU — O-RAN.WG10.TS.O1PMeas [48], A.4.13.14–16 — O1
  - Req-4.21.4.2.103 / .104（輸出）：NES configuration changes（M-Plane）MP §20.3.2.3；（C-Plane）MP §20.3.1.3 與 CUS.0-R004 §7.4.6、§16、§16.1、§16.2
  - Rel. 4.21.4.2.2（rApp/xApp 方案）的 Req-4.21.4.2.201–235 內容與上表相同，並註明 "NOTE: There is no O1 output."
- 說明：antenna mask 約等於關閉部分 TRXCU 或陣列元件，會改變實際的有效 (M, N, P)。E2 側的控制見 ORAN-C03。

### [WG1-009] SSB beam 配置
- 出處：WG1 全文搜尋 "SSB beam"
- 結果：只有 KPM 輸入（WG1-008 的 Req .023/.026/.028）與例外條件 "all SSB/PRACH beams masked"。**未找到** SSB beam 數量、方向、寬度等**可配置控制參數**的 use case 定義。

---

## G. PAPER（**非規範性**）— AI_Powered_O-RAN_MIMO_Optimization.pdf

> 性質：共 11 頁的圖片投影片，頁尾標示「Gemini Notebook」，副標題為「WG1 技術規範解析」。內容是 WG1 §4.6、§4.21、§4.22 的二次整理，**不能作為規範出處**，只能作為交叉檢查。PDF 沒有文字層，以下由頁面影像判讀。

### [PAPER-001] Massive MIMO（cell shaping）動態調整參數（p.4）
- 原文（影像文字）：「動態調整參數：• 水平與垂直波束寬度 • 電子與數位傾角 • 波束方位角 • 每波束最大發射功率」
- 對應規範：WG1-002、WG1-005

### [PAPER-002] 矩陣對比表：關鍵調整參數（p.8）
- 原文：Massive MIMO（小區塑形）的關鍵參數為「波束寬度、電子傾角、方位角、GoB」，控制介面為 O1，由 Non-RT RIC / SMO 執行，時間尺度為「秒級至分鐘級」；MU-MIMO（移動性最佳化）的關鍵參數為「用戶選擇/分組、通道預測、預編碼係數 (Precoding)」，控制介面為 E2，由 Near-RT RIC 執行，時間尺度為「十毫秒至百毫秒級」
- 對應規範：WG1-002、WG1-007。**時間尺度數值在 WG1 原文中未找到**，應視為投影片作者的詮釋。

### [PAPER-003] 關鍵數據（p.6）
- 原文：環境與系統設定包括「基站位置、站間距離；運行頻率、頻寬；完整 MIMO 配置能力：水平/垂直波束寬度可調範圍、方位角/仰角範圍」；RAN KPI 包括「每波束的 RSRP / RSRQ / CQI / SINR；波束資源使用率 (發射功率與 PRB 使用量)；波束換手失敗統計；雜訊干擾 (NI)」；應用層包括「用戶位置資訊 (如 GPS 座標)」
- 對應規範：WG1-003

### [PAPER-004] 節能降階（p.9）
- 原文：「數位 Massive MIMO：系統可動態將 64 條射頻通道 (64T64R) 關閉一半，降階至 32 條通道運作。」「混合架構：減少空間層數 (Layers) 或減少排程的 MU-MIMO 用戶數。」
- 對應規範：WG1-008（「64T64R」這個寫法是投影片自行加上的，WG1 原文只寫 "32 out of 64 RF channels"）

### [PAPER-005] 干擾管理（p.10）
- 原文：「透過 E2 介面，Near-RT RIC 直接監測特定的 mMIMO 波束」、「動態調整調變與編碼策略 (MCS)，引導波束避開干擾源」
- 對應規範：本次抽取範圍內（§4.6/§4.21/§4.22）**未找到**直接對應的條文，可能來自 WG1 其他章節，未查證。

---

## H. 需要人工從 specifications.o-ran.org 下載才能完整確認的章節

**O-RAN.WG4.CUS（Control, User and Synchronization Plane Specification）**
（YANG 未標明 CUS 版本；CCC 引用的是 CUS.0-R003-v15.00；WG1 引用的是 CUS.0-R004）

| # | 章節 / 條文名 | 由誰引用 | 用途 |
|---|---|---|---|
| 1 | §12.5.2（陣列座標系、azimuth/zenith 定義） | CCC 9.3.34/9.3.35 | ORAN-016/017 的角度定義與 TR 38.901 的換算 |
| 2 | §12.5.3（陣列幾何 M/N/Q、間距、左下元件位置、極化 p/P） | CCC 9.3.34/9.3.35 | ORAN-011～019 |
| 3 | 「Identification and Ordering of Array Elements」 | Y-UP L800 | ORAN-021 的元件編號規則 |
| 4 | Polarisation index（"See CUS-plane"） | Y-UP L766 | ORAN-019 |
| 5 | §12.4.3.4.2（參數 p'） | Y-BF L331 | ORAN-B10 |
| 6 | §12.4.3.4.4（ST4 TIME_DOMAIN_BEAM_CONFIG） | Y-UP L459 | ORAN-004 |
| 7 | 「Weight-based dynamic beamforming」 | Y-UP L2849/L3035 | ORAN-034 |
| 8 | §8.1.3.3（TX power budget / gain 限制） | Y-UP L3206；Y-MC L419/431/800/812 | ORAN-022/071/M08 |
| 9 | §8.2.2（U-plane only DL mode） | Y-UP L448 | ORAN-003 |
| 10 | 「ecpriRtcid / ecpriPcid」（eAxC 位元定義） | Y-MC（number-of-ru-ports-ul/dl） | ORAN-030、M03/M04 |
| 11 | 「methods of coupling of C-plane and U-plane」 | Y-UP L596；Y-MC coupling-methods | ORAN-M11 |
| 12 | 「frameStructure (frame structure)」 | Y-UP L844/L2232 | endpoint 能力 |
| 13 | §7.5.2.17（ST4 cmd scope） | Y-UP L1970 | ORAN-051 |
| 14 | §7.7.23.1（SE 相關，max-mcscaleremask-per-prb） | Y-UP L1265 | ORAN-050 |
| 15 | §7.8.2.1.2「Limits of number of PRB ranges」 | Y-UP L1368 | endpoint-prb-capacity |
| 16 | 「Elements for the C-Plane Protocol」（ST6 4-byte alignment） | Y-MC L420 | ORAN-M07 |
| 17 | 「SE 6: Non-contiguous PRB allocation in time and frequency domain」 requirement #3 | Y-MC L292 | ORAN-M07 |
| 18 | freqOffset、cp-length 相關條文（"See CUS-plane"） | Y-UP L870–899、L3772 | scs-config |
| 19 | §7.4.6、§16、§16.1、§16.2（TRx control / antenna mask） | WG1 §4.21.3.2（CUS.0-R004）；CCC 9.3.24（§16.2） | ORAN-C03、WG1-008 |
| 20 | **Section Type 1/3/4/5/6 與 Section Extension 1、2、3、10、19、20 等的完整定義（beamforming method：weight-based SE1、attribute-based SE2、DL precoding SE3、ST5/ST6 channel-info-based，以及 SE19/SE20）** | Y-UP supported-section-extensions（只寫 uint8，沒有對應表） | ORAN-050、B16、B17。本地 YANG **未提供** SE 編號與方法的對應 |
| 21 | Shared cell / Section Extension 10 cascade 說明 | Y-UP L3592；o-ran-shared-cell L264/L296/L843 | ORAN-040 |

**O-RAN.WG4.MP（Management Plane Specification）**

| # | 章節 | 由誰引用 | 用途 |
|---|---|---|---|
| 22 | §15.2.4（tx-arrays / rx-arrays） | CCC 9.3.34/9.3.35 | ORAN-010～024 |
| 23 | §14.4.2、§14.4.3（ALD / RET subunit mapping 與 tilt，AISG） | WG1 Table 4.6.4.3-1 | WG1-005；本地沒有 o-ran-ald 系列 YANG |
| 24 | §20.3.1.2、§20.3.1.3、§20.3.2.2、§20.3.2.3、§20.4.1（TRx control mask、sleep modes） | WG1 §4.21；CCC | WG1-008、ORAN-C03 |
| 25 | §9.1.3「Modify state」 | Y-HW L233 | 硬體狀態 |
| 26 | §4.8（array carrier 的 delete MO） | Y-UP L985 | ORAN-070 |
| 27 | 「Table 5: Centre Bandwidth Calculation」 | Y-UP L951 | ORAN-070 |
| 28 | Beamforming 權重/屬性檔格式（o-ran/beamforming 資料夾）所在的附錄；以及 beam tilt 相關章節 | Y-BF RPC | ORAN-B18～B22 |
| 29 | 比 2022-12-05 更新的 WG4 M-plane YANG（查證 `static-beams`、`pattern-idx`、SE19/SE20、beamforming method 列舉是否存在於新版） | 需求中提到但本地未找到 | ORAN-B* 補完 |
| 30 | Clause 11 與 Table A.1-1（fault-id 31） | Y-UP L1273/1373 | 能力超限告警 |

**其他（非 O-RAN 網站，但抽取過程中被引用）**：3GPP TS 28.541（§4.3.1、§4.3.5、§4.3.6、§4.4.1，beam 相關 NRM 與 bCIO）、TS 28.552（§5.1.1.2.11/12、§5.1.1.21、§5.1.1.28、§5.1.1.29、§5.1.1.30、§5.1.1.31.2）、TS 28.622、TS 28.662 §4.3.2（retTiltValue）、TS 28.623、AISG 規範。
