# 07 — O-RAN WG4 M-Plane R005 v21.01：RU 天線 / Beamforming / MIMO 規則抽取

> 本檔依據 v21.01 更新 05_oran.md 的 A–D 節（05 使用 2022-12-05 版 YANG）。
> 規則：每條都附出處，原文逐字保留；找不到的標「未找到」；不做臆測。

## 0. 來源

| 代號 | 檔案 | 版本 |
|---|---|---|
| MP | `specs/txt/O-RAN.WG4.TS.MP.0-R005-v21.01.txt`（由 `specs/oran/O-RAN.WG4.TS.MP.0-R005-v21.01.docx` 轉成文字，沒有頁碼，引用時寫章節號或表號） | O-RAN.WG4.TS.MP.0-R005-v21.01 |
| UP | `specs/oran/yang-v21.01/O-RAN.WG4.TS.MP-YANGs-R005-v21.01/RU Specific Models/Operations/o-ran-uplane-conf.yang` | revision 2026-05-07（version 21.0.0） |
| BF | `.../RU Specific Models/Radio/o-ran-beamforming.yang` | revision 2025-04-14（version 17.1.0） |
| MC | `.../RU Specific Models/Radio/o-ran-module-cap.yang` | revision 2026-05-07（version 21.0.0） |
| AC | `.../RU Specific Models/Radio/o-ran-antenna-calibration.yang` | revision 2024-04-15（version 7.2.0） |
| ALD | `.../Common Models/Operations/o-ran-ald.yang` | revision 2021-12-01（version 1.2.0） |
| ALDP | `.../Common Models/Interfaces/o-ran-ald-port.yang` | revision 2025-04-14（version 13.2.0） |
| FEAT | `.../Common Models/System/o-ran-wg4-features.yang` | revision 2026-05-07 |
| HW | `.../Common Models/System/o-ran-hardware.yang` | — |
| TXA | `.../RU Specific Models/Operations/o-ran-pm-tx-antenna-stats.yang`（submodule，由 o-ran-performance-management 引入） | revision 2025-12-22（version 20.0.0） |
| OLD | `specs/oran-yang/*@2022-12-05.yang`（05_oran.md 使用的版本） | 2022-12-05 |

- 路徑記法：`模組 : /data-node/...`，省略 prefix；`Lnnn` 是 v21.01 YANG 檔中的行號。
- **章節號更正**：v21.01 中 §15.2.4 是「General configuration scenario」，不是天線陣列幾何；Beamforming 在 **§15.4**；Antenna calibration 在 **§15.5**；ALD 在 **§14.4**；O-RU connectors 在 **§14.6**；節能在 **§20**（§20.3.x 存在）。MP 本文**沒有**專門描述陣列幾何的章節，幾何只定義在 UP YANG 的 `grouping parameters`，MP §15.4.5 則指向該處（見 MP-100）。

---

## 1. 05_oran.md 標為「未找到」項目的重新查證（v21.01）

### [MP-001] static-beams
- 出處：UP、BF、MC 全文，以及 MP 全文（grep `static.beam`）
- 結果：**未找到**。不存在名為 `static-beams` 的 leaf/list。與「預定義波束」最接近的是 BF `beam-information/beamforming-properties`（MP-044），MP §15.4.2 稱為 "pre-defined beams"；BF L572 另有 description 文字 "the static beamforming related information"（container `static-properties`）。

### [MP-002] pattern-idx
- 出處：UP、BF、MP 全文（grep `pattern-id`）
- 結果：**未找到** `pattern-idx`。只找到不相關的 `tdd-pattern-id`、`prach-pattern-id`、`srs-pattern-id`。UP `/user-plane-configuration/endpoint-types/supported-section-types/section-type`（L3217 附近）的 description 中有文字 "from a beam with one pattern id"，但沒有對應的 leaf。

### [MP-003] SE19 capability
- 出處：UP、BF、MC、FEAT、MP 全文（grep `SE-?19|extension 19`）
- 結果：**未找到** SE19 專屬的 capability leaf 或 feature。依照 M-plane 的設計，O-RU 支援哪些 SE 一律由 `endpoint-types/supported-section-types/supported-section-extensions`（uint8 leaf-list，MP-060）回報，可以填入 19。SE19 本身的語意需到 CUS 規範查證。

### [MP-004] SE20 capability（v21.01 新增，2022-12-05 沒有）
- 出處：FEAT : `feature SE20-MULTI-SD-PUNC-PATTERN-SUPPORT`（L581）；UP L3467 `se-20-multi-sd-punc-pattern-suported`、L4752 `low-level-tx-endpoints/se-20-multi-sd-punc-pattern-enabled-tx`、L5060 `low-level-rx-endpoints/se-20-multi-sd-punc-pattern-enabled-rx`、L3916 `se-20-full-prb-puncture-with-different-section-id-supported`
- 原文（FEAT）："Feature to indicate O-RU support for handling multiple section description puncturing pattern in Section Extension 20 per endpoint."
- 原文（UP L3472–3476）："This flag is applicable for 'static-low-level-[tr]x-endpoints' which support Section Estension 20 (SE-20). The flag associated with each puncturing pattern in SE-20. ... - Value of the flag advertised as 'TRUE' indicates O-RU supports handling of 'multiSDScope' field in SE-20."（原文拼字即為 "suported"、"Estension"）
- 型別：boolean（能力值為 config false，`-enabled-tx/-rx` 為 O-DU 設定）
- 說明：SE20 是 puncturing（打孔）pattern。能力回報加上 O-DU 開關，用來決定是否使用 `multiSDScope`。UP revision 2024-08-12 "3) add support for se-20-multi-sd-punc-pattern"；revision 2025-08-11 "1) Added se-20-full-prb-puncture-with-different-section-id-supported."。3GPP 對應：無（屬 fronthaul 參數）。

### [MP-005] beamforming method 列舉（v21.01 新增，2022-12-05 沒有）
- 出處：UP : `typedef beamforming-method-type`（L536）；使用處：`/user-plane-configuration/endpoint-bf-profile-group/supported-bf-methods`（L6540）、`/user-plane-configuration/low-level-tx-endpoints/bf-methods`（L4834）、`.../low-level-rx-endpoints/bf-methods`（L5259）
- 原文：
  - `NOBF` "No beamforming."
  - `PDBF` "Predefined-beam beamforming."
  - `WDBF` "Weight-based dynamic beamforming (based on real-time-updated weights)."
  - `ABBF` "Attribute-based dynamic beamforming (based on real-time-updated beam attributes)."
  - `CIBF` "Channel-information-based beamforming."
  - `DMRS_BF_EQ` "DMRS-based beamforming with equalization."
  - `DMRS_BF_NEQ` "DMRS-based beamforming without equalization."
- 型別：enumeration，共 7 個值
- 說明：用來回報每個 endpoint 可同時使用的 BF 方法組合，以及各組合對應的 delay profile。相關 feature 為 `BF-DELAY-PROFILE`（"Feature to indicate O-RU support for beamforming list and delay profiles(s) per endpoint."）與 `SELECTED-BF-METHOD-CONFIGURATION`。UP revision 2024-04-15 "2) add support for for beamforming list and delay profiles(s) per endpoint."（原文重複 "for"）。MP §15.2.4 step 4 規定了 NETCONF Client 的使用流程（MP-061）。
- 補充：05 所說的「method 1–4」在 v21.01 **未找到**編號式列舉，實際上是以上的名稱式列舉。

### [MP-006] downlink-radiation-offset
- 出處：UP、MP 全文（grep `radiation`）
- 結果：**未找到**。實際存在的是 `tx-array-carriers/downlink-radio-frame-offset`（UP L5520），屬於時序參數，見 MP-083。

---

## 2. o-ran-uplane-conf（UP）— 天線陣列

### [MP-010] grouping parameters（tx-arrays 與 rx-arrays 共用的幾何參數）
- 出處：UP : `grouping parameters`（L1392），由 `/user-plane-configuration/tx-arrays`（L5805）與 `/user-plane-configuration/rx-arrays`（L5942）以 `uses parameters` 引用；兩個 list 都是 `config false`，key 為 `name`。

