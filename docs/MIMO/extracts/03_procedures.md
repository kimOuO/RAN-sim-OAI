# 03 — Beamforming + MIMO 程序與規則摘錄（TS 38.214 / 38.213 / 38.215 / 38.321 / 38.300）

來源（皆為 Release 19）：
- 3GPP TS 38.214 V19.4.0（ETSI TS 138 214 V19.4.0, 2026-07）— `docs/MIMO/specs/ts_138214v190400p.pdf`
- 3GPP TS 38.213 V19.4.0（ETSI TS 138 213 V19.4.0, 2026-07）— `docs/MIMO/specs/ts_138213v190400p.pdf`
- 3GPP TS 38.215 V19.3.0 — `docs/MIMO/specs/ts_138215v190300p.pdf`
- 3GPP TS 38.321 V19.3.0（ETSI 2026-08）— `docs/MIMO/specs/ts_138321v190300p.pdf`
- 3GPP TS 38.300 V19.3.0 — `docs/MIMO/specs/ts_138300v190300p.pdf`
- 輔助核對（標 `S331-` / `S211-`）：TS 38.331 V19.3.0（ASN.1 值域）、TS 38.211 V19.4.0（codeword→layer 表）

體例：
- 頁碼 p.N 為規格頁首印的頁碼；**PDF 檔頁序 = N + 1**（封面佔第 1 頁）。
- 「原文」為逐字引用（`>`）。pdftotext 對數學符號會亂碼，凡含公式/表格者已用 PDF 頁面目視核對，公式以純文字改寫並標 `[式]`。
- 文中出現的「…」表示為了篇幅省略的原文片段，未改動其餘字句。
- 查無出處者寫「未找到」；本文件不補推測值。
- 「P1/P2/P3」三個名詞**未出現在上述任何一份規範**（屬 TR 38.802 研究階段與業界用語，不在本資料夾）；本文件只以規範中的 `repetition` on/off 語意去對應，並標明屬詮釋。

---

## A. TS 38.214 — TCI state / QCL / beam 指示（§5.1.5）

### [214-001] QCL-Type A/B/C/D 定義
- 出處：TS 38.214 V19.4.0 §5.1.5, p.50
- 原文：
  > The quasi co-location types corresponding to each DL RS are given by the higher layer parameter qcl-Type in QCL-Info and may take one of the following values:
  > - 'typeA': {Doppler shift, Doppler spread, average delay, delay spread}
  > - 'typeB': {Doppler shift, Doppler spread}
  > - 'typeC': {Doppler shift, average delay}
  > - 'typeD': {Spatial Rx parameter}
- 型別：ENUM {typeA, typeB, typeC, typeD}
- 說明：typeD（Spatial Rx parameter）即「beam」的 QCL；A/B/C 是時頻大尺度參數。

### [214-002] 一個 TCI-State 最多兩個 DL RS，且 QCL type 不可相同
- 出處：TS 38.214 V19.4.0 §5.1.5, p.50
- 原文：
  > The UE can be configured with a list of up to M TCI-State configurations within the higher layer parameter PDSCH-Config to decode PDSCH according to a detected PDCCH with DCI intended for the UE and the given serving cell, where M depends on the UE capability maxNumberConfiguredTCIstatesPerCC. Each TCI-State contains parameters for configuring a quasi co-location relationship between one or two downlink reference signals and the DM-RS ports of the PDSCH, the DM-RS port of PDCCH or the CSI-RS port(s) of a CSI-RS resource. … For the case of two DL RSs, the QCL types shall not be the same, regardless of whether the references are to the same DL RS or different DL RSs.
- 數值：M = UE 能力 `maxNumberConfiguredTCIstatesPerCC`；每個 TCI-State 含 1 或 2 個 DL RS（qcl-Type1 / qcl-Type2）
- 補充（S331-003）：ASN.1 上限 `maxNrofTCI-States INTEGER ::= 128`（TS 38.331 p.1661）
- 說明：legacy（Rel-15/16）TCI 設定數上限由 UE 能力決定，ASN.1 硬上限 128。

### [214-003] Unified TCI（Rel-17）：dl-OrJointTCI-StateList 最多 128 個
- 出處：TS 38.214 V19.4.0 §5.1.5, p.50
- 原文：
  > The UE can be configured with a list of up to 128 TCI-State configurations, within the higher layer parameter dl-OrJointTCI-StateList in PDSCH-Config for providing a reference signal for the quasi co-location for DM-RS of PDSCH and DM-RS of PDCCH in a BWP/CC, for CSI-RS, and to provide a reference signal with qcl-Type set to 'typeD', if applicable, for determining UL TX spatial filter for dynamic-grant and configured-grant based PUSCH and PUCCH resource in a BWP/CC, and SRS.
- 數值：≤ 128 個 TCI-State
- 說明：unified TCI 讓同一個 indicated TCI 同時決定 PDSCH/PDCCH/CSI-RS 的 DL QCL 與 PUSCH/PUCCH/SRS 的 UL spatial filter。

### [214-004] MAC CE 啟用：最多 8 個 TCI state（或 pair）對應到 DCI TCI 欄位 codepoint
- 出處：TS 38.214 V19.4.0 §5.1.5, p.51
- 原文：
  > The UE receives an activation command, as described in clause 6.1.3.14 of [10, TS 38.321], or 6.1.3.47 of [10, TS 38.321], used to map up to 8 TCI states and/or pairs of TCI states, with one TCI state for DL channels/signals and/or one TCI state for UL channels/signals to the codepoints of the DCI field 'Transmission Configuration Indication' for one or for a set of CCs/DL BWPs.
- 數值：≤ 8 個 codepoint（DCI TCI 欄位 3 bits 的推論見 [214-004a]）
- 相關：[321-005]、[321-006]
- [214-004a] DCI 欄位位元寬：38.214 未直接寫 bit 數；**未找到**（應在 TS 38.212 §7.3.1.2.2，不在本文件範圍）。

### [214-005] Unified TCI：DCI 1_1/1_2/1_3 指示 TCI（可不帶 DL assignment）
- 出處：TS 38.214 V19.4.0 §5.1.5, p.51
- 原文：
  > When tci-PresentInDCI is set as 'enabled' or tci-PresentDCI-1-2 is configured for the CORESET, a UE configured with dl-OrJointTCI-StateList with activated TCI-State or ul-TCI-StateList with activated TCI-UL-State receives DCI format 1_1/1_2/1_3 providing indicated TCI-State(s) and/or TCI-UL-State(s) … The DCI format 1_1/1_2 can be with or without, if applicable, DL assignment. If the DCI format 1_1/1_2 is without DL assignment, the UE can assume the following:
  > - CS-RNTI is used to scramble the CRC for the DCI
  > - … RV = all '1's … MCS = all '1's … NDI = 0 …
- 說明：沒有排程資料的「純 beam 指示 DCI」以 CS-RNTI 加擾並以特定欄位值辨識。

### [214-006] Unified TCI：初始設定後、尚未套用 indicated TCI 前的預設 QCL
- 出處：TS 38.214 V19.4.0 §5.1.5, p.51
- 原文：
  > Otherwise, the UE assumes that DM-RS of PDSCH and DM-RS of PDCCH, WUS, and the CSI-RS applying the indicated TCI state are quasi co-located with the SS/PBCH block the UE identified during the initial access procedure with respect to qcl-Type set to 'typeA', and when applicable, also with respect to qcl-Type set to 'typeD'.
- 說明：在 LTM 等特例之外，預設 beam = 初始接入時 UE 選到的 SSB。UL 對應規則（p.52）：UL TX spatial filter 與 RAR UL grant 排程的 PUSCH / MsgA PUSCH 相同。

### [214-007] Beam application time（beamAppTime）
- 出處：TS 38.214 V19.4.0 §5.1.5, p.52（PDF 第 53 頁核對符號）
- 原文：
  > When a UE configured with dl-OrJointTCI-StateList would transmit a PUCCH with positive HARQ-ACK or a PUSCH with positive HARQ-ACK corresponding to the DCI carrying the TCI State indication and without DL assignment, or corresponding to one or more PDSCH(s) scheduled by the DCI carrying the TCI State indication, and if the indicated TCI State(s) is/are different from the previously indicated one(s), the indicated TCI-State(s) and/or TCI-UL-State(s) should be applied starting from the first slot that is at least *beamAppTime* symbols after the last symbol of the PUCCH or the PUSCH … The first slot and the *beamAppTime* symbols are both determined on the active BWP with the smallest SCS among the BWP(s) from the CCs applying the indicated TCI-State(s) or TCI-UL-State(s) …
- 數值（S331-006，TS 38.331 p.1053）：`beamAppTime-r17 ENUMERATED {n1, n2, n4, n7, n14, n28, n42, n56, n70, n84, n98, n112, n224, n336, spare2, spare1}`，單位 symbol（38.331 p.1055：「The value n1 means 1 symbol, n2 two symbols and so on」）
- 說明：新 beam 在 **正確 ACK 後 ≥ beamAppTime 個 symbol 的第一個 slot** 生效；以最小 SCS 的 active BWP 計算。

### [214-008] Legacy MAC CE 啟用生效時間（3 ms 規則）
- 出處：TS 38.214 V19.4.0 §5.1.5, p.53（PDF 第 54 頁核對）
- 原文：
  > When the UE would transmit a PUCCH with HARQ-ACK information in slot n corresponding to the PDSCH carrying the activation command, the indicated mapping between TCI states and codepoints of the DCI field 'Transmission Configuration Indication' should be applied starting from the first slot that is after slot n + 3·N_slot^{subframe,μ} + (2^μ / 2^{μ_Kmac})·k_mac where μ is the SCS configuration for the PUCCH …
- [式] 生效 slot > n + 3·N_slot^{subframe,μ} + 2^μ/2^{μ_Kmac}·k_mac（k_mac 未提供時 = 0；FR1 與 FR2-NTN 的 μ_Kmac = 0）
- 說明：地面網路 k_mac = 0 時即「ACK 後 3 ms」。

### [214-009] Legacy：尚未收到 MAC CE 前的預設 QCL
- 出處：TS 38.214 V19.4.0 §5.1.5, p.54
- 原文：
  > Otherwise, the UE may assume that the DM-RS ports of PDSCH of a serving cell are quasi co-located with the SS/PBCH block determined in the initial access procedure with respect to qcl-Type set to 'typeA', and when applicable, also with respect to qcl-Type set to 'typeD'.

### [214-010] TCI 欄位存在 / timeDurationForQCL 門檻
- 出處：TS 38.214 V19.4.0 §5.1.5, p.54
- 原文：
  > If a UE is not provided dl-OrJointTCI-StateList-r17, and if a PDSCH is scheduled by a DCI format having the TCI field present, the TCI field in DCI in the scheduling component carrier points to the activated TCI states in the scheduled component carrier or DL BWP, the UE shall use the TCI-State according to the value of the 'Transmission Configuration Indication' field in the detected PDCCH with DCI for determining PDSCH antenna port quasi co-location. The UE may assume that the DM-RS ports of PDSCH of a serving cell are quasi co-located with the RS(s) in the TCI state with respect to the QCL type parameter(s) given by the indicated TCI state if the time offset between the reception of the DL DCI and the corresponding PDSCH is equal to or greater than a threshold timeDurationForQCL, where the threshold is based on reported UE capability [13, TS 38.306].
- 型別：`timeDurationForQCL` 為 UE 能力（TS 38.306）
- 說明：排程偏移 ≥ timeDurationForQCL 才依 DCI 的 TCI 收 PDSCH；不帶 TCI 欄位的 DCI 則沿用 CORESET 的 TCI（同頁）。

### [214-011] 排程偏移 < timeDurationForQCL 時的預設 beam
- 出處：TS 38.214 V19.4.0 §5.1.5, p.55
- 原文：
  > … if the offset between the reception of the DL DCI and the corresponding PDSCH is less than the threshold timeDurationForQCL and at least one configured TCI state for the serving cell of scheduled PDSCH contains qcl-Type set to 'typeD',
  > - the UE may assume that the DM-RS ports of PDSCH(s) of a serving cell are quasi co-located with the RS(s) with respect to the QCL parameter(s) used for PDCCH quasi co-location indication of the CORESET associated with a monitored search space with the lowest controlResourceSetId in the latest slot in which one or more CORESETs within the active BWP of the serving cell are monitored by the UE. In this case, if the qcl-Type is set to 'typeD' of the PDSCH DM-RS is different from that of the PDCCH DM-RS with which they overlap in at least one symbol, the UE is expected to prioritize the reception of PDCCH associated with that CORESET.
- 說明：UE 來不及切 beam 時，預設用「最近監聽 slot 中 controlResourceSetId 最小之 CORESET」的 beam；typeD 衝突時 PDCCH 優先。

---

## B. TS 38.214 — PDSCH 層數 / codeword / precoding / DM-RS（§5.1）

### [214-020] PDSCH 只有一種傳輸方案：最多 8 層，port 1000–1023
- 出處：TS 38.214 V19.4.0 §5.1.1 / §5.1.1.1, p.18
- 原文：
  > Only one transmission scheme is defined for the PDSCH, and is used for all PDSCH transmissions.
  > For transmission scheme 1 of the PDSCH, the UE may assume that a gNB transmission on the PDSCH would be performed with up to 8 transmission layers on antenna ports 1000-1023 as defined in Clause 7.3.1.4 of [4, TS 38.211], subject to the DM-RS reception procedures in Clause 5.1.6.2.
- 數值：layers ∈ [1, 8]；DM-RS port 1000–1023

### [214-021] Codeword 數 vs 層數
- 38.214 §5.1：**未找到**明文的「1–4 層 1 CW、5–8 層 2 CW」規則。該規則出處如下：
  - [300-001]（TS 38.300 §5.2.1, p.48）："The number of SU-MIMO code words is one for 1-4 layer transmissions and two for 5-8 layer transmissions."
  - [S211-001]（TS 38.211 V19.4.0 §7.3.1.3, Table 7.3.1.3-1, p.124）：Codeword-to-layer mapping，layers 1–4 → 1 codeword；5–8 → 2 codewords（5 層＝CW0 2 層 + CW1 3 層；6＝3+3；7＝3+4；8＝4+4）。
  - [S331-007]（TS 38.331 p.1051）：`maxNrofCodeWordsScheduledByDCI ENUMERATED {n1, n2}`。
- 38.214 相關句（§5.1, p.15，multi-DCI 重疊 PDSCH 情境）：
  > When the UE is scheduled with full/partially-overlapped PDSCHs in time and frequency domain, the UE can be scheduled with at most two codewords simultaneously.

### [214-022] PRB bundling：precoding 粒度 {2, 4, wideband}
- 出處：TS 38.214 V19.4.0 §5.1.2.3, p.32
- 原文：
  > A UE may assume that precoding granularity is P′BWP,i consecutive resource blocks in the frequency domain. P′BWP,i can be equal to one of the values among {2, 4, wideband}.
  > If P′BWP,i is determined as "wideband", the UE is not expected to be scheduled with non-contiguous PRBs and the UE may assume that the same precoding is applied to the allocated resource associated with a same TCI state or a same QCL assumption.
  > The UE may assume the same precoding is applied for any downlink contiguous allocation of PRBs in a PRG.
  > If a UE is scheduled a PDSCH with DCI format 1_0 or 4_0 for broadcast or 4_1 for multicast, the UE shall assume that P′BWP,i is equal to 2 PRBs.