| leaf | 型別 / 單位 | 原文 |
|---|---|---|
| name | string, mandatory | "Unique name of array antenna" |
| number-of-rows | uint16, mandatory | "Number of rows array elements are shaped into - M" |
| number-of-columns | uint16, mandatory | "Number of columns array elements are shaped into - N" |
| number-of-array-layers | uint8, mandatory | "Number of array layers array elements are shaped into - Q" |
| horizontal-spacing | decimal64 fd5, units Meter | "Average distance between centres of nearby AE in horizontal direction (in array coordinates system)" |
| vertical-spacing | decimal64 fd5, units Meter | "Average distance between centres of nearby AE in vertical direction (in array coordinates system)" |
| normal-vector-direction/azimuth-angle | decimal64 fd4, units Degrees | "Azimuth angle, counter-clockwise rotation around z-axis. Value 'zero' points to broad-side, value '90' points to y-axis" |
| normal-vector-direction/zenith-angle | decimal64 fd4, units Degrees | "Zenith angle, counter-clockwise rotation around y-axis. Value 'zero' points to zenith, value '90' points to horizon" |
| leftmost-bottom-array-element-position/{x,y,z} | decimal64 fd4, units Meter | "X dimension of position of leftmost, bottom array element"（y、z 的原文同理） |
| polarisations (list, key p, min 1 / max 2) | p: uint8；polarisation: `polarisation_type` | "List of supported polarisations.For O-RUs that use external antennas, the reported external antenna polarisations are expected to follow vendor deployment guidelines." |
| band-number | leafref → `/module-capability/band-capabilities/band-number`, mandatory | "This parameter informing which frequency band particular antenna array is serving for. Intended use is to deal with multiband solutions." |
| related-o-ru-connectors (list, key name) / array-element-id | name: leafref 到 hw component，限定 class 為 `O-RU-ANTENNA-CONNECTOR`；array-element-id: uint16 leaf-list | "Identifiers of array element(s) related to specific O-RU connector. Allowed values and semantic - as per CUS-Plane spec, clause 'Identification and Ordering of Array Elements'" |

- `typedef polarisation_type`（L507）：`MINUS_45`、`ZERO`、`PLUS_45`、`PLUS_90`
- 說明：陣列大小為 M×N×Q，加上間距、法向量與參考元素位置，對應 CUS §12.5.2 的陣列座標系。3GPP 對應：TR 38.901 §7.3 天線模型的 (M,N,P) 與 d_H、d_V（僅概念對應，O-RAN 未直接引用）。與 2022-12-05 相比，只有 polarisations 的 description 有修改（UP revision 2024-12-23 "1) clarified polarization list with external antennas"），欄位結構不變。

### [MP-011] tx-arrays 專屬欄位
- 出處：UP : `/user-plane-configuration/tx-arrays/`（L5805–5940）
- `min-gain`：decimal64 fd4，dB — "Min gain of RF path linked with array element (maximum over elements of array) or array layers"
- `max-gain`：decimal64 fd4，dB，mandatory — "Max gain of RF path linked with array element (minimum over elements of array) or array layers"
- `independent-power-budget`：boolean，mandatory — "If true then every element of array has own, power budget independent from power budget of other elements. Else all elements of array that are at same row and column and have same polarisation share power budget"
- `capabilities`（list）：`uses mcap:support-for-dl`，加上 `supported-energy-saving-capabilities-dl/{trx-control-capability-info, asm-capability-info}`（**v21.01 新增**，見 MP-121）
- `supported-max-power-level`（list key index，if-feature MAX-POWER-CONTROL，**新增**）：index uint8（"index = 0 means that the power reduction is not used for a tx-array."）；`array-max-power-reduction` decimal64 fd4 dB（"A leaf indicates the reduced upper power compared to the rated maximum power per tx-array for this index."）
- `max-power-level-used`：uint8（**新增**）
- `mplane-trx-control-txarr-capability-info`（**新增**）見 MP-122
- `null-steering-capability`（**新增**）見 MP-130

### [MP-012] rx-arrays 專屬欄位
- 出處：UP : `/user-plane-configuration/rx-arrays/`（L5942）
- `gain-correction-range/max`、`/min`：decimal64 fd4，dB，mandatory — "Array gain correction factor - maximum allowed value" / "... - minimum allowed value"
- `capabilities`：`uses mcap:support-for-ul`，加上 `supported-energy-saving-capabilities-ul`（**新增**）
- `mplane-trx-control-rxarr-capability-info`（**新增**）

### [MP-013] relations（陣列元件關係）
- 出處：UP : `/user-plane-configuration/relations`（L6003，config false，key entity uint16）
- 結構：`array1`、`array2`（choice tx-array-name / rx-array-name）；`types/relation-type` 的列舉為 `SHARED`、`COALOCATED`（原文拼字）；`pairs/element-array1`、`element-array2` 為 uint16。
- 原文："Structure describing relations between array elements"
- 與 2022-12-05 相同。

---

## 3. UP — eAxC、endpoint、beam 能力

### [MP-050] grouping eaxc
- 出處：UP : `grouping eaxc`（L1337）；MP §15.2.2
- 欄位：`o-du-port-bitmask`、`band-sector-bitmask`、`ccid-bitmask`、`ru-port-bitmask`、`eaxc-id`（L1384），全部是 uint16 且 mandatory。
- 原文（UP）："One eAxC identifier (eAxC ID) comprises a band and sector identifier (BandSector_ID), a component-carrier identifier (CC_ID) and a spatial stream identifier (RU_Port_ID). In this version of the specification, one eAxC contains only one spatial stream (i.e. one beam per subcarrier) at a time."
- 原文（MP §15.2.2）："In this version of the O-RAN WG4 specification, the length of eAxC_ID is constant and equal to 16 bits." 以及 "each parameter uses consecutive bits." "each parameter can occupy 0-16 bits." "An O-RU shall be configured with a single eAxC_ID format."
- 原文（MP §15.2.3）："The NETCONF Client shall assign unique values to the "eaxc_id" addresses to all low-level-rx-endpoint elements and low-level-tx-endpoint elements, within the O-RU when operating in the same direction (Tx or Rx)"
- 說明：RU_Port_ID 對應空間流（layer / 天線埠）。與 2022-12-05 相同。

### [MP-060] endpoint-types/supported-section-types
- 出處：UP : `/user-plane-configuration/endpoint-types/supported-section-types`（L3217；endpoint-types 為 config false，key id）
- 原文：section-type（uint8）"This parameter determines the characteristics of U-plane data to be transferred or received from a beam with one pattern id."；supported-section-extensions（uint8 leaf-list）"This parameter provides the extension types supported by the O-RU which provides additional parameters specific to the subject data extension"
- 說明：所有 SE（包括 SE19、SE20 等）的支援情況都經由這個 leaf-list 回報（見 MP-003）。

### [MP-061] endpoint-bf-profile-group / bf-profile-group / configured-bf-profile-id / bf-methods（新增）
- 出處：UP L6528 `/user-plane-configuration/endpoint-bf-profile-group`（config false，key bf-profile-id uint16；`supported-bf-methods` 為 leaf-list，min-elements 1；`supported-delay-profile` 為 leafref 到 o-ran-delay-management 的 `non-default-ru-delay-profile`）；L3488 `endpoint-types/bf-profile-group`；L4822/L5130 `low-level-[tr]x-endpoints/configured-bf-profile-id`；L4834/L5259 `bf-methods`
- 原文（supported-bf-methods）："Beamforming methods can be supported simultaneously."
- 原文（MP §15.2.4 step 4）："Each bf-profile-id is used to identify an endpoint-bf-profile-group which indicates a list of beamforming methods that can be used simultaneously, and delay profiles associated with each list of beamforming methods."
- 原文（MP §15.2.4）："If the NETCONF Client does not configure configured-bf-profile-id per endpoint, the O-RU shall use the beamforming method determined by section type supported by endpoint and default delay profile."
- 條件：if-feature BF-DELAY-PROFILE；`bf-methods` 另外需要 SELECTED-BF-METHOD-CONFIGURATION。

### [MP-062] grouping endpoint-beam-capacity
- 出處：UP : `grouping endpoint-beam-capacity`（L2118）
- 欄位：`max-beams-per-symbol`、`max-beams-per-slot`、`max-total-beamids-per-symbol`（**新增**）、`max-total-beamids-per-slot`（**新增**）、`max-beam-updates-per-slot`、`max-beam-updates-per-symbol`，以上皆為 uint16，range "min .. 32767"；另有 `*-multiple-beamid-tables` 四個 uint32 欄位（**新增**，if-feature MULTIPLE-BEAMID-TABLES-SUPPORTED）。
- 原文（max-beams-per-symbol）："Max number of different beamId values within one symbol that can be processed by endpoint or processed collectively by group of endpoints sharing capacity If the parameter is absent or if value 0 is reported for the parameter, then the endpoint does not support beamforming operation."
- 原文（MP §15.4.1）："Endpoints capable of either BF or non-BF operation are distinguished by the capabilities exposed by endpoint-types in endpoint-beam-capacity grouping."
- revision：UP 2024-04-15 "8) Changed description of max-beams-per-symbol/slot, so they refer to 'different beamId values' instead of 'beams'"、"9) added new leafs called max-beams-per-symbol-multiple-beamid-tables and max-beams-per-slot-multiple-beamid-tables"；UP 2024-08-12 "5) add Endpoint beam capacity counter for same or diff beamId values"。

### [MP-063] energy-sharing-group-id（新增）
- 出處：UP L4435 / L4565 `static-low-level-[tr]x-endpoints/energy-sharing-group-id`（uint8 leaf-list）；MP §20.3.3.2
- 原文（MP）："Multiple endpoints that have the same energy-sharing-group-id value signifies that these endpoints share common underlying HW components."
- 說明：用於資料層控制節能（MP-124）。

---

## 4. UP — array carriers 與 general-config

### [MP-080] tx-array-carriers/gain
- 出處：UP L5496
- 型別：decimal64 fd4，dB，mandatory
- 原文："Transmission gain in dB. Value applicable to each array element carrier belonging to array carrier. The value of transmission gain shall meet the constraints defined in CUS-Plane, clause 8.1.3.3."

### [MP-081] tx-array-carriers/carrier-max-power-reduction（新增）
- 出處：UP L5509，if-feature MAX-POWER-CONTROL
- 型別：decimal64 fd4，range "0..max"，dB
- 原文："The value represents the power reduction per tx-array-carrier."

### [MP-082] configured-tx/rx-beamId-table-index（新增）
- 出處：UP L1845（tx）、L1977（rx），if-feature MULTIPLE-BEAMID-TABLES-SUPPORTED，型別 uint8
- 原文："The value of beamId table index configured to be used by the O-DU for a given tx-array-carrier. The value shall be chosen from the list 'tx-array-beamId-table-indexes' advertised by the O-RU."

### [MP-083] downlink-radio-frame-offset / downlink-sfn-offset
- 出處：UP L5520 起
- 型別：`downlink-radio-frame-offset` 為 uint32 range 0..12288000，mandatory；`downlink-sfn-offset` 為 int16 range -32768..32767，mandatory
- 原文："This parameter is used for offsetting the starting position of 10ms radio frame. Note: The value should have same value within DU to all tx-array-carriers that have same frequency and bandwidth. Note2: Unit is 1/1.2288e9 s. Then, its range is calculated 0..12288000."；"This parameter is used for offsetting SFN value. Unit is in 10ms."
- 說明：兩者都是時序偏移，與輻射方向無關（見 MP-006）。

### [MP-084] t-da-offset、reference-level
- 出處：UP（位於 L5520 之後）
- `t-da-offset`：uint32，units Tc，default 0，if-feature EXT-ANT-DELAY-CONTROL。原文："the time difference between the output of DL signal at the antenna connector of O-RU and the transmission over the air. units are Tc=~0.5ns=1/1.96608GHz."
- `reference-level`：decimal64 fd4，dB，default 0，if-feature TX-REFERENCE-LEVEL。原文："Allows to adjust reference level for sum of IQ signal power over eAxCs in this array-carrier."

### [MP-085] tx-array-carriers/active（含 SLEEP）
- 出處：UP `grouping tx-common-array-carrier-elements`（L1701）；MP §15.3.2
- 列舉：`INACTIVE`、`SLEEP`、`ACTIVE`，default INACTIVE
- 原文（MP §15.3.2）："To save energy, O-RU may disable all array elements of tx-array / rx-array associated with the tx-array-carrier / rx-array-carrier in sleep mode provided there is no impact to operation of other tx-array-carriers / rx-array-carriers."

### [MP-086] general-config 中新增的天線／BF 相關開關
- 出處：UP `grouping general-config`（L959）
- `multiple-beamId-tables-support-enabled`（L1017）：boolean，default false。原文："When the parameter has value true, O-DU will be able to use multiple beamId table capability of O-RU."
- `energy-sharing-groups-disabled`（L1028）：uint8 leaf-list，if-feature MPLANE-DATA-LAYER-CONTROL
- `max-power-control-method`（L1185）：`max-power-control-methods`，列舉 `MAX-POWER-PER-TX-ARRAY-CONTROL`、`MAX-POWER-PER-TX-ARRAY-CARRIER-CONTROL`
- `null-control-method`（L1191）：`NULL-CONTROL-METHOD`，列舉 `NULL-PER-ARRAY-CARRIER`、`NULL-PER-ARRAY`。原文："When this leaf does not exist, it implies null steering functionality is not enabled for the O-RU"
- `vswr-thresholds`（L1075，if-feature CONFIGURABLE-VSWR-THRESHOLDS）：包含 default、range 與可設定的 global 值及 per tx-array-element 門檻；`*-monitoring-trigger-power` 的單位為 dBm（UP revision 2024-08-12 "4) add support for VSWR thresholds"）

---

## 5. o-ran-beamforming（BF，revision 2025-04-14）

### [MP-040] /beamforming-config（頂層）
- 出處：BF L1016；`config false`；由 `uses beamforming-config; uses beamforming-supported-type; container beam-tilt (if-feature BEAM-TILT)` 組成
- 原文（模組）："This module defines the beamforming capabilities of an O-RU. Only O-RUs that support beamforming shall support this module."
- 原文（MP §15.4.1）："Beamforming support is optional, and an O-RU shall indicate that it supports such functionality by indicating that it supports the "urn:o-ran:beamforming:x.y" namespace."

### [MP-041] per-band-config（deprecated）/ capabilities-groups
- 出處：BF L710 `list per-band-config`（key band-number，config false，**status deprecated**）；L718 `list capabilities-groups`（key capabilities-group uint16）
- 原文："Capabilities groups identification number assigned to be referenced by operations and notifications. This also help to group particular beamforming capabilities and bind it with arrays"
- 元素（grouping per-band-config-element）：`band-number`（leafref → module-cap band-number）、`tx-array`/`rx-array`（leaf-list，leafref → UP tx-arrays/rx-arrays name）、`static-properties`、`beam-information`
- revision：BF 2024-12-23 "1) Deprecate per-band-config list related RPC and Notification"

### [MP-042] static-properties：rt-bf-weights-update-support 與 beamforming-type
- 出處：BF L319（rt-bf-weights-update-support，boolean）、L325（choice beamforming-type）
- 原文："The parameter informs if O-RU supports real time beamforming weights update through C-Plane messaging"
- choice 的三個 case：
  - `frequency/frequency-domain-beams`
  - `time/time-domain-beams`
  - `hybrid/hybrid-beams`
  - 三者都有 `when "../rt-bf-weights-update-support = 'true'"`，並包含 beamforming-parameters、bf-compression-details、additional-compression-method-supported。
  - time 與 hybrid 另外包含 granularity-parameters。
  - 三者都有 `beamforming-params-for-mul-beamId-tables`（**新增**，if-feature MULTIPLE-BEAMID-TABLES-SUPPORTED）。
  - hybrid 另外有 `fd-weights-mapping`（**新增**，見 MP-043）。

### [MP-043] fd-weights-mapping（h(k) 映射，新增）
- 出處：BF L410 `.../hybrid-beams/fd-weights-mapping`（key fd-weight-number uint16；array-elements 為 uint16 leaf-list）
- 原文："Mapping of array elements to frequency domain beamforming weight. See h(k) in O-RAN CUS-Plane, clause 12.5.3"；"Frequency domain beamforming weight number. See k' in O-RAN CUS-Plane, clause 12.5.3"
- revision：BF 2023-04-10 "1) Added h(k) mapping"

### [MP-044] beamforming-parameters / granularity / number-of-beams / p-dash
- 出處：BF L237；L439；L451
- `max-number-of-beam-ids`：uint16，range "min .. 32767"，mandatory。原文："The number of Beam ID values that can be used for beams of the beamforming domain. Maximum Beam ID value for the beamforming domain will be initial-beam-id+max-number-of-beam-ids-1."
- `initial-beam-id`：uint16，range "min .. 32767"，mandatory。原文："First Beam ID that can be used for addressing beams of the beamforming domain."（BF revision 2025-04-14 "1) Improve description of max-number-of-beam-ids and initial-beam-id."）
- `frequency-granularity`：列舉 `CC`、`BAND`；`time-granularity`：列舉 `SLOT`、`SYMBOL`；兩者皆 mandatory
- `number-of-beams`：uint16，**status deprecated**
- `p-dash`：uint16。原文："This parameters specifies the dimesionality of the time-domain beamforming operation. Refer to description of parameter p' in clause 12.4.3.4.2 of CUS-Plane specification."

### [MP-045] beam-information / beamforming-properties / beamforming-property
- 出處：BF grouping per-band-config-element、beamforming-property（L464 起）
- `number-of-beamforming-properties`：uint16
- `beamforming-properties`（key beam-id，uint16 range "min .. 32767"）
- `beam-type`：列舉 `COARSE`、`FINE`（"This value indicates the beam resolution."）
- `beam-group-id`：uint16（"Beams with same beamGroupsID can be transmitted simultaneously."）
- `coarse-fine-beam-relation`、`neighbour-beams`：**deprecated**，由 `coarse-fine-beam-capability-based-relation`、`neighbour-beams-capability-based`（typedef beam-capabilities-reference）取代
- 原文（beam-information）："Beam information which exposes beamforming related O-RU capabilities. Specifies beam properties for predefined beamforming as described in clause 'Predefined-beam beamforming' of CUS-Plane specification"
- 說明：這是 GoB 預定義波束的鄰接與同時傳送關係。**BF YANG 沒有每個 beam 的方位角、仰角或波束寬度 leaf**（未找到），這些資訊只存在於實作自訂的 beamforming 檔案中（見 MP-047）。