- 數值：PRG ∈ {2, 4, wideband}（PRB）；DCI 1_0 固定 2 PRB
- 說明：同一 PRG 內 precoder 相同，UE 可跨 PRB 做通道估計內插。

### [214-023] DM-RS 接收：未設定前的預設
- 出處：TS 38.214 V19.4.0 §5.1.6.2, p.65
- 原文：
  > When receiving PDSCH scheduled by DCI format 1_0, 4_0, or 4_1, or receiving PDSCH before dedicated higher layer configuration of any of the parameters dmrs-AdditionalPosition, maxLength and dmrs-Type, the UE shall assume that the PDSCH is not present in any symbol carrying DM-RS except for PDSCH with allocation duration of 2 symbols with PDSCH mapping type B …, and a single symbol front-loaded DM-RS of configuration type 1 on DM-RS port 1000 is transmitted, and that all the remaining orthogonal antenna ports are not associated with transmission of PDSCH to another UE …
- 說明：預設 = 單層（port 1000）、type 1、單 symbol front-loaded；同頁續寫 mapping type A/B 預設 `dmrs-AdditionalPosition='pos2'`（p.66）。

### [214-024] DM-RS 設定：maxLength / dmrs-AdditionalPosition；port 由 DCI 天線埠欄位指示
- 出處：TS 38.214 V19.4.0 §5.1.6.2, p.66
- 原文：
  > - if maxLength is set to 'len1', single-symbol DM-RS can be scheduled for the UE by DCI, and the UE can be configured with a number of additional DM-RS for PDSCH by higher layer parameter dmrs-AdditionalPosition, which can be set to 'pos0', 'pos1', 'pos2' or 'pos3'.
  > - if maxLength is set to 'len2', both single-symbol DM-RS and double symbol DM-RS can be scheduled for the UE by DCI, and the UE can be configured with a number of additional DM-RS for PDSCH by higher layer parameter dmrs-AdditionalPosition, which can be set to 'pos0' or 'pos1'.
  > A UE may be scheduled with a number of DM-RS ports by the antenna port index in DCI format 1_1 as described in Clause 7.3.1.2 of [5, TS 38.212].
- 數值：len1 → pos0..pos3；len2 → pos0..pos1
- 說明：層數（= DM-RS port 數）由 DCI「Antenna port(s)」欄位（38.212 表 7.3.1.2.2-x）指示；同頁起列出 1 CW / 2 CW 時哪些「剩餘正交 port」可視為未被其他 UE 使用（MU-MIMO 假設）。

---

## C. TS 38.214 — CSI framework（§5.2.1）

### [214-030] CSI 可包含的量
- 出處：TS 38.214 V19.4.0 §5.2.1, p.81
- 原文：
  > CSI may consist of Channel Quality Indicator (CQI), precoding matrix indicator (PMI), CSI-RS resource indicator (CRI), SS/PBCH Block Resource indicator (SSBRI), layer indicator (LI), rank indicator (RI), L1-RSRP, L1-SINR, CapabilityIndex, time-domain channel properties (TDCP), L1-SRS-RSRP, SRS-RSRP-MRI, L1-CLI-RSSI or CLI-RSSI-MRI.CSI, prediction accuracy indicator (CSI-PAI), predicted-CRI (P-CRI), predicted-SSBRI (P-SSBRI), predicted-L1-RSRP (P-L1-RSRP), or reference signal prediction accuracy indicator (RS-PAI), CJT calibration of delay offset (CJTC-Dd), CJT calibration of frequency offset (CJTC-F), CJT calibration of delay and frequency offsets (CJTC-Dd-F) or CJT calibration of phase offset (CJTC-P).

### [214-031] CSI-ReportConfig / CSI-ResourceConfig / trigger state 關係
- 出處：TS 38.214 V19.4.0 §5.2.1, p.81–82
- 原文：
  > … a UE is configured by higher layers with N≥1 CSI-ReportConfig Reporting Settings and/or X≥1 ltm-CSI-ReportConfig Reporting Settings, M≥1 CSI-ResourceConfig Resource Settings and/or Y≥1 LTM-CSI-ResourceConfig Resource Settings, and one or two list(s) of trigger states (given by the higher layer parameters CSI-AperiodicTriggerStateList and CSI-SemiPersistentOnPUSCH-TriggerStateList). Each trigger state in CSI-AperiodicTriggerStateList contains a list of associated CSI-ReportConfigs or one associated LTM-CSI-ReportConfig indicating the Resource Set IDs for channel and optionally for interference …
- 結構：`CSI-ReportConfig (N≥1)` ──引用── `CSI-ResourceConfig (M≥1)` ──含── `csi-RS-ResourceSetList (S≥1 個 NZP-CSI-RS / SSB / CSI-IM set)`；aperiodic 由 trigger state 串接。

### [214-032] Reporting setting 內容與時域行為（reportConfigType）
- 出處：TS 38.214 V19.4.0 §5.2.1.1, p.82
- 原文：
  > Each Reporting Setting CSI-ReportConfig is associated with a single downlink BWP (indicated by higher layer parameter BWP-Id) given in the associated CSI-ResourceConfig for channel measurement and contains the parameter(s) for one CSI reporting band: codebook configuration including codebook subset restriction, time-domain behavior, frequency granularity for CQI and PMI, measurement restriction configurations, and the CSI-related quantities to be reported by the UE …
  > The time domain behavior of the CSI-ReportConfig is indicated by the higher layer parameter reportConfigType and can be set to 'aperiodic', 'semiPersistentOnPUCCH', 'semiPersistentOnPUSCH', or 'periodic'.
- 數值：reportConfigType ∈ {aperiodic, semiPersistentOnPUCCH, semiPersistentOnPUSCH, periodic}

### [214-033] Resource setting：resourceType 與 S 值
- 出處：TS 38.214 V19.4.0 §5.2.1.2, p.82–83
- 原文：
  > Each CSI Resource Setting CSI-ResourceConfig contains a configuration of a list of S≥1 CSI Resource Sets (given by higher layer parameter csi-RS-ResourceSetList), where the list is comprised of references to either or both of NZP CSI-RS resource set(s) and SS/PBCH block set(s) or the list is comprised of references to CSI-IM resource set(s) …
  > The time domain behavior of the CSI-RS resources within a CSI Resource Setting are indicated by the higher layer parameter resourceType and can be set to aperiodic, periodic, or semi-persistent. For periodic and semi-persistent CSI Resource Settings, when the UE is configured with groupBasedBeamReporting-v1710 or groupBasedBeamReporting-v1800, the number of CSI Resource Sets configured is S=2, otherwise the number of CSI-RS Resource Sets configured is limited to S=1, except … TDCP … CJTC …
  > All CSI Resource Settings linked to a CSI Report Setting shall have the same time domain behavior.
- 數值：periodic / SP 的 S = 1（group-based v1710/v1800 時 S = 2）

### [214-034] CSI 參數相依順序
- 出處：TS 38.214 V19.4.0 §5.2.1.4, p.84
- 原文：
  > - LI shall be calculated conditioned on the reported CQI, PMI, RI and CRI
  > - CQI shall be calculated conditioned on the reported PMI, RI and CRI
  > - PMI shall be calculated conditioned on the reported RI and CRI
  > - RI shall be calculated conditioned on the reported CRI.
- 說明：計算順序 CRI → RI → PMI → CQI → LI。

### [214-035] Periodic / semi-persistent / aperiodic 組合（Table 5.2.1.4-1）
- 出處：TS 38.214 V19.4.0 §5.2.1.4, Table 5.2.1.4-1, p.84–85
- 原文：
  > The Reporting configuration for CSI can be aperiodic (using PUSCH), periodic (using PUCCH) or semi-persistent (using PUCCH, and DCI activated PUSCH). The CSI-RS Resources can be periodic, semi-persistent, or aperiodic.
- 表（轉錄）：

| CSI-RS \ Report | Periodic | Semi-Persistent | Aperiodic |
|---|---|---|---|
| Periodic CSI-RS | No dynamic triggering/activation | PUCCH：MAC CE（38.321 §6.1.3.16）啟用；PUSCH：DCI 觸發 | DCI 觸發；可另用 subselection MAC CE（§6.1.3.13） |
| Semi-Persistent CSI-RS | Not Supported | 同上 | 同上 |
| Aperiodic CSI-RS | Not Supported | Not Supported | DCI 觸發；可另用 subselection MAC CE |

- 補充（§5.2.1.5.2, p.119）：SP on PUSCH 由 `SP-CSI-RNTI` 加擾的 DCI 啟用；SP on PUCCH 由 MAC CE（6.1.3.16）啟用，生效於 ACK slot n 之後 `n + 3·N_slot^{subframe,μ}` 的第一個 slot。SP CSI-RS 由 MAC CE（6.1.3.12/6.1.3.12a）啟用，同樣含 QCL（TCI-State 參照）。

### [214-036] CRI 報告與 repetition 的關係
- 出處：TS 38.214 V19.4.0 §5.2.1.4, p.85
- 原文：
  > When the UE is configured with higher layer parameter NZP-CSI-RS-ResourceSet and when the higher layer parameter repetition is set to 'off', the UE shall determine a CRI from the supported set of CRI values as defined in Clause 6.3.1.1.2 of [5, TS 38.212] and report the number in each CRI report. When the higher layer parameter repetition for a CSI-RS Resource Set for channel measurement is set to 'on', CRI for the CSI-RS Resource Set for channel measurement is not reported.
- 說明：repetition=on → 不報 CRI（gNB 同一 beam 重複，供 UE 掃 Rx beam；工程慣稱 P3）；repetition=off → 報 CRI（gNB 掃不同 Tx beam；工程慣稱 P2）。「P2/P3」為詮釋，規範未使用此名。

### [214-037] repetition on/off 的空間濾波語意
- 出處：TS 38.214 V19.4.0 §5.1.6.1.2, p.64
- 原文：
  > If a UE is configured with a NZP-CSI-RS-ResourceSet configured with the higher layer parameter repetition set to 'on', the UE may assume that the CSI-RS resources, described in Clause 5.2.2.3.1, within the NZP-CSI-RS-ResourceSet are transmitted with the same downlink spatial domain transmission filter, where the CSI-RS resources in the NZP-CSI-RS-ResourceSet are transmitted in different OFDM symbols. If repetition is set to 'off', the UE shall not assume that the CSI-RS resources within the NZP-CSI-RS-ResourceSet are transmitted with the same downlink spatial domain transmission filter.
- 同頁限制：
  > … the UE can only be configured with the same number (1 or 2) of ports with the higher layer parameter nrofPorts for all CSI-RS resources within the set.
- 數值：`repetition ENUMERATED {on, off}`（S331-008，TS 38.331 p.1024）；beam-management CSI-RS 每 resource 1 或 2 port
- [214-038] repetition 可設定的條件（§5.2.2.3.1, p.193）：
  > repetition in NZP-CSI-RS-ResourceSet … can be configured only when the higher layer parameter reportQuantity associated with all the reporting settings linked with the CSI-RS resource set is set to 'cri-RSRP', 'cri-SINR', 'cri-RSRP- Index', 'cri-SINR- Index' or 'none'.

### [214-039] reportQuantity 值域與語意
- 出處：TS 38.214 V19.4.0 §5.2.1.4.2, p.91–93
- 原文（值域）：
  > A UE may be configured with a CSI-ReportConfig with the higher layer parameter reportQuantity set to either 'none', 'cri-RI-PMI-CQI ', 'cri-RI-i1', 'cri-RI-i1-CQI', 'cri-RI-CQI', 'cri-RSRP', 'cri-SINR', 'ssb-Index-RSRP', 'ssb-Index-SINR', 'cri-RI-LI-PMI-CQI', 'cri-RSRP- Index', 'ssb-Index-RSRP- Index', 'cri-SINR- Index', 'ssb-Index-SINR- Index', 'tdcp', 'cli-SRS-RSRP', 'cli-RSSI', 'p-CRI-r19', 'p-CRI-RSRP-r19', 'p-SSB-Index-r19', 'p-SSB-Index-RSRP-r19', 'rs-PAI-r19', 'csi-PAI-r19', 'noneCSI-r19', 'noneBM-r19', 'cjtc-Dd', 'cjtc-F', 'cjtc-Dd-F' or 'cjtc-P'.
- 各值意義（摘自同節，p.92–93）：

| reportQuantity | 規範語意（摘要，出處同節） |
|---|---|
| none / none-csi-r19 / none-bm-r19 | 「the UE shall not report any quantity」（p.92） |
| cri-RI-PMI-CQI、cri-RI-LI-PMI-CQI | 報寬頻或子頻 preferred precoder（依 §5.2.2.2）（p.92） |
| cri-RI-i1 | 需 typeI-SinglePanel + widebandPMI；只報寬頻 i1（p.92） |
| cri-RI-i1-CQI | 同上，CQI 以同 i1、隨機 i2 的 Np 個 precoder 計算，PRG 由 pdsch-BundleSizeForCSI 決定（p.92） |
| cri-RI-CQI | 非 PMI 回報；以 non-PMI-PortIndication 指定每 rank 用哪些 port，precoder 視為單位矩陣乘 1/√ν（p.92–93） |
| cri-RSRP / ssb-Index-RSRP（及 -Index 變形） | Beam 報告，見 [214-040] |
| cri-SINR / ssb-Index-SINR（及 -Index 變形） | L1-SINR beam 報告（p.94） |
| p-CRI-r19 / p-CRI-RSRP-r19 / p-SSB-Index-r19 / p-SSB-Index-RSRP-r19 | AI/ML 預測 beam，見 [214-045] |
| -Index 後綴 | 另報「UE capability value set index（最大 SRS port 數）」（p.103, p.105） |

### [214-040] cri-RSRP / ssb-Index-RSRP：beam 數與 groupBasedBeamReporting
- 出處：TS 38.214 V19.4.0 §5.2.1.4.2, p.93
- 原文：
  > - if the UE is configured with the higher layer parameter groupBasedBeamReporting set to 'disabled', the UE is not required to update measurements for more than 64 CSI-RS and/or SSB resources, and the UE shall report in a single report nrofReportedRS or nrofReportedRS-r19 (higher layer configured) different CRI or SSBRI for each report setting …
  > - if the UE is configured with the higher layer parameter groupBasedBeamReporting set to 'enabled', the UE is not required to update measurements for more than 64 CSI-RS and/or SSB resources, and the UE shall report in a single reporting instance two different CRI or SSBRI for each report setting, where CSI-RS and/or SSB resources can be received simultaneously by the UE either with a single spatial domain receive filter, or with multiple simultaneous spatial domain receive filters.
  > - if the UE is configured with the higher layer parameter groupBasedBeamReporting-v1710 … the UE shall report in a single reporting instance nrofReportedGroups-r17, group(s) of two CRIs or SSBRIs selecting one CSI-RS or SSB from each of the two CSI Resource Sets …
- 數值：量測上限 64 個 resource；disabled → nrofReportedRS 個；enabled → 2 個（可同時接收）
- S331-001（TS 38.331 p.842）：`nrofReportedRS ENUMERATED {n1, n2, n3, n4}` → **一次最多 4 個 beam**（legacy 欄位）。`nrofReportedRS-r19` 值域：未找到於本次核對範圍（38.214 只說可等於 resource set 大小的特例）。

### [214-041] L1-RSRP 資源數上限
- 出處：TS 38.214 V19.4.0 §5.2.1.4.3, p.102
- 原文：
  > - the UE may be configured with CSI-RS resources, SS/PBCH Block resources or both CSI-RS and SS/PBCH block resources, when resource-wise quasi co-located with 'type C' and 'typeD' when applicable.
  > - the UE may be configured with CSI-RS resource setting up to 16 CSI-RS resource sets having up to 64 resources within each set. The total number of different CSI-RS resources over all resource sets is no more than 128.
- 數值：≤ 16 sets；每 set ≤ 64 resources；總計 ≤ 128
- S331-004（p.1657/1658）：`maxNrofNZP-CSI-RS-ResourcesPerSet = 64`、`maxNrofCSI-SSB-ResourcePerSet = 64`

### [214-042] L1-RSRP 位元寬與差分
- 出處：TS 38.214 V19.4.0 §5.2.1.4.3, p.102–103
- 原文：
  > For L1-RSRP reporting, if the higher layer parameter nrofReportedRS in CSI-ReportConfig is configured to be one, … the reported L1-RSRP value is defined by a 7-bit value in the range [-140, -44] dBm with 1dB step size, if the higher layer parameter nrofReportedRS is configured to be larger than one, or if the higher layer parameter groupBasedBeamReporting is configured as 'enabled', … the UE shall use differential L1-RSRP based reporting, where the largest measured value of L1-RSRP is quantized to a 7-bit value in the range [-140, -44] dBm with 1dB step size, and the differential L1-RSRP is quantized to a 4-bit value. The differential L1-RSRP value is computed with 2 dB step size with a reference to the largest measured L1-RSRP value which is part of the same L1-RSRP reporting instance. The mapping between the reported L1-RSRP value and the measured quantity is described in [11, TS 38.133].
- 數值：絕對值 7 bit，[-140, -44] dBm，1 dB；差分 4 bit，2 dB 步階，以同次最大值為參考
- 說明：報表值到 dBm 的對映表在 TS 38.133（本資料夾無）→ 對映表**未找到**。

### [214-043] L1-SINR 位元寬與差分
- 出處：TS 38.214 V19.4.0 §5.2.1.4.4, p.105
- 原文：
  > - for channel measurement, the UE may be configured with CSI-RS resource setting with up to 16 resource sets, with a total of up to 64 CSI-RS resources or up to 64 SS/PBCH Block resources.
  > For L1-SINR reporting, if the higher layer parameter nrofReportedRS in CSI-ReportConfig is configured to be one, the reported L1-SINR value is defined by a 7-bit value in the range [-23, 40] dB with 0.5 dB step size, and if … larger than one, or if … groupBasedBeamReporting is configured as 'enabled', the UE shall use differential L1-SINR based reporting, where the largest measured value of L1-SINR is quantized to a 7-bit value in the range [-23, 40] dB with 0.5 dB step size, and the differential L1-SINR is quantized to a 4-bit value. The differential L1-SINR is computed with 1 dB step size …
- 數值：7 bit，[-23, 40] dB，0.5 dB；差分 4 bit，1 dB

### [214-044] CRI / SSBRI 的索引定義
- 出處：TS 38.214 V19.4.0 §5.2.1.4.2, p.96 與 p.101
- 原文（CRI, p.96）：
  > … the UE shall derive the CSI parameters other than CRI conditioned on the reported CRI, where CRI k (k ≥ 0) corresponds to the configured (k+1)-th entry of associated nzp-CSI-RS-Resources in the corresponding NZP-CSI-RS-ResourceSet for channel measurement, and (k+1)-th entry of associated csi-IM-Resource in the corresponding csi-IM-ResourceSet (if configured) …
- 原文（SSBRI, p.101）：
  > If the UE is configured with a CSI-ReportConfig with the higher layer parameter reportQuantity set to 'ssb-Index-RSRP' or 'ssb-Index-RSRP- Index', the UE shall report SSBRI, where SSBRI k (k ≥ 0) corresponds to the configured (k+1)-th entry of the associated csi-SSB-ResourceList in the corresponding CSI-SSB-ResourceSet.
- 說明：CRI/SSBRI 是「set 內的序號」，不是 NZP-CSI-RS-ResourceId 或 SSB index 本身。
- 註：使用者清單寫「§5.2.2.5」，實際 CRI/SSBRI 定義在 §5.2.1.4.2；§5.2.2.5 是 CSI reference resource 定義（p.194–195）。

### [214-045] Rel-19 AI/ML beam 預測（P-CRI / P-SSBRI / P-L1-RSRP）
- 出處：TS 38.214 V19.4.0 §5.2.1.4.1, p.88；§5.2.1.4.2, p.93；§5.2.1.4.3a, p.103–104
- 原文（p.88）：
  > if the reportQuantity-r19 is set to 'p-CRI-r19', 'p-CRI-RSRP-r19', 'p-SSB-Index-r19', or 'p-SSB-Index-RSRP-r19', the first one Resource Setting (given by higher layer parameter resourcesForChannelMeasurement) is for channel measurement and the second one (given by higher layer parameter resourcesForChannelPrediction) is for predicted RS quantities reporting.
- 原文（p.93）：
  > - the UE is not required to update measurements for more than 64 CSI-RS or SSB resources given by resourcesForChannelMeasurement and is not expected to predict for more than 64 CSI-RS or SSB resources given by resourcesForChannelPrediction-r19,
- 原文（p.103–104）：
  > For P-CRI or P-SSBRI reporting without P-L1-RSRP, the ranking information of the nrofReportedPredictedRS P-CRI or P-SSBRI (per time instance, if nrofTimeInstance is configured) is conveyed by the order of the P-CRIs or P-SSBRIs reported in the CSI report, where the first reported P-CRI or P-SSBRI ranks first.
  > … the largest predicted value of P-L1-RSRP is quantized to a 7-bit value in the range [-140, -44] dBm with 1dB step size, and the differential P-L1-RSRP is quantized to a 4-bit value. The differential P-L1-RSRP value is computed with 2 dB step size …
- 數值：量測集合 Set A（resourcesForChannelMeasurement）≤ 64；預測集合 Set B（resourcesForChannelPrediction）≤ 64；位元寬同 L1-RSRP；多時間點時另有 ⌈log2 N⌉ bit time instance indicator（p.104）
- 概述見 [300-006]。

---

## D. TS 38.214 — CQI、Codebook（§5.2.2.1–§5.2.2.2）

### [214-050] CQI 表
- 出處：TS 38.214 V19.4.0 §5.2.2.1, p.130
- 原文：
  > The CQI indices and their interpretations are given in Table 5.2.2.1-2 or Table 5.2.2.1-4 for reporting CQI based on QPSK, 16QAM and 64QAM. The CQI indices and their interpretations are given in Table 5.2.2.1-3 for reporting CQI based on QPSK, 16QAM, 64QAM and 256QAM. The CQI indices and their interpretations are given in Table 5.2.2.1-5 for reporting CQI based on QPSK, 16QAM, 64QAM, 256QAM and 1024 QAM.
- 同頁：目標 TB error probability 0.1（table1 / table2 / table4-r17）或 0.00001（table3）。

### [214-051] Type I Single-Panel：2 port
- 出處：TS 38.214 V19.4.0 §5.2.2.2.1, Table 5.2.2.2.1-1, p.133
- 原文：
  > For 2 antenna ports {3000, 3001} and the UE configured with higher layer parameter codebookType set to 'typeI-SinglePanel' each PMI value corresponds to a codebook index given in Table 5.2.2.2.1-1. The UE is configured with the higher layer parameter twoTX-CodebookSubsetRestriction. … Bits 0 to 3 are associated respectively with the codebook indices 0 to 3 for υ =1 layer, and bits 4 and 5 are associated respectively with the codebook indices 0 and 1 for υ =2 layers.
- 數值：rank ≤ 2；1 層 4 個 codeword、2 層 2 個；CBSR 6 bit

### [214-052] Type I Single-Panel：4–32 port、(N1,N2)/(O1,O2)
- 出處：TS 38.214 V19.4.0 §5.2.2.2.1, Table 5.2.2.2.1-2, p.133–135（PDF 第 136 頁核對表格）
- 原文：
  > For 4 antenna ports {3000, 3001, 3002, 3003}, 8 antenna ports …, 12 antenna ports …, 16 antenna ports …, 24 antenna ports …, and 32 antenna ports {3000, 3001, …, 3031}, and the UE configured with higher layer parameter codebookType set to 'typeI-SinglePanel', except when the number of layers υ ∈ {2, 3, 4} …, each PMI value corresponds to three codebook indices i1,1, i1,2, i2. When the number of layers υ ∈ {2, 3, 4}, each PMI value corresponds to four codebook indices i1,1, i1,2, i1,3, i2.
  > The codebooks for 1-8 layers are given respectively in Tables 5.2.2.2.1-5, 5.2.2.2.1-6, 5.2.2.2.1-7, 5.2.2.2.1-8, 5.2.2.2.1-9, 5.2.2.2.1-10, 5.2.2.2.1-11, and 5.2.2.2.1-12.
  > - The values of N1 and N2 are configured with the higher layer parameter n1-n2, respectively. The supported configurations of (N1, N2) for a given number of CSI-RS ports and the corresponding values of (O1, O2) are given in Table 5.2.2.2.1-2. The number of CSI-RS ports, PCSI-RS, is 2N1N2.
  > - UE shall only use i1,2 = 0 and shall not report i1,2 if the value of N2 is 1.
- Table 5.2.2.2.1-2（PDF 目視核對）：

| P_CSI-RS | (N1,N2) | (O1,O2) |
|---|---|---|
| 4 | (2,1) | (4,1) |
| 8 | (2,2) | (4,4) |
| 8 | (4,1) | (4,1) |
| 12 | (3,2) | (4,4) |
| 12 | (6,1) | (4,1) |
| 16 | (4,2) | (4,4) |
| 16 | (8,1) | (4,1) |
| 24 | (4,3) | (4,4) |
| 24 | (6,2) | (4,4) |
| 24 | (12,1) | (4,1) |
| 32 | (4,4) | (4,4) |
| 32 | (8,2) | (4,4) |
| 32 | (16,1) | (4,1) |

- 最大 rank：8（codebook 表 1–8 層）；ri-Restriction 8 bit（[214-054]）
- codebookMode：1 或 2（Table 5.2.2.2.1-5/-6 以 codebookMode=1 / =2 分列；3 層以上表格為「codebookMode = 1-2」）

### [214-053] Type I SP 公式
- 出處：TS 38.214 V19.4.0 §5.2.2.2.1, p.134；Table 5.2.2.2.1-5, p.135（PDF 核對）
- [式]
  - φ_n = e^{jπn/2}；θ_p = e^{jπp/4}
  - u_m = [1, e^{j2πm/(O2N2)}, …, e^{j2πm(N2−1)/(O2N2)}]（N2>1）；u_m = 1（N2=1）
  - v_{l,m} = [u_m, e^{j2πl/(O1N1)}u_m, …, e^{j2πl(N1−1)/(O1N1)}u_m]^T
  - ṽ_{l,m} = [u_m, e^{j4πl/(O1N1)}u_m, …, e^{j4πl(N1/2−1)/(O1N1)}u_m]^T（3/4 層、≥16 port 使用）
  - 1 層（codebookMode=1）：W^{(1)}_{l,m,n} = (1/√P_CSI-RS)·[v_{l,m}; φ_n v_{l,m}]，i1,1 ∈ {0..N1O1−1}，i1,2 ∈ {0..N2O2−1}，i2 ∈ {0,1,2,3}
- 說明：W 為兩極化向量堆疊（上半 = 極化 1，下半 = 極化 2 乘 co-phase φ_n），即 DFT beam × co-phasing。規範不以「W = W1·W2」矩陣乘積形式書寫（全文 grep 無 "W1W2"），寫成 W1W2 屬文獻慣例。

### [214-054] Type I SP：RI 限制與 CBSR
- 出處：TS 38.214 V19.4.0 §5.2.2.2.1, p.134
- 原文：
  > The bitmap parameter n1-n2 forms the bit sequence a_{Ac−1}, ..., a1, a0 where a0 is the LSB and a_{Ac−1} is the MSB and where a bit value of zero indicates that PMI reporting is not allowed to correspond to any precoder associated with the bit. The number of bits is given by Ac = N1O1N2O2.
  > For UE configured with higher layer parameter codebookType set to 'typeI-SinglePanel', the bitmap parameter typeI-SinglePanel-ri‑Restriction forms the bit sequence r7, ..., r1, r0 where r0 is the LSB and r7 is the MSB. When ri is zero, i ∈ {0,1, …, 7}, PMI and RI reporting are not allowed to correspond to any precoder associated with υ = i +1 layers.
- 數值：CBSR 長度 Ac = N1·O1·N2·O2；RI 限制 8 bit
- 註：使用者清單寫「§5.2.2.3 RI/PMI 限制、CBSR」；實際 RI/CBSR 規則分散在各 codebook 小節（§5.2.2.2.x），§5.2.2.3 是 NZP CSI-RS 參考信號設定（見 [214-070]）。

### [214-055] Refined Type I Single-Panel（Rel-19，48/64/128 port）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.1a, Table 5.2.2.2.1a-1/-2, p.139–140（PDF 第 140–141 頁核對）
- 原文：
  > For 48, 64 and 128 antenna ports, obtained by aggregating K CSI-RS resources for channel measurement, and the UE configured with higher layer parameter codebookType set to 'typeI-SinglePanel-r19'
  > - The values of N1 and N2 are configured with the higher layer parameter n1-n2-r19. The supported configurations of (N1, N2), for a given number of CSI-RS ports, are given in Table 5.2.2.2.1a-1, for which O1 = O2 = 4. The number of CSI-RS ports, P_CSI−RS, is 2N1N2.
  > The codebook for 1-8 layers is given in Table 5.2.2.2.1a-4 …
- Table 5.2.2.2.1a-1：48 → (8,3), (6,4)；64 → (16,2), (8,4)；128 → (16,4), (8,8)；O1 = O2 = 4
- 最大 rank：8；codebookMode-r19 ∈ {modeA, modeB}（modeB 見 p.142）
- 說明：>32 port 不是靠新的 nrofPorts 值，而是**聚合 K 個 CSI-RS resource**（每個仍 ≤ 32 port；見 [214-071]）。

### [214-056] Type I Multi-Panel
- 出處：TS 38.214 V19.4.0 §5.2.2.2.2, Table 5.2.2.2.2-1, p.145–146
- 原文：
  > For 8 antenna ports {3000, 3001, …, 3007}, 16 antenna ports {3000, 3001, …, 3015}, and 32 antenna ports {3000, 3001, …, 3031}, and the UE configured with higher layer parameter codebookType set to 'typeI-MultiPanel',
  > - The values of Ng, N1 and N2 are configured with the higher layer parameters ng-n1-n2. … The number of CSI-RS ports, PCSI-RS, is 2NgN1N2.
  > - When Ng = 2, codebookMode shall be set to either '1' or '2'. When Ng = 4, codebookMode shall be set to '1'.
  > The bitmap parameter ri‑Restriction forms the bit sequence r3, ..., r1, r0 … When ri is zero, i ∈ {0,1, …, 3}, PMI and RI reporting are not allowed to correspond to any precoder associated with υ = i +1 layers.