### [MP-046] beamforming-supported-type / ue-specific-beamforming / dmrs-bf-general-capabilities
- 出處：BF L690；L734；L790（**新增**）
- `beamforming-trough-attributes-supported`：boolean。原文："Informs if beamforming can be controlled providing attributes to O-RU (like angles, beamwidth)."
- `beamforming-trough-ue-channel-info-supported`：boolean。原文："Informs if beamforming can be controlled by UE information."
- `ue-specific-beamforming`：presence 容器（ST6）。`max-number-of-ues`（uint8）已 **deprecated**，改用 `max-number-of-ues-15bit`（uint16 range "1 .. 32767"）；另有 `channel-information-compression-method-supported` 與 `dynamic-channel-information-compression-supported`（if-feature CHANNEL-INFORMATION-COMPRESSION）
- `dmrs-bf-general-capabilities`（新增）：
  - `equalization-data-scaling`：`EQ-SCALING-FUNCTION-TYPE`，列舉 `SCALING-F-1`（"G = SINR/(1+SINR)"）、`SCALING-F-2`（"G = 1"）
  - `max-num-ues-supported`：uint16 1..32767
  - `ueid-max-layer-bits`：uint8 1..4
  - `max-num-ueids`：uint16 1..32767
  - revision：BF 2024-08-12 "1) add DMRS-BF capabilities."

### [MP-047] operational-properties 與 beamforming 設定檔（MODIFY-BF-CONFIG）
- 出處：BF L637；MP §15.4.3；MP §12.2
- `number-of-writeable-beamforming-files`：uint8，range "1 .. max"，mandatory
- `update-bf-non-delete`：boolean，default false
- `persistent-bf-files`：boolean，default false
- `in-service-bf-update`（**新增**）：boolean，default false，`when "../update-bf-non-delete = 'true'"`
- 原文（MP §15.4.3）："**The file format of the beamforming configuration is O-RU implementation specific.**"
- 原文（MP §15.4.3）："The O-RU shall locate the beamforming configuration file in the generic folder, i.e. O-RAN/beamforming/ or o-ran/beamforming/."
- 原文（MP §15.4.3）："An O-RU supporting the modification of beamforming configuration shall support the storage of at least two beamforming files per capabilities-group supported. For each capabilities-group, one file corresponds to the pre-defined (factory, read-only) beamforming configuration and at least one file corresponds to a modified (read-write) beamforming file."
- 原文（MP §15.4.3）："[Abnormal handling] If the O-RU fails to activate the edited beamforming configuration file correctly ... the O-RU shall revert back to the pre-defined/factory beamforming configuration file"
- 原文（MP §12.2）："o-ran/beamforming/ - used to store beamforming configuration files"
- 結論：O-RAN **沒有標準化**波束權重檔的格式（未找到任何格式定義）。流程是 file upload/download 後，用 RPC 啟用檔案。
- revision：BF 2024-08-12 "2) add new capability to update beamforming configuration without deactive tx/rx-array-carrier"

### [MP-048] RPC activate-beamforming-config（deprecated）/ activate-beamforming-config-by-capability-group
- 出處：BF L1032、L1076（if-feature MODIFY-BF-CONFIG）
- input：`beamforming-config-file`（string，mandatory，"file name stored in o-ran/beamforming folder is indicated"），加上 band-number（舊 RPC）或 capabilities-group（新 RPC）
- output：`status`（`ACCEPTED`/`REJECTED`，REJECTED 時的原文為 "The O-RU should then use the default beamforming file."）、`error-message`
- 原文（舊 RPC）："This RPC is deprecated due to the deprecation of the list per-band-config. The RPC activate-beamforming-config-by-capability-group should be used instead."
- notification：`beamforming-information-update`（deprecated）、`capability-group-beamforming-information-update`

### [MP-049] Beam tilt（預定義波束的數位 tilt）
- 出處：BF feature BEAM-TILT（L196）；grouping beam-tilt-configuration（L798）、beam-tilt-state（L866）、beam-tilt-report（L963）；RPC modify-predefined-beam-tilt-offset（L1118）；notification predefined-beam-tilt-offset-complete（L1169）；MP §15.4.4
- 設定（RPC input，list predefined-beam-tilt-offset，key capabilities-group）：
  - `elevation-tilt-offset-angle`：int16 range -90..90，units degrees，default 0
  - `azimuth-tilt-offset-angle`：int16 range -90..90，units degrees，default 0
  - 原文："Values smaller than 0 represents an up-shift of the default service area towards the zenith (i.e., corresponding to a decrease in zenith angle) and values larger than 0 represent a down-shift ... The actual angle used is (angle DIV granularity) * granularity. Any O-RU which is reset using the o-ran-operations:reset RPC shall reset its offset angle to its default value."
  - azimuth 的原文："represents counter-clockwise rotation around z-axis. I.e., assuming view from the UE ..., value larger than 0 and smaller than 0 respectively represent right-shifted and left-shifted of the default service area in azimuth domain."
- 能力（`/beamforming-config/beam-tilt/predefined-beam-tilt-offset-information`）：
  - `elevation-tilt-offset-granularity`、`azimuth-tilt-offset-granularity`：uint8 0..30，units Degrees，mandatory（值 0 表示不支援）
  - `minimum-supported-elevation-tilt-offset`、`minimum-supported-azimuth-tilt-offset`：int16 -90..0
  - `maximum-supported-elevation-tilt-offset`、`maximum-supported-azimuth-tilt-offset`：int16 0..90
  - `run-time-tilt-offset-supported`：boolean，mandatory
- 狀態：`predefined-beam-tilt-state/{elevation,azimuth}-tilt-offset-angle`，int16 -90..90
- 原文（MP §15.4.4）："This capability is an O-RU specific functionality, enabling adaptation of the service area associated with an O-RU without the need for operation of additional ALDs described in clause 14, or modifying the beamforming configuration using the "MODIFY-BF-CONFIG" feature"
- 原文（MP §15.4.4）："Tilting is a per band operation and hence the parameters are defined per band."（YANG 實際以 capabilities-group 為 key）
- 原文（MP §15.4.7.5）："BEAM-TILT is a digital tilt feature which does not impact antenna's physical position"
- 說明：這是 O-RAN 唯一的 tilt leaf，屬於**數位 tilt 偏移**，作用在整組 GoB 上。3GPP 對應：概念上相當於 TS 28.658/32.xxx 的 RET tilt，但 O-RAN 未直接引用。

### [MP-050b] Multiple beamId tables（MP §15.4.6）
- 出處：MP §15.4.6.1–15.4.6.3；MC L959 `max-beamId-tables-supported`（uint8）；MC L1147 / L1226 `[tr]x-array-beamId-table-indexes`（uint8 leaf-list）
- 原文："Multiple beamId tables supported by the O-RU are expected to be linearly indexed from 1 to 255."；"the first list entry in tx-array-beamId-table-indexes/rx-array-beamId-table-indexes shall always point to default global beamId table which shall be of size 32767."

---

## 6. Null steering（UP，v21.01 新增；MP §15.4.7）

### [MP-130] null-steering-capability（tx-arrays）
- 出處：UP L5898，if-feature NULL-STEERING
- `max-azimuth-angle`、`min-azimuth-angle`、`max-zenith-angle`、`min-zenith-angle`：int16，units 0.1（"Unit is 0.1 degree"）；其中 min-zenith-angle 為 mandatory
- `max-null-width-value`：uint8，default 1
- `max-total-null-point-width`、`max-total-null-stripe-width`、`max-total-null-and-null-stripe-width`：uint32
- 原文（MP §15.4.7.1）："Null steering is a directional interference mitigation feature. It utilizes beamforming technology to reduce EIRP towards given directions. Null steering function is applicable for pre-defined beams."
- 原文（MP §15.4.7.2）："There are two types of null(s): null point and elevation null stripe. A null point is a null at a certain zenith and azimuth angle. Elevation null stripe is null at a zenith angle for all azimuth angles."
- 注意：MP §15.4.7.2 使用的名稱 `max-total-null-width` 與 YANG leaf `max-total-null-point-width` 不一致（依原文照錄）。

### [MP-131] null-steering-info（設定）
- 出處：UP `grouping null-steering-cfg-grp`（L772）；由 `tx-array-carriers`（L5617）與 `/user-plane-configuration/array-config/array-null-config[array-name]`（L954）引用
- `intended-null`（key id uint8）欄位：
  - `azimuth-angle`：int16，0.1°
  - `zenith-angle`：int16，0.1°，mandatory
  - `null-width`：uint8，default 1
  - `null-freq`：uint32