- Table 5.2.2.2.2-1（依文字版轉錄，並以 P = 2·Ng·N1·N2 驗算；未以 PDF 目視核對）：8 port：(2,2,1)，(O1,O2)=(4,1)；16 port：(2,4,1)(4,1)、(4,2,1)(4,1)、(2,2,2)(4,4)；32 port：(2,8,1)(4,1)、(4,4,1)(4,1)、(2,4,2)(4,4)、(4,2,2)(4,4)
- 最大 rank：4（ri-Restriction 4 bit）

### [214-057] Refined Type I Multi-Panel（Rel-19，48/64/128 port）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.2a, Table 5.2.2.2.2a-1, p.149–150（PDF 第 151 頁核對）
- 原文：
  > For 48, 64 and 128 antenna ports, obtained by aggregating K CSI-RS resources for channel measurement, and the UE configured with higher layer parameter codebookType set to 'typeI-MultiPanel-r19'
  > - The values of Ng, N1 and N2 are configured with the higher layer parameter ng-n1-n2-cbsr-r19, where Ng = K is the number of CSI-RS resources configured in the resource set for channel measurement. … The number of CSI-RS ports, P_CSI−RS, is 2NgN1N2.
- Table 5.2.2.2.2a-1（O1,O2）=(4,4)：48 → (2,4,3), (2,6,2)；64 → (2,4,4), (2,8,2), (4,4,2)；128 → (4,4,4), (4,8,2)
- 最大 rank：4（ri-Restriction-r19 為 r3..r0；PMI 定義 υ = 1 與 υ ∈ {2,3,4}，p.150）

### [214-058] Type II（Rel-15）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.3, p.152；Table 5.2.2.2.3-4 與公式 p.156（PDF 第 157 頁核對）
- 原文：
  > For 4 antenna ports …, 8 …, 12 …, 16 …, 24 …, and 32 antenna ports …, and the UE configured with higher layer parameter codebookType set to 'typeII'
  > - The values of N1 and N2 are configured with the higher layer parameter n1-n2-codebookSubsetRestriction. The supported configurations of (N1, N2) … are given in Table 5.2.2.2.1-2. …
  > - The value of L is configured with the higher layer parameter numberOfBeams, where L=2 when PCSI-RS = 4 and L ∈ {2, 3, 4} when PCSI-RS > 4.
  > - The value of NPSK is configured with the higher layer parameter phaseAlphabetSize, where NPSK ∈ {4, 8}.
  > - The UE is configured with the higher layer parameter subbandAmplitude set to 'true' or 'false'.
  > - The UE shall not report RI > 2.
- 數值：port 4–32；L ∈ {2,3,4}；NPSK ∈ {4,8}；rank ≤ 2；subbandAmplitude=true 時強係數數 K^(2)：L=2→4、L=3→4、L=4→6（Table 5.2.2.2.3-4）
- [式] 係數相位 φ_{l,i} = e^{j2πc_{l,i}/NPSK}（subbandAmplitude=false）；弱係數在 true 時用 e^{j2πc/4}；v_{l,m} 與 Type I 相同形式，m1 = O1·n1 + q1，m2 = O2·n2 + q2（p.156）
- 說明：預編碼 = L 個正交 DFT beam 的線性組合（逐層求和式，規範未寫成 W1W2 乘積）。

### [214-059] Type II Port Selection（Rel-15）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.4, p.158–159
- 原文：
  > - The number of CSI-RS ports is given by PCSI-RS ∈ {4, 8, 12, 16, 24, 32} as configured by higher layer parameter nrofPorts.
  > - The value of L is configured with the higher layer parameter numberOfBeams, where L=2 when PCSI-RS = 4 and L ∈ {2, 3, 4} when PCSI-RS > 4.
  > - The value of d is configured with the higher layer parameter portSelectionSamplingSize, where d ∈ {1, 2, 3, 4} and d ≤ min(PCSI-RS/2, L).
  > - The value of NPSK is configured with the higher layer parameter phaseAlphabetSize, where NPSK ∈ {4, 8}.
  > - The UE shall not report RI > 2.
- 數值：rank ≤ 2；typeII-PortSelectionRI-Restriction 2 bit

### [214-060] Enhanced Type II（Rel-16，typeII-r16）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.5, Table 5.2.2.2.5-1, p.161–162（PDF 第 163 頁核對）
- 原文：
  > … and UE configured with higher layer parameter codebookType set to ' typeII-r16'
  > - The values of L, β and pυ are determined by the higher layer parameter paramCombination-r16, where the mapping is given in Table 5.2.2.2.5-1.
  > - The UE is not expected to be configured with paramCombination-r16 equal to 3, 4, 5, 6, 7, or 8 when PCSI-RS = 4, 7 or 8 when PCSI-RS < 32 …
  > - The UE shall report the RI value υ according to the configured higher layer parameter typeII-RI-Restriction-r16. The UE shall not report υ > 4.
- Table 5.2.2.2.5-1：

| paramCombination-r16 | L | pυ (υ∈{1,2}) | pυ (υ∈{3,4}) | β |
|---|---|---|---|---|
| 1 | 2 | 1/4 | 1/8 | 1/4 |
| 2 | 2 | 1/4 | 1/8 | 1/2 |
| 3 | 4 | 1/4 | 1/8 | 1/4 |
| 4 | 4 | 1/4 | 1/8 | 1/2 |
| 5 | 4 | 1/4 | 1/4 | 3/4 |
| 6 | 4 | 1/2 | 1/4 | 1/2 |
| 7 | 6 | 1/4 | – | 1/2 |
| 8 | 6 | 1/4 | – | 3/4 |

- 數值：port 4–32；rank ≤ 4；頻域基底 M_υ = ⌈pυ·N3/R⌉；R 由 numberOfPMI-SubbandsPerCQI-Subband 設定（p.161–162）

### [214-061] Enhanced Type II Port Selection（typeII-PortSelection-r16）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.6, Table 5.2.2.2.6-1, p.169
- 原文：
  > - The value of d is configured with the higher layer parameter portSelectionSamplingSize-r16, where d ∈ {1,2,3,4} and d ≤ L.
  > - The values L, β and pυ are configured as in Clause 5.2.2.2.5, where the supported configurations are given in Table 5.2.2.2.6-1.
  > - The UE shall report the RI value υ according to the configured higher layer parameter typeII-PortSelectionRI-Restriction-r16. The UE shall not report υ > 4.
- 數值：port 4–32；rank ≤ 4；paramCombination 1–6（Table 5.2.2.2.6-1，與 5.2.2.2.5-1 的 1–6 列相同）

### [214-062] Further Enhanced Type II Port Selection（Rel-17，typeII-PortSelection-r17）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.7, Table 5.2.2.2.7-1, p.170–171
- 原文：
  > - The values α, M and β are determined by the higher layer parameter paramCombination-r17, where the mapping is given in Table 5.2.2.2.7-1.
  > - The parameter N ∈ {2,4} is configured with the higher-layer parameter valueOfN, when M = 2.
  > - The UE shall report the RI value υ according to the configured higher layer parameter typeII-PortSelectionRI-Restriction-r17. The UE shall not report υ > 4.
- 數值：port 4–32；rank ≤ 4；paramCombination-r17 ∈ 1..8；M ∈ {1,2}（文字版轉錄 Table 5.2.2.2.7-1：1–4 列 M=1，5–8 列 M=2；α/β 欄位符號在文字版遺失，數值請以 PDF 第 172 頁為準——本文件未逐格核對）

### [214-063] Enhanced Type II for CJT（Rel-18，typeII-CJT-r18）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.8, p.174–176
- 原文：
  > … per CSI-RS resource, and the UE configured with N_TRP ∈ {1,2,3,4} CSI-RS resources in a resource set for channel measurement and with higher layer parameter codebookType set to 'typeII-CJT-r18'
  > A set of N_L ∈ {1,2,4} combinations of values of {L1, …, L_NTRP} is configured by the higher layer parameter paramCombination-CJT-L-r18 … A single value of pυ and β is configured by the higher layer parameter paramCombination-CJT-r18 …
  > - The UE shall report the RI value υ according to the configured higher layer parameter typeII-RI-Restriction-r18. The UE shall not report υ > 4.
  > - … Otherwise, the UE is expected to select N0 CSI-RS resources, with 1 ≤ N0 ≤ N_TRP, and the selection is reported with an N_TRP-bit bitmap …
- 數值：每 resource 4–32 port；N_TRP ≤ 4；rank ≤ 4；表 5.2.2.2.8-1/-2/-3

### [214-064] Further Enhanced Type II PS for CJT（typeII-CJT-PortSelection-r18）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.9, p.180–181
- 原文：
  > … per CSI-RS resource, the UE configured with N_TRP ∈ {1,2,3,4} CSI-RS resources in a resource set for channel measurement and with higher layer parameter codebookType set to 'typeII-CJT-PortSelection-r18'
  > A set of N_L ∈ {1,2,4} combinations of values of {α1, …, α_NTRP} is configured by the higher layer parameter paramCombination-CJT-PS-alpha-r18 …
- 原文（p.182）：
  > - The UE shall report the RI value υ according to the configured higher layer parameter typeII-PortSelectionRI-Restriction-r18. The UE shall not report υ > 4.
- 數值：rank ≤ 4；表 5.2.2.2.9-1/-2/-3

### [214-065] Enhanced Type II for predicted PMI / Doppler（Rel-18，typeII-Doppler-r18）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.10, Table 5.2.2.2.10-1, p.187–188
- 原文：
  > … per CSI-RS resource, the UE configured with K ∈ {4,8,12} aperiodic CSI-RS resources or with a single periodic or semi-persistent CSI-RS resource in the resource set for channel measurement and with codebookType set to 'typeII-Doppler-r18'
  > - The values of L, β and pυ are determined by the higher layer parameter paramCombination-Doppler-r18 …
  > - The UE shall report the RI value υ according to … typeII-RI-Restriction-r18. The UE shall not report υ > 4.
  > - The value of N4 ∈ {1,2,4,8} is configured by the higher layer parameter vectorLengthDD, such that the PMI indicates N3 precoder matrices for each of the N4 consecutive slot intervals of duration d slots …
- 數值：port 4–32；rank ≤ 4；N4 ∈ {1,2,4,8}；paramCombination-Doppler-r18 1..9

### [214-066] Further Enhanced Type II PS for predicted PMI（typeII-Doppler-PortSelection-r18）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.11, p.191
- 原文：
  > - The UE shall report the RI value υ according to … typeII-PortSelectionRI-Restriction-r18. The UE shall not report υ > 4.
  > - The value of N4 = 1 is configured by the higher layer parameter vectorLengthDD …
- 數值：port 4–32；rank ≤ 4；N4 = 1

### [214-067] Rel-19 refined Type II 系列（48/64/128 port 聚合）
- 出處：TS 38.214 V19.4.0 §5.2.2.2.5a p.168；§5.2.2.2.9a p.187；§5.2.2.2.11a p.192
- 原文（5.2.2.2.5a）：
  > For 48, 64 and 128 antenna ports, obtained by aggregating K CSI-RS resources for channel measurement, and the UE configured with higher layer parameter codebookType set to 'eTypeII-r19' … The UE shall not report υ > 4. The codebook is defined as in Clause 5.2.2.2.5.
- 原文（5.2.2.2.9a）：
  > For 48 and 64 antenna ports, obtained by aggregating K CSI-RS resources for channel measurement, and the UE configured with higher layer parameter codebookType set to 'valueOfN-r19' … The number of CSI-RS ports is P_CSI-RS = K·P … The UE is not expected to be configured with paramCombination-r19 equal to 8. … The UE shall not report υ > 4.
- 原文（5.2.2.2.11a）：
  > For 48, 64 and 128 antenna ports, obtained by aggregating K CSI-RS resources for channel measurement, and the UE configured with higher layer parameter codebookType set to 'typeII-Doppler-r19' … The UE shall not report υ > 4. … N4 ∈ {1,2,4,8} …

### [214-068] Codebook 總表（本文件整理，每格出處見上方 ID）

| codebookType | Rel | 適用 port 數 | 最大 rank | 主要參數 | 表號 | ID |
|---|---|---|---|---|---|---|
| typeI-SinglePanel（2 port） | 15 | 2 | 2 | twoTX-CodebookSubsetRestriction (6 bit) | 5.2.2.2.1-1 | 214-051 |
| typeI-SinglePanel | 15 | 4,8,12,16,24,32 | 8 | n1-n2(CBSR), codebookMode 1/2, ri-Restriction 8 bit | 5.2.2.2.1-2…-12 | 214-052~054 |
| typeI-SinglePanel-r19 | 19 | 48,64,128（K 個 resource 聚合） | 8 | n1-n2-r19, codebookMode-r19 A/B, O1=O2=4 | 5.2.2.2.1a-1…-7 | 214-055 |
| typeI-MultiPanel | 15 | 8,16,32 | 4 | ng-n1-n2, codebookMode, ri-Restriction 4 bit | 5.2.2.2.2-1… | 214-056 |
| typeI-MultiPanel-r19 | 19 | 48,64,128（Ng=K） | 4 | ng-n1-n2-cbsr-r19, ri-Restriction-r19 | 5.2.2.2.2a-1/-2 | 214-057 |
| typeII | 15 | 4–32 | 2 | numberOfBeams L, phaseAlphabetSize, subbandAmplitude | 5.2.2.2.3-x | 214-058 |
| typeII-PortSelection | 15 | 4–32 | 2 | L, portSelectionSamplingSize d, NPSK | 5.2.2.2.4-x | 214-059 |
| typeII-r16（eType II） | 16 | 4–32 | 4 | paramCombination-r16 (L,pυ,β), R | 5.2.2.2.5-1… | 214-060 |
| typeII-PortSelection-r16 | 16 | 4–32 | 4 | d, paramCombination 1–6 | 5.2.2.2.6-1 | 214-061 |
| typeII-PortSelection-r17（FeType II PS） | 17 | 4–32 | 4 | paramCombination-r17 (α,M,β), valueOfN | 5.2.2.2.7-1… | 214-062 |
| typeII-CJT-r18 | 18 | 每 resource 4–32，N_TRP≤4 | 4 | paramCombination-CJT-L-r18, -CJT-r18 | 5.2.2.2.8-1/-2/-3 | 214-063 |
| typeII-CJT-PortSelection-r18 | 18 | 同上 | 4 | paramCombination-CJT-PS-alpha-r18 | 5.2.2.2.9-1/-2/-3 | 214-064 |
| typeII-Doppler-r18 | 18 | 4–32 | 4 | paramCombination-Doppler-r18, N4∈{1,2,4,8} | 5.2.2.2.10-1 | 214-065 |
| typeII-Doppler-PortSelection-r18 | 18 | 4–32 | 4 | paramCombinationDoppler-PS-r18, N4=1 | 5.2.2.2.7-1（沿用） | 214-066 |
| eTypeII-r19 | 19 | 48,64,128 | 4 | paramCombination-r19（同 5.2.2.2.5-1） | 5.2.2.2.1a-1（N1,N2） | 214-067 |
| valueOfN-r19（refined FeType II PS） | 19 | 48,64 | 4 | paramCombination-r19（≠8） | 5.2.2.2.7-1（沿用） | 214-067 |
| typeII-Doppler-r19 | 19 | 48,64,128 | 4 | paramCombination-Doppler-r19, N4 | 5.2.2.2.10-1（沿用） | 214-067 |

### [214-069] portSubsetIndicator（天線 port 子集）
- 出處：TS 38.214 V19.4.0 §5.2.1.4.2, p.99–100
- 原文：
  > - the higher layer bitmap parameter portSubsetIndicator, of length up to 32 bits, which contains the bit sequence …, bit … corresponds to antenna port 3000 + i, and … is the number of ports nrofPorts configured for the CSI-RS resources(s) … A bit value 0 in portSubsetIndicator indicates that the corresponding antenna port is disabled for the sub-configuration, whereas bit value 1 indicates that the antenna port is enabled and belongs to the antenna port subset for the sub-configuration. …
  > - the higher layer bitmap parameter portSubsetIndicator-r19, of length 48, 64 or 128 bits, … The number of enabled antenna ports can be 48, 64 or 128 for a sub-configuration configured with codebookType set to 'typeI-SinglePanel-r19' or 2, 4, 8, 12, 16, 24 or 32 for a sub-configuration configured with codebookType set to 'typeI-SinglePanel', according to UE capability.
- 前提（p.99）：sub-configuration 只能搭 `typeI-SinglePanel`、`typeI-MultiPanel` 或 `typeI-SinglePanel-r19`，且不設定 valueOfM。
- 說明：這是 Rel-18/19 的「空間域 port 自適應」（節能）機制。

---

## E. TS 38.214 — NZP CSI-RS 資源（§5.2.2.3.1）

### [214-070] NZP CSI-RS 主要參數
- 出處：TS 38.214 V19.4.0 §5.2.2.3.1, p.192–193
- 原文：
  > - nrofPorts in resourceMapping defines the number of CSI-RS ports, where the allowable values are given in Clause 7.4.1.5 of [4, TS 38.211].
  > - powerControlOffset: which is the assumed ratio of PDSCH EPRE to NZP CSI-RS EPRE when UE derives CSI feedback and takes values in the range of [-8, 15] dB with 1 dB step size. …
  > - powerControlOffsetSS: which is the assumed ratio of NZP CSI-RS EPRE to SS/PBCH block EPRE.
  > - qcl-InfoPeriodicCSI-RS contains a reference to a TCI-State indicating QCL source RS(s) and QCL type(s). If the TCI-State is configured with a reference to an RS configured with qcl-Type set to 'typeD' association, that RS may be an SS/PBCH block located in the same or different CC/DL BWP or a CSI-RS resource configured as periodic located in the same or different CC/DL BWP. …
- 數值：`nrofPorts ENUMERATED {p1,p2,p4,p8,p12,p16,p24,p32}`（S331-002，TS 38.331 p.862）；powerControlOffset ∈ [-8, 15] dB
- 說明：periodic CSI-RS 以 qcl-InfoPeriodicCSI-RS 指向 TCI-State → 形成 SSB → CSI-RS 的 beam 階層。

### [214-071] Rel-19 聚合 CSI-RS resource 的同質性要求
- 出處：TS 38.214 V19.4.0 §5.2.2.3.1, p.193
- 原文：
  > The UE expects that all the CSI-RS resources of a resource set for channel measurement, linked to a CSI-ReportConfig configured with codebookType set to 'typeI-SinglePanel-r19', 'typeI-MultiPanel-r19', 'eTypeII-r19', 'valueOfN-r19' or 'eTypeII-Doppler-r19', are configured with the same qcl-info, powerControlOffset and powerControlOffsetSS.
  > For a NZP-CSI-RS-ResourceSet for channel measurement with 2 ≤ K ≤ 4 resources, linked to a CSI-ReportConfig configured with codebookType set to 'typeI-SinglePanel-r19', … the slot offsets of the K CSI-RS resources are configured within X ∈ {1,2} slots, without DL/UL switching in between the K resources …
- 數值：K ∈ [2, 4]；K 個 resource 落在 1 或 2 個相鄰 slot 內；QCL/功率偏移一致

---

## F. TS 38.214 — PUSCH 與 SRS（§6.1.1, §6.2.1）

### [214-080] PUSCH 兩種傳輸方案
- 出處：TS 38.214 V19.4.0 §6.1.1, p.225
- 原文：
  > Two transmission schemes are supported for PUSCH: codebook based transmission and non-codebook based transmission. The UE is configured with codebook based transmission when the higher layer parameter txConfig in pusch-Config is set to 'codebook', the UE is configured non-codebook based transmission when the higher layer parameter txConfig is set to 'nonCodebook'. If the higher layer parameter txConfig is not configured, the UE is not expected to be scheduled by DCI format 0_1, 0_2 or 0_3. If PUSCH is scheduled by DCI format 0_0, the PUSCH transmission is based on a single antenna port.
- 數值：txConfig ∈ {codebook, nonCodebook}；DCI 0_0 → 單 port

### [214-081] Codebook-based PUSCH：SRI + TPMI + rank
- 出處：TS 38.214 V19.4.0 §6.1.1.1, p.226
- 原文：
  > … the UE determines its PUSCH transmission precoder(s) based on SRI(s), TPMI(s) and the transmission rank, where the SRI(s), TPMI(s) and the transmission rank are given by DCI fields of one or two SRS resource indicators and one or two Precoding information and number of layers …
  > Only one or two SRS resource sets can be configured in srs-ResourceSetToAddModList with higher layer parameter usage in SRS-ResourceSet set to 'codebook' …
  > The TPMI is used to indicate the precoder to be applied over the layers {0…ν-1} and that corresponds to the SRS resource selected by the SRI when multiple SRS resources are configured … the transmission precoder is selected from the uplink codebook that has a number of antenna ports equal to higher layer parameter nrofSRS-Ports or nrofSRS-Ports-n8 in SRS-Config, as defined in Clause 6.3.1.5 of [4, TS 38.211]. … The indicated SRI in slot n is associated with the most recent transmission of SRS resource identified by the SRI, where the SRS resource is prior to the PDCCH carrying the SRI.
- 同節（p.228）coherence 子集：
  > For codebook based transmission with two or four antenna ports, the UE determines its codebook subsets based on TPMI(s) and upon the reception of higher layer parameter codebookSubset … which may be configured with 'fullyAndPartialAndNonCoherent', or 'partialAndNonCoherent', or 'nonCoherent' depending on the UE capability for two or four antenna ports.
- 數值：codebookSubset ∈ {fullyAndPartialAndNonCoherent, partialAndNonCoherent, nonCoherent}；3 port 只允許 nonCoherent；8 port 用 CodebookTypeUL（p.228）；rank 上限 maxRank（p.227）

### [214-082] Non-codebook-based PUSCH：SRI 決定 precoder 與 rank
- 出處：TS 38.214 V19.4.0 §6.1.1.2, p.229–230
- 原文：
  > … the UE can determine its PUSCH precoder(s) and transmission rank based on the SRI(s) when multiple SRS resources are configured …
  > Only one SRS port for each SRS resource is configured.
  > The maximum number of SRS resources per SRS resource set that can be configured for non-codebook based uplink transmission is 1, 2, 3, 4 or 8 depending on UE capability.
- 同節（p.231）：UE 可依 `associatedCSI-RS` 量到的 DL CSI-RS 計算 SRS precoder（通道互易）。
- 數值：每 SRS resource 1 port；每 set ≤ {1,2,3,4,8}（UE 能力）

### [214-083] SRS usage 與 beamManagement 規則
- 出處：TS 38.214 V19.4.0 §6.2.1, p.277
- 原文：
  > The SRS resource set applicability is configured by the higher layer parameter usage in SRS-ResourceSet. When the higher layer parameter usage is set to 'beamManagement', only one SRS resource in each of multiple SRS resource sets may be transmitted at a given time instant, but the SRS resources in different SRS resource sets with the same time domain behaviour in the same BWP may be transmitted simultaneously. For a given CC, multiple SRS resources across multiple sets with usage "beamManagement" are not expected to be partially overlapped in time.
- 數值：usage ∈ {beamManagement, codebook, nonCodebook, antennaSwitching}（前三者見本節與 §6.1.1；antennaSwitching 見 [214-084]）。38.214 另有 positioning 用的 SRS-PosResourceSet（K ≤ 16）。

### [214-084] Antenna switching：xTyR 支援組合
- 出處：TS 38.214 V19.4.0 §6.2.1.2, p.286–287
- 原文：
  > When the UE is configured with the higher layer parameter usage in SRS-ResourceSet set as 'antennaSwitching', the UE may be configured with only one of the following configurations depending on the indicated UE capability supportedSRS-TxPortSwitch ('t1r2' for 1T2R, 't1r1-t1r2' for 1T=1R/1T2R, 't2r4' for 2T4R, 't1r4' for 1T4R, 't1r1-t1r2-t1r4' for 1T=1R/1T2R/1T4R, 't1r4-t2r4' for 1T4R/2T4R, 't1r1-t1r2-t2r2-t2r4' for 1T=1R/1T2R/2T=2R/2T4R, 't1r1-t1r2-t2r2-t1r4-t2r4' for 1T=1R/1T2R/2T=2R/1T4R/2T4R, 't1r1' for 1T=1R, 't2r2' for 2T=2R, 't1r1-t2r2' for 1T=1R/2T=2R, 't4r4' for 4T=4R, or 't1r1-t2r2-t4r4' for 1T=1R/2T=2R/4T=4R) or … supportedSRS-TxPortSwitchBeyond4Rx ('t1r1' …, 't2r6' for 2T6R, 't1r6' for 1T6R, 't4r8' for 4T8R, 't2r8' for 2T8R, 't1r8' for 1T8R) or … srs-AntennaSwitching8T8R (… 'noTdm' or 'tdmAndNoTdm' for 8T8R) or the UE may be configured with 't3r3' for 3T=3R … or … 't3r6' …
- 數值：1T2R, 1T4R, 2T4R, 1T=1R, 2T=2R, 4T=4R, 1T6R, 2T6R, 1T8R, 2T8R, 4T8R, 8T8R, 3T=3R, 3T6R（依 UE 能力）
- 說明：antenna switching SRS 是 TDD 下行 CSI 互易取得（非 codebook DL precoding）的依據。

### [214-085] SRS 與 unified TCI
- 出處：TS 38.214 V19.4.0 §6.2.1, p.278
- 原文：
  > If an SRS resource set, except an SRS resource set for positioning, is configured with followUnifiedTCI-StateSRS, the UE shall transmit the target SRS resource(s) within the SRS resource set according to the spatial relation, if applicable, with a reference to the RS used for determining UL TX spatial filter. The RS is determined based on an RS configured with qcl-Type set to 'typeD' in QCL-Info of the indicated TCI-State or an RS in the indicated TCI-UL-State.

---

## G. TS 38.213 — SSB、隨機存取關聯、Link recovery、Pathloss RS

### [213-001] SS/PBCH 候選位置（Case A–G）
- 出處：TS 38.213 V19.4.0 §4.1, p.10–11
- 原文（節錄）：
  > - Case A - 15 kHz SCS: the first symbols of the candidate SS/PBCH blocks have indexes of {2, 8} + 14·n. … For carrier frequencies smaller than or equal to 3 GHz, n = 0, 1. … For carrier frequencies within FR1 larger than 3 GHz, n = 0, 1, 2, 3.
  > - Case B - 30 kHz SCS: … {4, 8, 16, 20} + 28·n. For carrier frequencies smaller than or equal to 3 GHz, n = 0. For carrier frequencies within FR1 larger than 3 GHz, n = 0, 1.
  > - Case C - 30 kHz SCS: … {2, 8} + 14·n. …（paired ≤3 GHz: n=0,1；>3 GHz: n=0..3；unpaired <1.88 GHz: n=0,1；≥1.88 GHz: n=0..3）
  > - Case D - 120 kHz SCS: … {4, 8, 16, 20} + 28·n. For carrier frequencies within FR2 and FR2-NTN, n = 0, 1, 2, 3, 5, 6, 7, 8, 10, 11, 12, 13, 15, 16, 17, 18.
  > - Case E - 240 kHz SCS: … {8, 12, 16, 20, 32, 36, 40, 44} + 56·n. For carrier frequencies within FR2-1 and FR2-NTN, n = 0, 1, 2, 3, 5, 6, 7, 8.
  > - Case F – 480 kHz SCS: … {2, 9} + 14·n. For carrier frequencies within FR2-2, n = 0, 1, …, 31.
  > - Case G – 960 kHz SCS: … {2, 9} + 14·n. For carrier frequencies within FR2-2, n = 0, 1, …, 31.
- 推得的候選數（本文件計算 = 每組符號數 × n 個數）：A/C ≤3 GHz → 4；A/C FR1 >3 GHz → 8；B ≤3 GHz → 4、>3 GHz → 8；D → 64；E → 64；F/G → 64（非共享頻譜）

### [213-002] L̄max / Lmax 與 SSB index 取得方式
- 出處：TS 38.213 V19.4.0 §4.1, p.11（PDF 第 12 頁核對符號）
- 原文：
  > The candidate SS/PBCH blocks in a half frame are indexed in an ascending order in time from 0 to L̄max − 1, where L̄max is determined according to SS/PBCH block patterns for Cases A through G. Lmax is a maximum number of SS/PBCH block indexes in a cell, and the maximum number of transmitted SS/PBCH blocks within a half frame is Lmax.
  > - For operation without shared spectrum channel access in FR1 and FR2, and for operation with shared spectrum channel access in FR2-2, Lmax = L̄max
  > - For operation with shared spectrum channel access in FR1, Lmax = 8 for L̄max = 10 and 15 kHz SCS of SS/PBCH blocks and for L̄max = 20 and 30 kHz SCS of SS/PBCH blocks
  > For L̄max = 4, a UE determines the 2 LSB bits of a candidate SS/PBCH block index per half frame from a one-to-one mapping with an index of the DM-RS sequence transmitted in the PBCH …
  > For L̄max > 4, a UE determines the 3 LSB bits … – for L̄max = 64, the UE determines the 3 MSB bits of the candidate SS/PBCH block index from PBCH payload bits …
- 數值：L̄max ∈ {4, 8, 10, 20, 64}；Lmax ∈ {4, 8, 64}（非共享頻譜時 = L̄max）
- 說明：SSB index = 初始接入的「beam 編號」；L̄max=64 時 index 需 PBCH DM-RS（3 LSB）＋ payload（3 MSB）。

### [213-003] SSB 週期
- 出處：TS 38.213 V19.4.0 §4.1, p.11
- 原文：
  > If the UE is not configured a periodicity of the half frames for receptions of the SS/PBCH blocks, the UE assumes a periodicity of a half frame. …
  > For initial cell selection, a UE may assume that half frames with SS/PBCH blocks occur with a periodicity of 2 frames.
- 數值：初始選細胞假設 20 ms（2 frames）