- `beam-id-ranges-in-scope/beam-id-range`（if-feature BEAM-ID-SCOPE-NULLING）欄位：
  - `range-id`：uint8
  - `first-beam-id`：uint16，mandatory
  - `target-first-beam-id`：uint16，if-feature TARGET-BEAM-RANGE
  - `num-of-ids`：uint16，default 1
- `last-bfw-null-completed`：date-and-time，config false
- 原文（MP §15.4.7.3）："Zenith angle and azimuth angel for a null point or elevation null stripe uses array coordinate system as defined in CUS plane specification [2] Clause 12.5.2."
- notification：`predefined-beam-null-complete`（L6788）
- revision：UP 2026-05-07 "1) Addition of NULL-STEERING feature and related parameters."

---

## 7. o-ran-module-cap（MC）

### [MP-070] ru-capabilities：類別、埠數與空間流數
- 出處：MC `grouping ru-capabilities`（L636）
- `ru-supported-category`：列舉 `CAT_A`（"Informs that precoding is not supported in O-RU"）、`CAT_B`（"Informs that precoding is supported in O-RU"）
- `number-of-ru-ports`：uint8，**deprecated**；由 `number-of-ru-ports-ul`、`number-of-ru-ports-dl`（uint8）取代
- `extended-number-of-ru-ports-ul`、`extended-number-of-ru-ports-dl`（**新增**）：uint16 range "256..max"，`when "../number-of-ru-ports-[ud]l=255"`（MC revision 2025-04-14 "1) added support for expanded range of ru-port."）
- `number-of-spatial-streams`：uint8。原文："This value indicates the maximum accumulated number of spatial streams supported by O-RU for DL and UL."
- `number-of-spatial-streams-dl`、`number-of-spatial-streams-ul`（**新增**）：uint8（MC revision 2023-04-10 "1) Clarify the parameter number-of-spatial-streams"）
- `max-power-per-pa-antenna`、`min-power-per-pa-antenna`：**deprecated**。原文："min-gain and max-gain define constraints related to TX power budget, as defined in CUS-Plane, clause 8.1.3.3."
- `fronthaul-split-option`：uint8 range "7"
- 3GPP 對應：空間流數對應 TS 38.214 的最大 layer 數（概念對應）。

### [MP-071] ru-capabilities 中新增的 BF 與節能欄位
- `max-beamId-tables-supported`（L959）：uint8
- `energy-saving-capability-common-info`（L926）：`st8-ready-message-supported`、`sleep-duration-extension-supported`、`emergency-wake-up-command-supported`，皆為 boolean
- `min-hibernate-time-duration`、`max-hibernate-time-duration`（L975）：uint32，units minutes；max 為 mandatory；if-feature DEEP-HIBERNATE
- `bundle-offset-in-se11-supported`：boolean，default false

### [MP-072] band-capabilities
- 出處：MC `grouping band-capabilities`（L1238）
- `band-number`：uint16。原文："the integer representation of the operating band, as defined in 3GPP TS 38.104, clause 5.2 and/or 3GPP TS 36.104, clause 5.5. For example, 5G band n77 is represented as integer '77'."（MC revision 2024-12-23 "1) clarifying band-number"）
- `max-num-component-carriers`：uint8
- `max-num-sectors`：uint8
- `max-num-bands`：已 deprecated（移到 ru-capabilities）
- `max-power-per-antenna`、`min-power-per-antenna`：deprecated
- `codebook-configuration_ng`、`_n1`、`_n2`：deprecated。原文："Parameter deprecated since antenna topology already specified in [tr]x-array"
- 3GPP 對應：band-number 對應 TS 38.104 §5.2。

### [MP-073] 未找到的項目
- module-cap 中沒有 beamforming method 或 beam 數量的 capability（**未找到**）。這些資訊位於 BF 與 UP 的 endpoint-types。

---

## 8. 節能：TRX control、antenna mask、ASM、資料層、最大功率（MP §20）

### [MP-120] MP §20.1 範圍
- 原文："Carrier deactivation. RF channel switch off/on (C-Plane controlled and M-Plane controlled). Advanced sleep modes. Deep hibernate. Max output power control."

### [MP-121] TRX control（C-Plane 控制）能力（§20.3.1.2）
- 出處：MC `grouping trx-control-capability-info`（L599），掛在 UP `tx-arrays/capabilities/supported-energy-saving-capabilities-dl/trx-control-capability-info`（rx 側為 `-ul`）；if-feature "feat:TRX-CONTROL or feat:TRX-CONTROL-BIDIR"
- `supported-trx-control-masks`（key index uint8）：`mask-name` 為 string，`antenna-mask` 為 binary
- `sleep-modes`（key sleep-mode-type）：
  - `sleep-mode-type` 列舉：`SLEEP_MODE_0`–`SLEEP_MODE_3`
  - `wake-up-duration`：uint32，microseconds
  - `wake-up-duration-guaranteed`：boolean
- `defined-duration-sleep-supported`、`undefined-duration-sleep-supported`：boolean
- 原文（MP §20.3.1.1）："TRX control via C-Plane messages is used to achieve energy saving through disabling one or more O-RU array elements for a defined or undefined period of time. For example, an O-DU can switch off 32 out of 64 array elements of a massive MIMO antenna array."
- 原文（MP §20.3.1.2）："The absence of the list supported-trx-control-masks indicates that any combination of antenna mask is supported by the O-RU for a particular [tr]x-array."
- revision：MC 2026-05-07 "1) Added feature flag TRX-CONTROL-BIDIR for impacted parameters and descriptions."；MC 2023-08-14 "1) Introduce TRX-control and advanced sleep modes"
- 3GPP 對應：TR 38.864（NES）概念，O-RAN 原文未引用。

### [MP-122] TRX control（M-Plane 控制）與 antenna mask（§20.3.2）
- 出處：UP `grouping mplane-trx-control-supp-antenna-masks`（L750；`mplane-supported-trx-control-masks`，key index uint8，`antenna-mask` binary）；UP `grouping array-config-group`（L843）：`tx-array-antenna-mask-config`、`rx-array-antenna-mask-config`（key array-name，欄位為 `antenna-bitmask` binary 與 `antenna-bitmask-index` uint8，if-feature MPLANE-TRX-CONTROL）；notification `mplane-trx-control-ant-mask-update`（L6718；欄位 array-name、array-type TX-ARRAY/RX-ARRAY、updated-antenna-mask、updated-antenna-mask-index）
- 原文（UP antenna-bitmask）："The antenna mask contains as many binary values as number of array elements associated with respective tx or rx-array. Value of '1' indicates antenna element shall be kept active and value of '0' indicates antenna element should be turned inactive. Refer clause 20.3.2 of M-Plane specification."
- 原文（MP §20.3.2.3）："the antenna mask configuration shall be done for the largest tx or rx array that is advertised by the O-RU, not for the tx-array or rx-array which is a subset of the largest array"
- 原文（MP §20.3.2.3）："Prior to any M-Plane TRX Control antenna mask or associated antenna index being configured, the value of the antenna mask shall be considered to be all-ones, meaning all array-elements are enabled."
- 原文（MP §20.3.2.3 NOTE）："Binary values are encoded with a base-64 encoding (see reference [4]) so the above mask would actually be represented as "/wAA/w=="."
- 原文（MP §20.3.2.2）："If an antenna mask list is present, an all-ones antenna mask shall be included in the list to assure all array elements can be turned on."
- 原文（MP §20.3.2.5）：O-DU 在發出 C-Plane TRX Control 命令之前，必須先確認目前 M-Plane 設定的 mask 為 all-ones；反向亦同。
- revision：UP 2024-04-15 "6) support for M-plane based TRX control for Network Energy Saving."

### [MP-123] ASM（§20.4）
- 出處：MC `grouping asm-capability-info`（`uses sleep-mode-capability-info`）；UP `.../asm-capability-info`（if-feature ADVANCED-SLEEP-MODE）
- 原文："These capability attributes are defined for each [tr]x-arrays."

### [MP-124] 資料層控制（§20.3.3）
- 出處：UP `energy-sharing-groups-disabled`（MP-086）、`energy-sharing-group-id`（MP-063）、notification `data-layer-control-wakeup-notification`（L6706）
- 原文（MP §20.3.3.1）："Data layer control is used to achieve energy saving through reducing the number of data layers independent of TRX-Control."
- 原文（MP §20.3.3.2）："The O-RU controller shall trigger data layer control only for the energy-sharing-group of endpoints all of whose eAxC-id values are currently not being used by the O-DU"
- revision：UP 2023-12-11 "4) Introduction of new energy saving sub-use case - Data Layer control"