### [213-004] SSB ↔ PRACH occasion 關聯（beam 回報給 gNB 的方式）
- 出處：TS 38.213 V19.4.0 §8.1, p.64–65
- 原文：
  > For Type-1 random access procedure, a UE is provided a number N of SS/PBCH block indexes associated with one PRACH occasion and a number R of contention based preambles per SS/PBCH block index per valid PRACH occasion either by ssb-perRACH-OccasionAndCB-PreamblesPerSSB or by ssb-perRACH-OccasionAndCB-PreamblesPerSSB-r19.
  > … SS/PBCH block indexes … are mapped to valid PRACH occasions in the following order …
  > - First, in increasing order of preamble indexes within a single PRACH occasion
  > - Second, in increasing order of frequency resource indexes for frequency multiplexed PRACH occasions
  > - Third, in increasing order of time resource indexes for time multiplexed PRACH occasions within a PRACH slot
  > - Fourth, in increasing order of indexes for PRACH slots
- 說明：UE 選用哪個 PRACH occasion/preamble 即隱含選到哪個 SSB beam（N、R 的符號在文字版遺失，依上下文為 N 與 R）。

### [213-010] BFD / 候選 beam 集合 q0、q1
- 出處：TS 38.213 V19.4.0 §6, p.19
- 原文：
  > A UE can be provided, for each BWP of a serving cell, a set q̄0 of periodic CSI-RS resource configuration indexes by failureDetectionResourcesToAddModList and a set q̄1 of periodic CSI-RS resource configuration indexes and/or SS/PBCH block indexes by candidateBeamRSList or candidateBeamRSListExt or candidateBeamRS-List for radio link quality measurements on the BWP of the serving cell. Instead of the sets q̄0 and q̄1, for each BWP of a serving cell, the UE can be provided respective two sets q̄0,0 and q̄0,1 … by failureDetectionSet1 and failureDetectionSet2 … and corresponding two sets q̄1,0 and q̄1,1 … by candidateBeamRS-List and candidateBeamRS-List2 …
- 說明：q0 = 監測中的 beam（BFD-RS），q1 = 候選新 beam；Rel-17 起可每 TRP 一組。
- S331-005（TS 38.331 p.1658/1660）：`maxNrofFailureDetectionResources = 10`；`maxNrofCandidateBeams = 16`（PRACH-ResourceDedicatedBFR 數）

### [213-011] q0 未設定時的隱式決定、數量與 port 限制
- 出處：TS 38.213 V19.4.0 §6, p.19
- 原文：
  > If the UE is not provided q̄0 by failureDetectionResourcesToAddModList for a BWP of the serving cell, the UE determines the set q̄0 to include periodic CSI-RS resource configuration indexes with same values as the RS indexes in the RS sets indicated by TCI-State for respective CORESETs that the UE uses for monitoring PDCCH. … If there are two RS indexes in a TCI state, the set q̄0 … includes RS indexes configured with qcl-Type set to 'typeD' for the corresponding TCI states.
  > The UE expects the set q̄0 to include up to two RS indexes. If the UE is provided q̄0,0 or q̄0,1, the UE expects the set q̄0,0 or the set q̄0,1 to include up to a number of N_BFD RS indexes indicated by maxBFD-RS-resourcesPerSetPerBWP.
  > The UE expects single port RS in the set q̄0, or q̄0,0, or q̄0,1. The UE expects single-port or two-port CSI-RS with frequency density equal to 1 or 3 REs per RB in the set q̄1, or q̄1,0, or q̄1,1.
- 數值：隱式 q0 ≤ 2 個 RS；q0 為單 port；q1 為 1/2 port、密度 1 或 3 RE/RB

### [213-012] Qout,LR / Qin,LR 門檻
- 出處：TS 38.213 V19.4.0 §6, p.19
- 原文：
  > The thresholds Qout,LR and Qin,LR correspond to the default value of rlmInSyncOutOfSyncThreshold, as described in [10, TS 38.133] for Qout, and to the value provided by rsrp-ThresholdSSB or rsrp-ThresholdBFR, respectively.
  > The physical layer in the UE assesses the radio link quality according to the set q̄0 … against the threshold Qout,LR. … The UE applies the Qin,LR threshold to the L1-RSRP measurement obtained from a SS/PBCH block. The UE applies the Qin,LR threshold to the L1-RSRP measurement obtained for a CSI-RS resource after scaling a respective CSI-RS reception power with a value provided by powerControlOffsetSS.
- 數值：Qout,LR = rlmInSyncOutOfSyncThreshold 預設值（其 BLER 數值定義在 TS 38.133 → 本資料夾**未找到**）；Qin,LR = rsrp-ThresholdSSB / rsrp-ThresholdBFR（L1-RSRP 門檻）
- 說明：Qout 是「假想 PDCCH BLER」門檻（依 38.133），Qin 是 RSRP 門檻。

### [213-013] Beam failure instance 指示週期
- 出處：TS 38.213 V19.4.0 §6, p.20
- 原文：
  > In non-DRX mode operation, the physical layer in the UE provides an indication to higher layers when the radio link quality for all corresponding resource configurations in the set q̄0, or in the set q̄0,0 or q̄0,1, that the UE uses to assess the radio link quality is worse than the threshold Qout,LR. The physical layer informs the higher layers when the radio link quality is worse than the threshold Qout,LR with a periodicity determined by the maximum between the shortest periodicity among the SS/PBCH blocks on the PCell or the PSCell and/or the periodic CSI-RS configurations in the set q̄0, q̄0,0, or q̄0,1 that the UE uses to assess the radio link quality and 2 msec. In DRX mode operation, … with a periodicity determined as described in [10, TS 38.133].
- [式] 非 DRX：BFI 指示週期 = max(q0 中最短 RS 週期, 2 ms)
- 說明：「全部」q0 RS 都差於 Qout 才算一次 BFI → 交 MAC 計數（[321-002]）。

### [213-014] 候選 beam 回報給 MAC
- 出處：TS 38.213 V19.4.0 §6, p.20
- 原文：
  > For the PCell or the PSCell, upon request from higher layers, the UE provides to higher layers the periodic CSI-RS configuration indexes and/or SS/PBCH block indexes from the set q̄1, or q̄1,0, or q̄1,1 and the corresponding L1-RSRP measurements that are larger than or equal to the Qin,LR threshold.

### [213-015] BFR 的 PRACH 與 recovery search space（4 slot 起監聽）
- 出處：TS 38.213 V19.4.0 §6, p.20
- 原文：
  > For the PCell or the PSCell, the UE can be provided, by PRACH-ResourceDedicatedBFR, a configuration for PRACH transmission as described in clause 8.1. For PRACH transmission in slot n and according to antenna port quasi co-location parameters associated with periodic CSI-RS resource configuration or with SS/PBCH block associated with index q_new provided by higher layers [11, TS 38.321], the UE monitors PDCCH in a search space set provided by recoverySearchSpaceId for detection of a DCI format with CRC scrambled by C-RNTI or MCS-C-RNTI starting from slot n + 4 + 2^μ·k_mac, … within a window configured by BeamFailureRecoveryConfig. For PDCCH monitoring in a search space set provided by recoverySearchSpaceId and for corresponding PDSCH receptions, the UE assumes the same antenna port quasi-collocation parameters as the ones associated with index q_new until the UE receives by higher layers an activation for a TCI state or any of the parameters tci-StatesPDCCH-ToAddList and/or tci-StatesPDCCH-ToReleaseList.
- [式] 監聽起點 slot = n + 4 + 2^μ·k_mac（k_mac 未提供 = 0）

### [213-016] BFR 成功後 28 symbols 的 QCL/空間濾波規則
- 出處：TS 38.213 V19.4.0 §6, p.20
- 原文：
  > For the PCell or the PSCell, after 28 symbols from a last symbol of a first PDCCH reception in a search space set provided by recoverySearchSpaceId for which the UE detects a DCI format with CRC scrambled by C-RNTI or MCS-C-RNTI and until the UE receives an activation command for PUCCH-SpatialRelationInfo [11, TS 38.321] or is provided PUCCH-SpatialRelationInfo for PUCCH resource(s), the UE transmits a PUCCH on a same cell as the PRACH transmission using
  > - a same spatial filter as for the last PRACH transmission
  > …
  > For the PCell or the PSCell and for sets q̄0 and q̄1, after 28 symbols from a last symbol of a first PDCCH reception in a search space set provided by recoverySearchSpaceId where a UE detects a DCI format with CRC scrambled by C-RNTI or MCS-C-RNTI, the UE assumes same antenna port quasi-collocation parameters as the ones associated with index q_new for PDCCH monitoring in a CORESET with index 0.
- 數值：28 symbols

### [213-017] Unified TCI 下的 BFR 後行為
- 出處：TS 38.213 V19.4.0 §6, p.20–21
- 原文：
  > If a UE is provided dl-OrJointTCI-StateList or ul-TCI-StateList and is indicated one or two TCI state(s) for the PCell or the PSCell [6, TS 38.214] associated with q̄0 and q̄1, after 28 symbols from a last symbol of a first PDCCH reception in a search space set provided by recoverySearchSpaceId where the UE detects a DCI format with CRC scrambled by C-RNTI or MCS-C-RNTI, the UE
  > - if SSB-MTC-AdditionalPCI is not provided, monitors PDCCH in all CORESETs, and receives PDSCH and aperiodic CSI-RS resource in a CSI-RS resource set with same indicated TCI state as for the PDCCH and PDSCH, using the same antenna port quasi co-location parameters as the ones associated with the corresponding index q_new, if any
  > - transmits PUSCH, PUCCH and SRS that uses a same spatial domain filter with same indicated TCI state as for the PUSCH and the PUCCH, using a same spatial domain filter as for the last PRACH transmission …

### [213-020] Pathloss RS：每 serving cell 最多 4 個估計
- 出處：TS 38.213 V19.4.0 §7, p.25
- 原文：
  > A UE does not expect to simultaneously maintain more than four pathloss estimates per serving cell for all PUSCH/PUCCH/SRS transmissions as described in clauses 7.1.1, 7.2.1, and 7.3.1, except for SRS transmissions configured by SRS-PosResourceSet as described in clause 7.3.1.
- 數值：≤ 4 個 pathloss 估計 / serving cell

### [213-021] PUSCH pathloss RS 決定與 PL 定義
- 出處：TS 38.213 V19.4.0 §7.1.1, p.33 與 p.36
- 原文（p.33）：
  > - If the UE is not provided PUSCH-PathlossReferenceRS and enableDefaultBeamPL-ForSRS, or before the UE is provided dedicated higher layer parameters, the UE calculates PL_b,f,c(q_d) … using a RS resource from an SS/PBCH block with same SS/PBCH block index as the one the UE uses to obtain MIB …
  > - If the UE is configured with a number of RS resource indexes, up to the value of maxNrofPUSCH-PathlossReferenceRSs, and a respective set of RS configurations for the number of RS resource indexes by PUSCH-PathlossReferenceRS, the set of RS resource indexes can include one or both of a set of SS/PBCH block indexes … and a set of CSI-RS resource indexes …
- 原文（p.36）：
  > PL_b,f,c(q_d) = referenceSignalPower – higher layer filtered RSRP, where referenceSignalPower is provided by higher layers and RSRP is defined in [7, TS 38.215] for the reference serving cell …
- 說明：pathloss RS 與 beam 綁定（SRI ↔ PUSCH-PathlossReferenceRS-Id 映射，p.34–35；可由 MAC CE 更新，p.36，見 [321-004] 的 6.1.3.27/6.1.3.28）。
- Spatial relation（PUCCH-SpatialRelationInfo / SRS spatialRelationInfo）的規則在 38.213 只以功控情境出現（§7.2.1 p.42 等）；空間關係本體的定義：**未在 38.213 找到獨立小節**（在 38.214 §5.1.5/§6.2.1 與 38.331）。

---

## H. TS 38.215 — RSRP 量測定義

### [215-001] SS-RSRP
- 出處：TS 38.215 V19.3.0 §5.1.1, p.9
- 原文：
  > SS reference signal received power (SS-RSRP) is defined as the linear average over the power contributions (in [W]) of the resource elements that carry secondary synchronization signals. The measurement time resource(s) for SS-RSRP are confined within SS/PBCH Block Measurement Time Configuration (SMTC) window duration, except when measurement is being performed by wake-up receiver (WUR). If SS-RSRP is used for L1-RSRP as configured by reporting configurations as defined in TS 38.214 [6], the measurement time resources(s) restriction by SMTC window duration is not applicable.
  > SS-RSRP shall be measured only among the reference signals corresponding to SS/PBCH blocks with the same SS/PBCH block index and the same physical-layer cell identity.
- 說明：以 SSS RE 平均功率（W）；可加 PBCH DM-RS；**同一 SSB index（同 beam）內**平均。

### [215-002] CSI-RSRP
- 出處：TS 38.215 V19.3.0 §5.1.2, p.10
- 原文：
  > CSI reference signal received power (CSI-RSRP), is defined as the linear average over the power contributions (in [W]) of the resource elements of the antenna port(s) that carry CSI reference signals configured for RSRP measurements within the considered measurement frequency bandwidth in the configured CSI-RS occasions.
  > For CSI-RSRP determination CSI reference signals transmitted on antenna port 3000 according to TS 38.211 [3] shall be used. If CSI-RSRP is used for L1-RSRP, CSI reference signals transmitted on antenna ports 3000, 3001 can be used for CSI-RSRP determination.
- 數值：一般用 port 3000；L1-RSRP 可用 3000、3001（對應 [214-037] 的 1/2 port 限制）

### [215-003] Antenna connector / reference point 規則
- 出處：TS 38.215 V19.3.0 §5.1.1, p.9（SS-RSRP）；§5.1.2, p.10（CSI-RSRP，文字相同）
- 原文：
  > For frequency range 1, the reference point for the SS-RSRP shall be the antenna connector of the UE. For frequency range 2, SS-RSRP shall be measured based on the combined signal from antenna elements corresponding to a given receiver branch. For frequency range 1 and 2, if receiver diversity is in use by the UE, the reported SS-RSRP value shall not be lower than the corresponding SS-RSRP of any of the individual receiver branches.
- 說明：FR1 參考點 = UE 天線接頭；FR2 = 同一 receiver branch 的陣元合成訊號（即含 UE 接收 beamforming 增益）；分集時回報值 ≥ 任一分支。

### [215-004] L1-RSRP 的定義方式
- 出處：TS 38.215 V19.3.0 §5.1.1 p.9、§5.1.2 p.10（"Applicable for" 欄）
- 原文：
  > Applicable for — If SS-RSRP is used for L1-RSRP, RRC_CONNECTED intra-frequency, RRC_CONNECTED inter-frequency. If SS-RSRP is used for predicted RSRP, RRC_CONNECTED intra-frequency.
- 說明：38.215 **沒有獨立的「L1-RSRP」小節**；L1-RSRP = 以 SS-RSRP 或 CSI-RSRP 定義、依 38.214 報告設定做的 Layer-1 量測（不受 SMTC 限制、不經 L3 濾波）。同理 L1-SINR 以 SS-SINR / CSI-SINR 定義（§5.1.5–5.1.6, p.13–14）。

---

## I. TS 38.321 — MAC：BFD/BFR 與 beam 相關 MAC CE

### [321-001] BFD/BFR 參數
- 出處：TS 38.321 V19.3.0 §5.17, p.141–142
- 原文：
  > Beam failure is detected by counting beam failure instance indication from the lower layers to the MAC entity.
  > - beamFailureInstanceMaxCount for the beam failure detection (per Serving Cell or per BFD-RS set of Serving Cell configured with two BFD-RS sets);
  > - beamFailureDetectionTimer for the beam failure detection (per Serving Cell or per BFD-RS set of Serving Cell configured with two BFD-RS sets);
  > - beamFailureRecoveryTimer for the beam failure recovery procedure for SpCell;
  > - rsrp-ThresholdSSB: an RSRP threshold for the SpCell beam failure recovery;
  > - rsrp-ThresholdBFR: an RSRP threshold for the SCell beam failure recovery or for the beam failure recovery of BFD-RS set of Serving Cell;
  > - candidateBeamRSList: list of candidate beams for SpCell beam failure recovery;
- 值域（S331-009，TS 38.331 p.1149–1150 / p.735）：
  - `beamFailureInstanceMaxCount ENUMERATED {n1, n2, n3, n4, n5, n6, n8, n10}`
  - `beamFailureDetectionTimer ENUMERATED {pbfd1, pbfd2, pbfd3, pbfd4, pbfd5, pbfd6, pbfd8, pbfd10}`，單位 = 「Qout,LR reporting periods of Beam Failure Detection Reference Signal」
  - `beamFailureRecoveryTimer ENUMERATED {ms10, ms20, ms40, ms60, ms80, ms100, ms150, ms200}`

### [321-002] BFI_COUNTER 演算法（單一 BFD-RS set）
- 出處：TS 38.321 V19.3.0 §5.17, p.142–143
- 原文：
  > - BFI_COUNTER (per Serving Cell or per BFD-RS set of Serving Cell configured with two BFD-RS sets): counter for beam failure instance indication which is initially set to 0.
  > 1> else:
  >   2> if beam failure instance indication has been received from lower layers:
  >     3> start or restart the beamFailureDetectionTimer;
  >     3> increment BFI_COUNTER by 1;
  >     3> if BFI_COUNTER >= beamFailureInstanceMaxCount:
  >       4> if the Serving Cell is SCell:
  >         5> trigger a BFR for this Serving Cell;
  >       …
  >       4> else:
  >         5> initiate a Random Access procedure (see clause 5.1) on the SpCell;
  >   2> if the beamFailureDetectionTimer expires; or
  >   2> if beamFailureDetectionTimer, beamFailureInstanceMaxCount, or any of the reference signals used for beam failure detection is reconfigured by upper layers associated with this Serving Cell; or
  >   2> if the reference signal(s) associated with this Serving Cell used for beam failure detection is changed:
  >     3> set BFI_COUNTER to 0.
- 說明：timer 在每次 BFI 重啟；timer 到期代表 BFI 不連續 → 計數歸零。兩組 BFD-RS set 版本見同節 p.142（per-set 計數，兩組都失敗時在 SpCell 發 RA）。

### [321-003] BFR 完成條件
- 出處：TS 38.321 V19.3.0 §5.17, p.144
- 原文：
  > 2> if the Serving Cell is SpCell and the Random Access procedure initiated for SpCell beam failure recovery is successfully completed (see clause 5.1):
  >   3> set BFI_COUNTER to 0;
  >   3> stop the beamFailureRecoveryTimer, if configured;
  >   3> consider the Beam Failure Recovery procedure successfully completed.
  > 2> else if the Serving Cell is SCell, and a PDCCH addressed to C-RNTI indicating uplink grant for a new transmission is received for the HARQ process used for the transmission of the MAC CE for BFR which contains beam failure recovery information of this Serving Cell; or …
- 註：引文逐字取自文字版 p.144（原文跨兩行斷行，已合併）。

### [321-004] Beam / MIMO 相關 MAC CE 清單（§6.1.3.x）

| 小節 | 名稱 | 頁 |
|---|---|---|
| 6.1.3.12 | SP CSI-RS/CSI-IM Resource Set Activation/Deactivation MAC CE | 258 |
| 6.1.3.12a | SP CSI-RS/CSI-IM Resource Set Activation/Deactivation for Candidate Cell | 259 |
| 6.1.3.13 | Aperiodic CSI Trigger State Subselection MAC CE | 260 |
| 6.1.3.14 | TCI States Activation/Deactivation for UE-specific PDSCH MAC CE | 261 |
| 6.1.3.15 | TCI State Indication for UE-specific PDCCH MAC CE | 261 |
| 6.1.3.16 | SP CSI reporting on PUCCH Activation/Deactivation MAC CE | 262 |
| 6.1.3.17 | SP SRS Activation/Deactivation MAC CE | 263 |
| 6.1.3.18 | PUCCH spatial relation Activation/Deactivation MAC CE | 264 |
| 6.1.3.19 | SP ZP CSI-RS Resource Set Activation/Deactivation MAC CE | 265 |
| 6.1.3.23 | BFR MAC CEs（BFR / Truncated BFR） | 267 |
| 6.1.3.24 | Enhanced TCI States Activation/Deactivation for UE-specific PDSCH MAC CE | 269 |
| 6.1.3.25 | Enhanced PUCCH Spatial Relation Activation/Deactivation MAC CE | 270 |
| 6.1.3.26 | Enhanced SP/AP SRS Spatial Relation Indication MAC CE | 271 |
| 6.1.3.27 | SRS Pathloss Reference RS Update MAC CE | 272 |
| 6.1.3.28 | PUSCH Pathloss Reference RS Update MAC CE | 273 |
| 6.1.3.29 | Serving Cell Set based SRS Spatial Relation Indication MAC CE | 273 |
| 6.1.3.43 | Enhanced BFR MAC CEs | 284 |
| 6.1.3.44 | Enhanced TCI States Indication for UE-specific PDCCH MAC CE | 287 |
| 6.1.3.45 | PUCCH spatial relation Activation/Deactivation for multiple TRP PUCCH | 288 |
| 6.1.3.47 | Unified TCI States Activation/Deactivation MAC CE | 290 |
| 6.1.3.58 | BFD-RS Indication MAC CE | 306 |
| 6.1.3.59 | SP/AP SRS TCI State Indication MAC CE | 307 |
| 6.1.3.60 | Serving Cell Set based SRS TCI State Indication MAC CE | 308 |
| 6.1.3.70 | Enhanced Unified TCI States Activation/Deactivation MAC CE for Joint TCI States | 322 |
| 6.1.3.71 | Enhanced Unified TCI States Activation/Deactivation MAC CE for Separate TCI States | 322 |
| 6.1.3.76 | Candidate Cell TCI States Activation/Deactivation MAC CE | 331 |
| 6.1.3.77 | Cross-RRH TCI State Indication for UE-specific PDCCH MAC CE | 332 |

（頁碼為各小節標題所在頁；IAB/NCR 專用 beam MAC CE 6.1.3.61/62/66/67/68 未列。）

### [321-005] 6.1.3.14 legacy PDSCH TCI 啟用：最多 8 個
- 出處：TS 38.321 V19.3.0 §6.1.3.14, p.261
- 原文：
  > The codepoint to which the TCI State is mapped is determined by its ordinal position among all the TCI States with Ti field set to 1, i.e. the first TCI State with Ti field set to 1 shall be mapped to the codepoint value 0, second TCI State with Ti field set to 1 shall be mapped to the codepoint value 1 and so on. The maximum number of activated TCI states is 8. The activated TCI states can be associated with at most one PCI different from the Serving Cell PCI at a time;
- 數值：Serving Cell ID 5 bit、BWP ID 2 bit；activated ≤ 8

### [321-006] 6.1.3.47 / 6.1.3.70 unified TCI 啟用：最多 16 個
- 出處：TS 38.321 V19.3.0 §6.1.3.47, p.290；§6.1.3.70, p.322
- 原文（6.1.3.47）：
  > - TCI state ID: This field indicates the TCI state identified by TCI-StateId as specified in TS 38.331 [5]. If D/U is set to 1, 7-bits length TCI state ID i.e. TCI-StateId as specified in TS 38.331 [5] is used. If D/U is set to 0, the most significant bit of TCI state ID is considered as the reserved bit and remainder 6 bits indicate the TCI-UL-State-Id as specified in TS 38.331 [5]. The maximum number of activated TCI states is 16;
- 數值：DL/joint TCI ID 7 bit、UL TCI ID 6 bit；activated TCI state ≤ 16（codepoint 仍 ≤ 8，見 [214-004]；Pi 欄位 P1..P8，Figure 6.1.3.47-1）

### [321-007] 6.1.3.15 PDCCH TCI 指示
- 出處：TS 38.321 V19.3.0 §6.1.3.15, p.261–262
- 原文：
  > The TCI State Indication for UE-specific PDCCH MAC CE is identified by a MAC subheader with LCID as specified in Table 6.2.1-1. It has a fixed size of 16 bits with following fields: …
  > - CORESET ID: … The length of the field is 4 bits;
- 數值：固定 16 bit；CORESET ID 4 bit

### [321-008] BFR MAC CE 格式要點
- 出處：TS 38.321 V19.3.0 §6.1.3.23, p.267
- 原文：
  > The BFR MAC CE and Truncated BFR MAC CE have a variable size. They include a bitmap and in ascending order based on the ServCellIndex, beam failure recovery information i.e. octets containing candidate beam availability indication (AC) for SCells indicated in the bitmap. For BFR MAC CE, a single octet bitmap is used when the highest ServCellIndex of this MAC entity's SCell for which beam failure is detected and the evaluation of the candidate beams according to the requirements as specified in TS 38.133 [11] has been completed is less than 8, otherwise four octets are used. A MAC PDU shall contain at most one BFR MAC CE.

### [321-009] SP CSI-RS / SP CSI 報告 / SP SRS 啟用 MAC CE 欄位
- 出處：TS 38.321 V19.3.0 §6.1.3.12 p.258；§6.1.3.16 p.262；§6.1.3.17 p.263
- 原文（6.1.3.12）：
  > - A/D: This field indicates whether to activate or deactivate indicated SP CSI-RS and CSI-IM resource set(s). The field is set to 1 to indicate activation, otherwise it indicates deactivation;
  > - SP CSI-RS resource set ID: This field contains an index of NZP-CSI-RS-ResourceSet containing Semi Persistent NZP CSI-RS resources, … The length of the field is 6 bits;
- 原文（6.1.3.16）：
  > It has a fixed size of 16 bits with following fields: … Si: This field indicates the activation/deactivation status of the Semi-Persistent CSI report configuration …
- 原文（6.1.3.17）：
  > - A/D: This field indicates whether to activate or deactivate indicated SP SRS resource set. The field is set to 1 to indicate activation, otherwise it indicates deactivation;
- 原文（6.1.3.13, p.260）：
  > The maximum number of mapped CSI Trigger States is 63;

---

## J. TS 38.300 — 概述段落

### [300-001] 下行 MIMO 概述
- 出處：TS 38.300 V19.3.0 §5.2.1, p.47–48
- 原文：
  > Demodulation Reference Signal (DMRS) based spatial multiplexing is supported for Physical Downlink Shared Channel (PDSCH). Up to 8, 12, 16 and 24 orthogonal DL DMRS ports are supported for type 1, type 2, enhanced type 1, and enhanced type 2 DMRS respectively. Up to 8 orthogonal DL DMRS ports per UE are supported for SU-MIMO and up to 4 orthogonal DL DMRS ports per UE are supported for MU-MIMO. The number of SU-MIMO code words is one for 1-4 layer transmissions and two for 5-8 layer transmissions.
  > The DMRS and corresponding PDSCH are transmitted using the same precoding matrix and the UE does not need to know the precoding matrix to demodulate the transmission. The transmitter may use different precoder matrix for different parts of the transmission bandwidth, resulting in frequency selective precoding. The UE may also assume that the same precoding matrix is used across a set of Physical Resource Blocks (PRBs) denoted Precoding Resource Block Group (PRG).
- 數值：SU-MIMO ≤ 8 port/UE；MU-MIMO ≤ 4 port/UE；1–4 層 1 CW、5–8 層 2 CW
- 說明：PDSCH 是「透明 precoding」——precoder 不必告訴 UE（DM-RS 同 precoder）。

### [300-002] 上行 MIMO 概述
- 出處：TS 38.300 V19.3.0 §5.3.1, p.51
- 原文：
  > Two transmission schemes are supported for PUSCH: codebook based transmission and non-codebook based transmission.
  > For codebook based transmission, the gNB provides the UE with a transmit precoding matrix indication in the DCI. The UE uses the indication to select the PUSCH transmit precoder from the codebook. For non-codebook based transmission, the UE determines its PUSCH precoder based on wideband SRI field from the DCI.
  > … For a given UE, up to 4 or up to 8 layer transmissions are supported. The number of code words is one for 1 to 4 layer transmission and two for 5 to 8 layer transmission. When transform precoding is used, only a single MIMO layer transmission is supported.

### [300-003] Beam level mobility（L1/L2，不需 RRC）
- 出處：TS 38.300 V19.3.0 §9.2.3.1, p.97
- 原文：
  > Beam Level Mobility does not require explicit RRC signalling to be triggered. Beam level mobility can be within a cell, or between cells, the latter is referred to as inter-cell beam management (ICBM). … The gNB provides via RRC signalling the UE with measurement configuration containing configurations of SSB/CSI resources and resource sets, reports and trigger states for triggering channel and interference measurements and reports. … Beam Level Mobility is then dealt with at lower layers by means of physical layer and MAC layer control signalling, and RRC is not required to know which beam is being used at a given point in time.
  > SSB-based Beam Level Mobility is based on the CD-SSB associated to the initial DL BWP … Beam Level Mobility can be also performed based on CSI-RS, if configured for the active DL BWP.

### [300-004] UE-initiated beam report（Rel-19）
- 出處：TS 38.300 V19.3.0 §9.2.3.1, p.97
- 原文：
  > For UE-initiated beam reporting, Mode A and Mode B are supported, where upon detection of an event, UE transmits a UE Initiated Report Indicator (UEIRI) indication in a PUCCH resource to indicate transmission of a beam report. Corresponding to the UEIRI indication, in Mode A, the UE transmits the beam report on a PUSCH indicated by a DCI, while in Mode B, the UE transmits the beam report on a type1 CG PUSCH associated to the PUCCH resource.

### [300-005] Beam failure detection and recovery 概述
- 出處：TS 38.300 V19.3.0 §9.2.8, p.129
- 原文：
  > For beam failure detection, the gNB configures the UE with beam failure detection reference signals (SSB or CSI-RS) and the UE declares beam failure when the number of beam failure instance indications from the physical layer reaches a configured threshold before a configured timer expires.
  > After beam failure is detected on SpCell, the UE:
  > - triggers beam failure recovery by initiating a Random Access procedure on the SpCell;
  > - selects a suitable beam to perform beam failure recovery (if the gNB has provided dedicated Random Access resources for certain beams, those will be prioritized by the UE).
  > - includes an indication of a beam failure on SpCell in a BFR MAC CE if the Random Access procedure involves contention-based random access.
  > Upon completion of the Random Access procedure, beam failure recovery for SpCell is considered complete.
  > After beam failure is detected on an SCell, the UE:
  > - triggers beam failure recovery by initiating a transmission of a BFR MAC CE for this SCell;
  > - selects a suitable beam for this SCell (if available) and indicates it along with the information about the beam failure in the BFR MAC CE.