### [MP-125] 最大輸出功率控制（§20.6）
- 出處：UP `array-config/max-power-control-config`（key array-name，`max-power-level-index` 為 leafref 到 tx-arrays supported-max-power-level/index）；MP-011；MP-081；MP-086；notification `max-power-update`（L6771）
- 原文（MP §20.6.1）："To achieve this, the number of scheduled PRBs may be restricted by the O-DU, allowing the O-RU to adapt Power Amplifier (PA) accordingly."
- 原文（MP §20.6.3）："If the new value results in increased power reduction, then the O-DU shall reduce the power (e.g., by scheduling less PRBs) for the affected carriers before requesting the new configuration."
- revision：UP 2025-08-11 "4) Adding new MAX POWER CONTROL for energy saving functionality."

### [MP-126] Deep hibernate（§20.5）
- 原文："Deep-hibernate is an O-RU mode used to achieve relatively higher energy saving by disabling all carriers and stopping the C/U/S/M functions"；"If an O-RU receives a deep-hibernate RPC while one or more [tr]x-array-carriers are active, then it shall reject the RPC"

---

## 9. ALD / RET（MP §14.4、§19.11.6）

### [MP-140] ALD 協定
- 出處：MP §14.4.1
- 原文："An O-RU can connect to one or more external equipment including antenna line devices such as a RET, MultiRET, MHA, RAE, etc."；"For the communication with antenna line devices, AISG 2.0 protocol [26] as Layer 7 application and HDLC protocol as Layer 2 data link are used."；"AISG 2.0 uses Application Part protocols (RETAP, TMAAP etc.) at Layer 7 and HDLC as a Layer 2 datalink protocol."
- 3GPP 對應：TS 37.462（HDLC / Iuant 第 2 層）、TS 37.466（Iuant 應用層）。

### [MP-141] RPC ald-communication（透傳）
- 出處：ALD : `rpc ald-communication`；MP §14.4.3
- input：
  - `port-id`：leafref → `/ald-ports-io/ald-port/port-id`，mandatory
  - `ald-req-msg`：binary，length "0..1200"
- output：
  - `port-id`
  - `status`：`ACCEPTED`/`REJECTED`
  - `error-message`
  - `ald-resp-msg`：binary 0..1200
  - `frames-with-wrong-crc`、`frames-without-stop-flag`、`number-of-received-octets`：uint32
- 原文（MP §14.4.3）："leaf: ald-req-msg (up to 1 200 bytes) - may contain HDLC address, control bits and payload (see: 3GPP TS 37.462 for details)."
- 原文（MP §14.4.2）："NOTE: The assumed HDLC communication speed is 9 600 bits per second."
- 原文（MP §14.4.3）："After reception, the O-RU shall wait a minimum of 3ms before the next transmission as per 3GPP TS 37.462, clause 4.5"
- **結論（tilt）**：RET 的機械或電子下傾角是由 O-DU 或 O-RU controller 自行組 AISG 2.0 RETAP 訊息，再經 `ald-req-msg` 以二進位**透傳**。O-RAN YANG 中**沒有 RET tilt leaf**（在 v21.01 全部非 import 模組中 grep `tilt` 只找到 o-ran-beamforming 的 predefined-beam-tilt，未找到其他結果）。O-RAN 唯一的 tilt leaf 是數位的 `elevation/azimuth-tilt-offset-angle`（MP-049）。MP §15.4.4 也明確把這兩者區分開來（"without the need for operation of additional ALDs"）。

### [MP-142] ald-port
- 出處：ALDP : `/ald-ports-io/ald-port`（config false，key name）
- 欄位：
  - `name`：string 1..255
  - `port-id`：uint8，mandatory。原文："If the module supports 2 ALD Port connectors, use 0 and 1."
  - `dc-control-support`：boolean，mandatory
  - `dc-enabled-status`：boolean，default false
  - `supported-connector`：列舉 `ANTENNA_CONNECTOR`、`RS485_PORT`
  - `related-o-ru-connectors`：leafref，class 為 O-RU-ANTENNA-CONNECTOR 或 O-RU-RS485
- 可設定項目：`ald-port-dc-control/dc-enabled`
- 其他：`over-current-supported`；notification `overcurrent-report`、`dc-enabled-status-change`
- 原文（MP §14.4.3 程序）："NETCONF Client triggers DC voltage on desired ALD ports using NETCONF <edit-config> RPC. After DC is turned on - NETCONF Client shall wait at least 3 s."
- revision：ALDP 2023-08-14 "1) Introduction of O-RU Connectors for ALD Port."

### [MP-143] Shared O-RU 與 ALD（§19.11.6）
- 原文："the shared O-RU host shall be responsible for the operation of the antenna line devices." "The Shared O-RU Host may be required to co-ordinate antenna line operations with the different Shared Resource Operators, e.g. remote electrical tilt."

### [MP-144] O-RU 天線連接器（§14.6）
- 出處：HW identity `O-RU-ANTENNA-CONNECTOR`（L233），以及衍生的 `O-RU-FEEDER`、`O-RU-BF-CAL`（L248）
- 原文（MP §14.6.2.1）："Exposed O-RU Connectors of class "O-RU-ANTENNA-CONNECTOR" ... are used in o-ran-uplane-conf.yang module to show how feeders and beamforming calibration lines are related to antenna arrays and their array elements."

---

## 10. Antenna calibration（AC；MP §15.5）

### [MP-150] antenna-calibration-capabilities（config false）
- 出處：AC `grouping antenna-calibration-capabilities`；`/antenna-calibration/antenna-calibration-capabilities`

| leaf | 型別 / 單位 / 條件 |
|---|---|
| self-calibration-support | boolean，default false |
| coordinated-calibration-support | boolean，default false，if-feature O-RU-COORDINATED-ANT-CAL |
| number-of-calibration-symbols-per-block-dl / -ul | uint8 1..max，symbols，mandatory |
| interval-between-calibration-blocks | uint8，symbols |
| number-of-calibration-blocks-per-step-dl / -ul | uint8 1..max，mandatory |
| interval-between-calibration-steps | uint8，radio-frames |
| number-of-calibration-steps | uint8 1..max，mandatory |
| calibration-period | uint16，minutes（COORDINATED） |
| configured-preparation-timer-supported | boolean，default false |

- 原文（MP §15.5.1）："Antenna calibration operation is an optional capability whose operation is dependent on O-RU design"

### [MP-151] self-calibration-policy（config true）
- `self-calibration-allowed`：boolean，default false
- `coordinated-calibration-allowed`：boolean，default false，限制條件 `must "../self-calibration-allowed = 'false'"`
- `coordinated-ant-calib-prep-timer`：uint8，range "2..10|60"，seconds，default 60
- `coordinated-calibration-multiple-time-resources-allowed`：boolean
- revision：AC 2024-04-15 "1) fixing bug in coordinated-ant-calib-prep-timer."

### [MP-152] RPC start-antenna-calibration 參數（MP Table 15.5.5-1）
- 原文（表）：
  - `symbol-bitmask-dl/ul`：string
  - `slot-bitmask-dl/ul`：string
  - `frame-bitmask-dl/ul`：string
  - `calibration-step-size`：uint8，"Number of frames within a calibration step."
  - `calibration-step-number`：uint8
  - `start-sfn`：原文寫作 "unt16"
- notifications：`antenna-calibration-required`（dl/ul-calibration-frequency-chunk，單位 Hz）、`antenna-calibration-coordinated`、`antenna-calibration-result`、`antenna-calibration-multiple-time-resource-params`
- 原文（MP §15.5.2.2）："If the O-RU does not receive a start-antenna-calibration RPC request within 60 seconds after triggering the sending of the first antenna-calibration-required notification, the O-RU shall raise a major alarm "Triggering failure of antenna calibration""

---

## 11. 其他天線相關 PM：tx-antenna（VSWR）

### [MP-160] o-ran-pm-tx-antenna-stats
- 出處：TXA（submodule）
- `tx-antenna-meas-object-type`：只有 `VSWR` 一種
- `tx-antenna-object-unit`：`ARRAY_ELEMENT`（key 為 tx-array + tx-array-element uint32）、`CONNECTOR_BAND`（key 為 related-o-ru-connector（O-RU-FEEDER）+ band-number）
- `report-info`：AVERAGE、STD_DEVIATION、MAXIMUM(_AND_TIME)、MINIMUM(_AND_TIME)、FIRST(_AND_TIME)、LATEST(_AND_TIME)、FREQUENCY_TABLE
- revision：TXA 2025-12-22 "1) submodules creation. 2) correct max-bin-count definition."（2022-12-05 的本地子集中沒有此檔，無法比對早期差異）

---

## 12. 2022-12-05 → v21.01 變更清單（天線 / BF 相關）

比對方法：對 OLD 與 v21.01 的 uplane-conf、beamforming、module-cap 三個模組，擷取所有 `leaf|leaf-list|container|list|typedef|grouping|feature|rpc|notification` 名稱後做 diff。結果只有新增，**沒有任何名稱被移除**。processing-element 與 hardware 沒有新舊版可比對的相關差異（未逐項列出）。