### [300-006] AI/ML-based beam management（Rel-19）
- 出處：TS 38.300 V19.3.0 §22.2.1, p.285
- 原文：
  > AI/ML-based beam management utilizes intra-cell downlink beam prediction of the serving cell to reduce measurement/RS overhead and to improve the accuracy of beam selection. Two types of beam prediction are supported:
  > - Spatial-domain downlink transmission beam prediction for one set of beams based on measurement results of another set of beams where the set of beams for prediction can be SSB or CSI-RS beams and another set of beams for measurement can be SSB or CSI-RS beams; and
  > - Temporal-domain downlink transmission beam prediction for one set of beams based on historic measurement results of another set of beams (these two sets may be different).
  > For AI/ML-based beam management, both Network-side model and UE-side model are supported.
- 38.300 中「multi-antenna / MIMO 總覽」專節：**未找到**（MIMO 內容分散在 §5.2.1、§5.3.1）。

---

## K. 輔助核對（TS 38.331 / TS 38.211）

| ID | 內容 | 出處 |
|---|---|---|
| S331-001 | `nrofReportedRS ENUMERATED {n1, n2, n3, n4}`（groupBasedBeamReporting disabled 分支內） | TS 38.331 V19.3.0 CSI-ReportConfig, p.842 |
| S331-002 | `nrofPorts ENUMERATED {p1,p2,p4,p8,p12,p16,p24,p32}` | TS 38.331 CSI-RS-ResourceMapping, p.862 |
| S331-003 | `maxNrofTCI-States INTEGER ::= 128` | TS 38.331 multiplicity, p.1661 |
| S331-004 | `maxNrofNZP-CSI-RS-ResourcesPerSet = 64`；`maxNrofCSI-SSB-ResourcePerSet = 64` | p.1657–1658 |
| S331-005 | `maxNrofFailureDetectionResources = 10`；`maxNrofCandidateBeams = 16` | p.1658, p.1660 |
| S331-006 | `beamAppTime-r17 ENUMERATED {n1…n336, spare2, spare1}`，單位 symbol | p.1053, p.1055 |
| S331-007 | `maxNrofCodeWordsScheduledByDCI ENUMERATED {n1, n2}` | p.1051 |
| S331-008 | `repetition ENUMERATED { on, off }` | NZP-CSI-RS-ResourceSet, p.1024 |
| S331-009 | beamFailureInstanceMaxCount / beamFailureDetectionTimer / beamFailureRecoveryTimer 值域 | p.1149–1150, p.735 |
| S331-010 | `ng-n1-n2-cbsr-r19`：two-four-three(192), two-six-two(192), two-eight-two(256), four-four-two(128), two-four-four(256), four-four-four(256), four-eight-two(256) bit | p.798 |
| S211-001 | Codeword-to-layer mapping：1–4 層 1 CW；5–8 層 2 CW | TS 38.211 V19.4.0 §7.3.1.3, Table 7.3.1.3-1, p.124 |

---

## L. Beamforming + MIMO 運作流程（每步附出處 ID）

> 下列步驟是把上方條文串成時間順序的整理；步驟名「P1/P2/P3」為業界慣稱，規範中對應的是 SSB sweep 與 NZP-CSI-RS `repetition` off/on，本身無此名詞。

**Step 0 — gNB 組態（RRC，beam 相關資源先配好）**
- SSB 圖樣與數量：Case A–G、L̄max/Lmax ∈ {4, 8, 64} → [213-001]、[213-002]
- CSI-RS / TCI-State / CSI-ReportConfig 結構 → [214-002]、[214-003]、[214-031]~[214-033]、[214-070]
- 層-3 beam mobility 不需 RRC 參與 → [300-003]

**Step 1 — 初始接入：SSB beam sweep（慣稱 P1）**
1. gNB 在 half frame 內送最多 Lmax 個 SSB（各自一個 beam），初始選細胞假設 20 ms 週期 → [213-001]~[213-003]
2. UE 量 SS-RSRP（同 SSB index 內平均；FR2 用 receiver branch 合成訊號）→ [215-001]、[215-003]
3. UE 由 PBCH DM-RS（＋payload）得 SSB index → [213-002]
4. UE 在該 SSB 關聯的 PRACH occasion/preamble 發 Msg1，隱式告知 gNB 選到的 beam → [213-004]
5. 未收到 TCI 設定／啟用前，PDCCH/PDSCH DM-RS 預設與此 SSB QCL（typeA + typeD）；UL 空間濾波同 RAR/MsgA PUSCH → [214-006]、[214-009]
6. 未設定 pathloss RS 時，PL 以取得 MIB 的 SSB 估計 → [213-021]

**Step 2 — CSI-RS Tx beam 精修（慣稱 P2）**
1. NZP-CSI-RS resource set `repetition='off'`：UE 不可假設同一 Tx 濾波 → [214-037]
2. reportQuantity = `cri-RSRP`（或 `cri-SINR`），每 resource 1–2 port；periodic CSI-RS 以 qcl-InfoPeriodicCSI-RS 指向 SSB（typeD）→ [214-037]、[214-038]、[214-070]
3. UE 回報 nrofReportedRS（≤4）個 CRI + L1-RSRP（7 bit 絕對 + 4 bit/2 dB 差分）；或 group-based 報 2 個可同收的 beam → [214-040]、[214-042]、[214-044]
4. 量測/報告時域型態依 Table 5.2.1.4-1（P/SP/AP；SP 由 MAC CE 或 SP-CSI-RNTI DCI 啟用）→ [214-035]、[321-009]
5. （Rel-19 選用）AI/ML：以 Set A 量測預測 Set B 的最佳 beam（P-CRI/P-SSBRI/P-L1-RSRP）→ [214-045]、[300-006]

**Step 3 — UE Rx beam 精修（慣稱 P3）**
1. NZP-CSI-RS resource set `repetition='on'`：同一 Tx 濾波、不同 OFDM symbol → UE 掃自己的 Rx beam → [214-037]
2. 此時 CRI 不回報 → [214-036]
3. SRS 端的對應：`usage='beamManagement'`，每 set 同一時刻只送一個 resource → [214-083]

**Step 4 — 通道狀態回報（CSI acquisition for MIMO）**
1. 計算順序 CRI → RI → PMI → CQI → LI → [214-034]
2. reportQuantity = `cri-RI-PMI-CQI` / `cri-RI-LI-PMI-CQI` 等 → [214-039]
3. Codebook 選擇（Type I SP/MP、Type II、eType II、FeType II PS、CJT、Doppler、Rel-19 48/64/128 port 聚合）與 rank 上限 → [214-051]~[214-068]
4. RI/PMI 限制（ri-Restriction、CBSR）、port 子集（portSubsetIndicator）→ [214-054]、[214-069]
5. CQI 表 → [214-050]
6. TDD 互易路徑：antenna-switching SRS（xTyR）→ [214-084]

**Step 5 — TCI 指示（gNB 下達要用的 beam）**
- Legacy（Rel-15/16）：
  1. RRC 設定 ≤ M 個 TCI-State（ASN.1 上限 128）→ [214-002]
  2. MAC CE 6.1.3.14 啟用 ≤ 8 個 → 對應 DCI TCI codepoint；ACK 後約 3 ms（n + 3·N_slot^{subframe,μ} + k_mac 項）生效 → [214-004]、[214-008]、[321-005]
  3. PDCCH beam 由 MAC CE 6.1.3.15 指定 → [321-007]
  4. DCI TCI 欄位選 codepoint；排程偏移 ≥ timeDurationForQCL 才依 DCI，否則用最低 CORESET ID 的 beam → [214-010]、[214-011]
- Unified TCI（Rel-17+）：
  1. dl-OrJointTCI-StateList ≤ 128 → [214-003]
  2. MAC CE 6.1.3.47（/6.1.3.70/6.1.3.71）啟用 ≤ 16 個 TCI state，映射到 ≤ 8 個 codepoint → [214-004]、[321-006]
  3. DCI 1_1/1_2/1_3（可無 DL assignment，CS-RNTI）指示 → [214-005]
  4. 正確 ACK 後 ≥ beamAppTime symbols 的第一個 slot 生效，同時更新 DL QCL 與 UL 空間濾波（PUSCH/PUCCH/SRS）→ [214-007]、[214-085]
- UL pathloss RS 綁 beam，≤ 4 個估計，可由 MAC CE 更新 → [213-020]、[213-021]、[321-004]

**Step 6 — PDSCH precoding / layers（資料傳輸）**
1. 傳輸方案唯一：≤ 8 層，DM-RS port 1000–1023 → [214-020]
2. 層數由 DCI 天線埠欄位指示的 DM-RS port 數決定；DM-RS 型態/位置 → [214-023]、[214-024]
3. Codeword：1–4 層 1 CW；5–8 層 2 CW → [214-021]、[300-001]、[S211-001]
4. Precoder 對 UE 透明（DM-RS 同 precoder）；PRG ∈ {2, 4, wideband} 內 precoder 固定 → [214-022]、[300-001]
5. SU-MIMO ≤ 8 DM-RS port、MU-MIMO ≤ 4 port/UE → [300-001]
6. 上行：codebook（SRI+TPMI+rank，coherence 子集）或 non-codebook（SRI）→ [214-080]~[214-082]、[300-002]

**Step 7 — Beam failure detection（BFD）**
1. q0（顯式或由 CORESET TCI 隱式，≤2 個、單 port）→ [213-010]、[213-011]
2. 全部 q0 RS 的假想 BLER 差於 Qout,LR → PHY 以 max(最短 RS 週期, 2 ms) 週期發 BFI → [213-012]、[213-013]
3. MAC：每次 BFI 重啟 beamFailureDetectionTimer、BFI_COUNTER+1；≥ beamFailureInstanceMaxCount 即觸發 BFR；timer 到期歸零 → [321-001]、[321-002]

**Step 8 — Beam failure recovery（BFR）**
1. PHY 依要求回報 q1 中 L1-RSRP ≥ Qin,LR 的候選 → [213-014]
2. SpCell：以 q_new 對應的 PRACH（CFRA 優先）發起 RA；從 slot n+4(+k_mac) 起在 recoverySearchSpaceId 監聽 → [213-015]、[300-005]
3. SCell / 每 TRP（BFD-RS set）：發 (Enhanced) BFR MAC CE，含候選 beam → [321-008]、[321-004]、[300-005]
4. 收到 gNB 回應後 28 symbols 起，PDCCH（CORESET 0）/PUCCH 改用 q_new 的 QCL／最後 PRACH 的空間濾波；unified TCI 下全通道跟隨 → [213-016]、[213-017]
5. 完成條件：SpCell RA 成功（停 beamFailureRecoveryTimer）；SCell 收到對應 HARQ process 的 UL grant → [321-003]
6. 之後回到 Step 5 以正式 TCI 指示覆蓋 q_new 假設 → [213-015]

---

## M. GPT 文件（GPT_search.md、spec_v1.md）錯誤／不精確之處

| # | 文件：位置 | GPT 說法 | 依規範核對 | 出處 |
|---|---|---|---|---|
| 1 | GPT_search.md §1、§7、§9；spec_v1.md「logical_antenna_mode」 | CSI-RS port 上限寫成 32（`nrofPorts` enum 最大 p32），並以此代表 logical port 的全部範圍 | 單一 resource 的 `nrofPorts` 確實 ≤ p32；但 Rel-19 codebook 以**聚合 K（2–4）個 CSI-RS resource** 支援 48/64/128 port，GPT 以 Rel-19 為題卻漏掉這點 | [214-055]、[214-057]、[214-067]、[214-071]、S331-002 |
| 2 | GPT_search.md §7/§9 `codebook.type` enum；spec_v1.md「allowed_families」 | codebook 家族只列 typeI-SinglePanel / typeI-MultiPanel / typeII（spec_v1 另加 typeII-PortSelection） | 漏掉 typeII-r16、typeII-PortSelection-r16/-r17、typeII-CJT(-PortSelection)-r18、typeII-Doppler(-PortSelection)-r18，以及 Rel-19 的 typeI-SinglePanel-r19、typeI-MultiPanel-r19、eTypeII-r19、valueOfN-r19、typeII-Doppler-r19 | [214-068]、[214-032] |
| 3 | GPT_search.md §3 / §7 範例 | 範例寫 `codebook_type: typeI-SinglePanel` 搭配 `max_rank: 8`，但沒說明 rank 上限與 codebook 種類有關 | 8 層只適用 Type I SP；Type I MP ≤ 4；Type II / Type II PS ≤ 2；eType II 系列 ≤ 4 | [214-052]、[214-056]、[214-058]~[214-067] |
| 4 | spec_v1.md「MIMO 的 mode」段 | `portSubsetIndicator`「bitmap 最長 32 bits」 | Rel-15 欄位確為最長 32 bit；但 Rel-19 另有 `portSubsetIndicator-r19`（48/64/128 bit），且此機制只用於 CSI-ReportConfig 的 sub-configuration，並限定搭 Type I codebook | [214-069] |
| 5 | spec_v1.md 三層關係圖「CodebookConfig: Type-I SinglePanel / MultiPanel / Type-II」 | 同 #2，只列 3 種 | 同 #2 | [214-068] |
| 6 | 兩份文件整體 | 全文沒有 beam management 程序（SSB sweep、CSI-RS repetition、L1-RSRP 報告、TCI/QCL、BFD/BFR），只講天線資料結構 | 是缺漏而非錯誤；程序規則見本文件 A、C、G、I 節 | 本文件 A/C/G/I |
| 7 | GPT_search.md §2 | 「38.214 本身就定義 Type-I/Type-II codebook、PMI、RI 等 procedure」 | 正確，但 codebook 表的 port 配置、(N1,N2)/(O1,O2) 等定義在 38.214 Table 5.2.2.2.1-2，GPT 沒引用表號，只引用 38.331 `n1-n2` 欄位說明 | [214-052] |
| 8 | spec_v1.md「Beamforming 如果只使用 3GPP 文件」 | 「最直接的 beamforming parameter 是 38.901 §7.3.1 的 antenna port mapping」 | 38.901 是通道模型的研究報告（TR），不是 gNB 行為規範；3GPP 的「beam」在規範層面以 SSB index / CRI / TCI-State / QCL-TypeD / spatial filter 表示（38.213/38.214），GPT 沒提 | [214-001]、[214-037]、[213-002] |
| 9 | GPT 文件（本次檢視範圍內） | 沒有寫 L1-RSRP 位元寬、nrofReportedRS、TCI 數量、beamFailure 參數 | 因 GPT 未提，無從比對；正確值見 [214-042]、S331-001、[214-003]、[321-005]/[321-006]、S331-009 | — |
| 10 | spec_v1.md CodebookConfig-r19 | `typeI-SinglePanel-r19` 的 `n1-n2-r19` 值列為 eight-three、six-four、sixteen-two、eight-four、sixteen-four、eight-eight | 與 Table 5.2.2.2.1a-1 一致（48:(8,3),(6,4)；64:(16,2),(8,4)；128:(16,4),(8,8)），但 GPT 沒註明這需要聚合 K 個 resource 且 O1=O2=4 | [214-055] |
| 11 | spec_v1.md CodebookConfig 表 | Type I SP 各 `n1-n2` 的 restriction_size（8, 64, 16, 96, 24, 128, 32, 192, 192, 48, 256, 256, 64） | 與 Ac = N1O1N2O2 公式及 Table 5.2.2.2.1-2 一致 → **正確** | [214-052]、[214-054] |

（GPT_search.md 的其餘內容，如 38.901 陣列參數與 38.104 TRXUA/RDN，屬 01 號摘錄範圍，本文件不重複核對。）