### 12.1 revision 紀錄（逐字，僅列 2022-12-05 之後）
- **UP**：
  - 2023-04-10 v12 "5) continuity bit information in Section Extension 11 6) U-Plane Processing Limits"
  - 2023-08-14 v13 "5) Introduction of TRX-Control and Advanced Sleep Mode for network energy savings"
  - 2023-12-11 v14 "3) introduce max-prb-blks-per-sec-ext-23 and se-23-prb-block-mode-supported 4) Introduction of new energy saving sub-use case - Data Layer control"
  - 2024-04-15 v15 "2) add support for for beamforming list and delay profiles(s) per endpoint. 3) add support for user-group optimization. 4) add support for multiple beamid tables. ... 6) support for M-plane based TRX control for Network Energy Saving. ... 8)/9)（max-beams 描述與 multiple-beamid-tables leaf）"
  - 2024-08-12 v16 "1) add up-link performance improvement functionality, including DMRX-BF-EQ and DMS-BF-NEQ features 2) Introduction of capabilities and configuration for SE27 O-DU controlled dimensionality reduction 3) add support for se-20-multi-sd-punc-pattern 4) add support for VSWR thresholds 5) add Endpoint beam capacity counter for same or diff beamId values"（"DMRX"、"DMS" 為原文拼字）
  - 2024-12-23 v17 "1) clarified polarization list with external antennas ..."
  - 2025-04-14 v18 "1) corrected description of common-se24-dmrs-capabilities-grp."
  - 2025-08-11 v19 "1) Added se-20-full-prb-puncture-with-different-section-id-supported. ... 4) Adding new MAX POWER CONTROL for energy saving functionality."
  - 2025-12-22 v20 "1) Added point-a-offset-to-absolute-frequency-center. ..."
  - 2026-05-07 v21 "1) Addition of NULL-STEERING feature and related parameters. 2) Addition of new RRM measurements. 3) ... 4) Update to parameters which apply to new feature TRX-CONTROL-BIDIR. 5) Addition of parameters for the feature SE31-MCS-INFORMATION."
- **BF**：
  - 2023-04-10 v11.1 "1) Added h(k) mapping"
  - 2024-04-15 v15 "1) clarifying descriptions inside capabilities-group. 2) add support for multiple beamid tables. 3) remove import by revision date for o-ran-compression-factors."
  - 2024-08-12 v16 "1) add DMRS-BF capabilities. 2) add new capability to update beamforming configuration without deactive tx/rx-array-carrier"
  - 2024-12-23 v17 "1) Deprecate per-band-config list related RPC and Notification"
  - 2025-04-14 v17.1 "1) Improve description of max-number-of-beam-ids and initial-beam-id."
- **MC**：
  - 2023-04-10 "1) Clarify the parameter number-of-spatial-streams 2) Introduce NB-IoT"
  - 2023-08-14 "1) Introduce TRX-control and advanced sleep modes"
  - 2023-12-11 "1) Introduce bundle-offset-in-se11-supported"
  - 2024-04-15 "1) add support for multiple beamid tables. ... 3) Support for deep hibernate sleep mode."
  - 2024-12-23 "1) clarifying band-number"
  - 2025-04-14 "1) added support for expanded range of ru-port."
  - 2026-05-07 "1) Added feature flag TRX-CONTROL-BIDIR ..."
- **AC**：2024-04-15 "1) fixing bug in coordinated-ant-calib-prep-timer."（OLD 為 2021-12-01）
- **ALD**：未變更（仍為 2021-12-01）。**ALDP**：2023-08-14、2024-08-12、2025-04-14（描述修正與 O-RU connectors）。

### 12.2 新增節點（與天線、BF、MIMO、節能相關者）
- **UP**：
  - typedef：`beamforming-method-type`、`NULL-CONTROL-METHOD`、`max-power-control-methods`
  - grouping：`array-config-group`、`null-steering-cfg-grp`、`mplane-trx-control-supp-antenna-masks`
  - list：`endpoint-bf-profile-group`、`tx/rx-array-antenna-mask-config`、`array-null-config`、`max-power-control-config`、`intended-null`、`beam-id-range`、`supported-max-power-level`、`vswr-threshold-per-tx-array-element`
  - container：`null-steering-capability`、`null-steering-info`、`beam-id-ranges-in-scope`、`supported-energy-saving-capabilities-dl/ul`、`trx-control-capability-info`、`asm-capability-info`、`mplane-trx-control-[tr]xarr-capability-info`、`vswr-thresholds`、`se24-dmrs-capabilities`
  - leaf：`bf-methods`、`supported-bf-methods`、`bf-profile-group`、`configured-bf-profile-id`、`configured-[tr]x-beamId-table-index`、`multiple-beamId-tables-support-enabled`、`max-total-beamids-per-{symbol,slot}`、`max-beams-per-{symbol,slot}-multiple-beamid-tables`、`max-total-beamids-per-{symbol,slot}-multiple-beamid-tables`、`antenna-bitmask(-index)`、`energy-sharing-group(-id)`、`energy-sharing-groups-disabled`、`carrier-max-power-reduction`、`array-max-power-reduction`、`max-power-level-index/used`、`max-power-control-method`、`null-control-method`、`se-20-*`、`se-27-*`、`max-dmrs-ant-port-number`、`max-user-data-layers`、`number-of-ue-data-layers`、`sinr-max-data-layers`、`pdbf-cyclic-delay-supported`
  - notification：`mplane-trx-control-ant-mask-update`、`max-power-update`、`predefined-beam-null-complete`、`data-layer-control-wakeup-notification`
- **BF**：
  - container `dmrs-bf-general-capabilities`（grouping `dmrs-bf-gen-capabilities`）
  - typedef `EQ-SCALING-FUNCTION-TYPE`
  - list `beamforming-params-for-mul-beamId-tables`、`fd-weights-mapping`
  - leaf `fd-weight-number`、`array-elements`、`in-service-bf-update`、`equalization-data-scaling`、`max-num-ues-supported`、`max-num-ueids`、`ueid-max-layer-bits`
- **MC**：
  - `number-of-spatial-streams-dl/ul`
  - `extended-number-of-ru-ports-dl/ul`
  - `max-beamId-tables-supported`
  - `tx/rx-array-beamId-table-indexes`
  - `energy-saving-capability-common-info`（`st8-ready-message-supported`、`sleep-duration-extension-supported`、`emergency-wake-up-command-supported`）
  - grouping `trx-control-capability-info`、`asm-capability-info`、`sleep-mode-capability-info`（`sleep-mode-type`、`defined-duration-sleep-supported`…）
  - `mask-name`、`antenna-mask`
  - `min/max-hibernate-time-duration`
  - `bundle-offset-in-se11-supported`
  - `supported-filter-pass-bandwidths-dl/ul`

### 12.3 在 v21.01 標記為 deprecated 的天線 / BF 節點
- **BF**：
  - `per-band-config`（L710）
  - `number-of-beams`
  - `coarse-fine-beam-relation`、`neighbour-beams`
  - `ue-specific-beamforming/max-number-of-ues`
  - RPC `activate-beamforming-config`（L1032）
  - notification `beamforming-information-update`（L1153）
  - 其中 per-band-config 相關的 RPC 與 notification 是在 2024-12-23 才被 deprecate，其餘在 05 中已標為 deprecated。
- **MC**：
  - `number-of-ru-ports`
  - `max-power-per-pa-antenna`、`min-power-per-pa-antenna`
  - band-capabilities 下的 `max-num-bands`、`max-power-per-antenna`、`min-power-per-antenna`、`codebook-configuration_ng/_n1/_n2`
- **UP**：`absolute-frequency-center`（"deprecated in version 5.0.0"）
- 沒有任何節點被刪除（status obsolete：未找到）。

---

## 13. RU 天線 M-plane 資料模型樹（摘要）

```
o-ran-uplane-conf : /user-plane-configuration                         [UP L6685]
├── tx-arrays* [name] (ro)                                            [MP-010/011]
│   ├── name, number-of-rows(M,u16), number-of-columns(N,u16), number-of-array-layers(Q,u8)
│   ├── horizontal-spacing / vertical-spacing          dec64.5  Meter
│   ├── normal-vector-direction/{azimuth,zenith}-angle dec64.4  Degrees
│   ├── leftmost-bottom-array-element-position/{x,y,z} dec64.4  Meter
│   ├── polarisations*[p] (1..2) / polarisation  {MINUS_45,ZERO,PLUS_45,PLUS_90}
│   ├── band-number → module-capability/band-capabilities/band-number
│   ├── related-o-ru-connectors*[name] / array-element-id* (u16)
│   ├── min-gain / max-gain  dec64.4 dB ; independent-power-budget (bool)
│   ├── capabilities*/ (support-for-dl, tx-array-beamId-table-indexes*)
│   │   └── supported-energy-saving-capabilities-dl/{trx-control-capability-info, asm-capability-info}   [MP-121/123]
│   ├── supported-max-power-level*[index]/array-max-power-reduction dB ; max-power-level-used   {MAX-POWER-CONTROL}
│   ├── mplane-trx-control-txarr-capability-info/mplane-supported-trx-control-masks*[index]/antenna-mask   {MPLANE-TRX-CONTROL}
│   └── null-steering-capability/{min,max}-{azimuth,zenith}-angle (i16, 0.1°), max-null-width-value, max-total-*   {NULL-STEERING}
├── rx-arrays* [name] (ro)  uses parameters; gain-correction-range/{max,min} dB; capabilities*; mplane-trx-control-rxarr-capability-info
├── relations*[entity] (ro) / array1, array2, types*[relation-type SHARED|COALOCATED]/pairs*
├── endpoint-types*[id] (ro)
│   ├── supported-section-types*[section-type]/supported-section-extensions* (u8)   ← SE19/SE20… 在此回報   [MP-060]
│   ├── endpoint-beam-capacity: max-beams-per-{symbol,slot}, max-total-beamids-*, max-beam-updates-*  (u16 ≤32767)
│   └── bf-profile-group* → endpoint-bf-profile-group   {BF-DELAY-PROFILE}
├── endpoint-bf-profile-group*[bf-profile-id] (ro) / supported-bf-methods* {NOBF,PDBF,WDBF,ABBF,CIBF,DMRS_BF_EQ,DMRS_BF_NEQ}, supported-delay-profile
├── static-low-level-[tr]x-endpoints*[name] (ro) / array, energy-sharing-group-id*, se-20-multi-sd-punc-pattern-suported …
├── low-level-[tr]x-endpoints*[name] (rw) / e-axcid{o-du-port,band-sector,ccid,ru-port}-bitmask + eaxc-id (u16),
│       configured-bf-profile-id, bf-methods*, se-20-multi-sd-punc-pattern-enabled-[tr]x …          [MP-050/061]
├── tx-array-carriers*[name] (rw)
│   ├── center-of-channel-bandwidth (u64 Hz), channel-bandwidth (u64 Hz), active {INACTIVE,SLEEP,ACTIVE}, state
│   ├── gain (dec64.4 dB, mandatory), carrier-max-power-reduction (dB ≥0)
│   ├── downlink-radio-frame-offset (u32 0..12288000, 1/1.2288e9 s), downlink-sfn-offset (i16, 10 ms)
│   ├── t-da-offset (u32 Tc), reference-level (dB), configured-tx-beamId-table-index (u8)
│   └── null-steering-info/intended-null*[id]{azimuth,zenith (0.1°), null-width, null-freq}, beam-id-ranges-in-scope
├── rx-array-carriers*[name] (rw) / gain-correction, n-ta-offset, t-au-offset, configured-rx-beamId-table-index …
├── general-config/ multiple-beamId-tables-support-enabled, energy-sharing-groups-disabled*,
│                   max-power-control-method, null-control-method, vswr-thresholds …
├── tx-array-antenna-mask-config*[array-name]/{antenna-bitmask (binary), antenna-bitmask-index (u8)}   {MPLANE-TRX-CONTROL}
├── rx-array-antenna-mask-config*[array-name]/{antenna-bitmask, antenna-bitmask-index}
└── array-config/ max-power-control-config*[array-name]/max-power-level-index ; array-null-config*[array-name]/null-steering-info
   notifications: [tr]x-array-carriers-state-change, mplane-trx-control-ant-mask-update, max-power-update,
                  predefined-beam-null-complete, data-layer-control-wakeup-notification

o-ran-beamforming : /beamforming-config (ro)                          [BF L1016]
├── per-band-config*[band-number]  (deprecated)
├── capabilities-groups*[capabilities-group u16]
│   ├── band-number, tx-array*, rx-array*
│   ├── static-properties/ rt-bf-weights-update-support (bool)
│   │   ├── choice beamforming-type: frequency-domain-beams | time-domain-beams | hybrid-beams
│   │   │     initial-beam-id, max-number-of-beam-ids (u16 ≤32767), [frequency-granularity CC|BAND, time-granularity SLOT|SYMBOL],
│   │   │     compression, beamforming-params-for-mul-beamId-tables*, hybrid: fd-weights-mapping*[fd-weight-number]/array-elements*
│   │   ├── number-of-beams (deprecated), p-dash (u16)
│   └── beam-information/ number-of-beamforming-properties,
│       beamforming-properties*[beam-id]/beamforming-property/{beam-type COARSE|FINE, beam-group-id,
│         coarse-fine-beam-capability-based-relation*, neighbour-beams-capability-based*}
├── ue-specific-beamforming! / max-number-of-ues-15bit (1..32767), channel-information-compression-*
├── operational-properties/ number-of-writeable-beamforming-files (u8≥1), update-bf-non-delete, persistent-bf-files, in-service-bf-update   {MODIFY-BF-CONFIG}
├── dmrs-bf-general-capabilities/ equalization-data-scaling, max-num-ues-supported, ueid-max-layer-bits (1..4), max-num-ueids
├── beamforming-trough-attributes-supported, beamforming-trough-ue-channel-info-supported (bool)
└── beam-tilt/   {BEAM-TILT}
    ├── predefined-beam-tilt-offset-information*[capabilities-group]/ {elev,azim}-tilt-offset-granularity (u8 0..30 °),
    │     minimum-/maximum-supported-{elevation,azimuth}-tilt-offset (i16 −90..0 / 0..90 °), run-time-tilt-offset-supported
    └── predefined-beam-tilt-state*[capabilities-group]/ {elevation,azimuth}-tilt-offset-angle (i16 −90..90 °)
   rpc: activate-beamforming-config (deprecated), activate-beamforming-config-by-capability-group{beamforming-config-file, capabilities-group},
        modify-predefined-beam-tilt-offset{predefined-beam-tilt-offset*[capabilities-group]/{elevation,azimuth}-tilt-offset-angle default 0}
   notif: capability-group-beamforming-information-update, predefined-beam-tilt-offset-complete

o-ran-module-cap : /module-capability                                 [MC]
├── ru-capabilities (ro)/ ru-supported-category {CAT_A,CAT_B}, number-of-ru-ports-{ul,dl} (u8) + extended-* (u16 ≥256),
│     number-of-spatial-streams(-dl/-ul) (u8), max-num-bands, max-beamId-tables-supported (u8),
│     energy-saving-capability-common-info/{st8-ready-message-supported, sleep-duration-extension-supported, emergency-wake-up-command-supported},
│     min/max-hibernate-time-duration (u32 minutes)
└── band-capabilities*[band-number u16 = TS 38.104 band] (ro)/ support-for-dl/ul, max-num-component-carriers, max-num-sectors

o-ran-antenna-calibration : /antenna-calibration                      [AC]
├── antenna-calibration-capabilities (ro)  (symbols/blocks/steps; calibration-period minutes)
├── self-calibration-policy/ self-calibration-allowed, coordinated-calibration-allowed, coordinated-ant-calib-prep-timer (2..10|60 s)
└── rpc start-antenna-calibration ; notif antenna-calibration-required/-coordinated/-result/-multiple-time-resource-params

o-ran-ald-port : /ald-ports-io                                        [ALDP]
├── ald-port*[name] (ro)/ port-id (u8), dc-control-support, dc-enabled-status, supported-connector {ANTENNA_CONNECTOR,RS485_PORT}, related-o-ru-connectors*
└── ald-port-dc-control*[name]/dc-enabled
o-ran-ald : rpc ald-communication { port-id, ald-req-msg (binary ≤1200) } → { status, ald-resp-msg, CRC/stop-flag/octet counters }
            （AISG 2.0 RETAP 透傳；O-RAN 無 RET tilt leaf）
o-ran-performance-management ⊃ o-ran-pm-tx-antenna-stats : VSWR per ARRAY_ELEMENT | CONNECTOR_BAND
```

---

## 14. 仍未解決或需到其他規範查證
- SE19 的語意、各 SE 與 BF 方法的對應、antenna mask 的 bit 順序、陣列座標系、h(k)：需查 CUS（O-RAN.WG4.CUS.0）的 §7.7.x、§12.5.2、§12.5.3、§16.2。MP 只引用這些章節，未定義內容。
- 每個 beam 的指向角與波束寬度：M-plane YANG **未找到**；beamforming 檔案格式為「O-RU implementation specific」（MP §15.4.3）。
- RET 電子下傾角的值域與單位：不在 O-RAN MP 範圍內 → **已解決**，見 `09_38141-1_ALD.md` [37466-003]（signed int16、10 倍電氣下傾角 = 解析度 0.1°、正值向下）與 [37466-014]（上下界由 device data 0x06/0x07 宣告）。AISG 2.0 原文仍未取得（09 §F #10）。
