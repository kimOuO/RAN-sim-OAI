# RAN/RU 天線、Beamforming 與 MIMO 規則規格及資料綱要（v2）

## 0. 文件說明

### 0.1 目的
本文件整合 9 份官方文件摘錄（`docs/MIMO/extracts/01`～`09`），為 O-RAN／RAN digital twin simulator 訂定天線、beamforming 與 MIMO 的分層規則及資料綱要（schema）。文件中的每一條規則與每一個欄位均標示規範性等級與出處 ID；出處 ID 可在對應摘錄中查到原文。機器可讀版本見 `antenna_schema_v2.yaml`。

### 0.2 規範性標記
| 標記 | 定義 |
|---|---|
| [3GPP-N] | 3GPP TS 規範性條文（shall／ASN.1 值域／表格） |
| [3GPP-TR] | TR 38.901 通道模型或 calibration 設定，屬研究報告，不具規範性 |
| [ORAN-N] | O-RAN WG4 CUS／MP 規範或 YANG 模型的規範性條文 |
| [DERIVED] | 由原文推導（例如乘積、單位換算、區間公式），原文未逐字寫出 |
| [SIM] | 本專案 simulator 的擴充，無標準依據 |

### 0.3 出處格式
`[ID]` 對應摘錄條目，例如 `[214-052]` 即 `03_procedures.md` 的條目 214-052。ID 前綴與摘錄檔的對照如下：

| 前綴 | 摘錄檔 |
|---|---|
| 901-、104- | 01_38901_38104.md |
| 211-、212- | 02_38211_38212.md |
| 214-、213-、215-、321-、300-、S331-、S211- | 03_procedures.md |
| 331-、306- | 04_38331_38306.md |
| ORAN-、WG1-、PAPER-、C0x | 05_oran.md（舊版 YANG 2022-12-05） |
| CUS- | 06_oran_cus_v21.md |
| MP- | 07_oran_mp_v21.md（v21.01 YANG，內容與 05 衝突時以本檔為準） |
| 133-、1412- | 08_38133_38141-2.md |
| 1411-、37466-、37461-、37462- | 09_38141-1_ALD.md |

頁碼一律採用規格頁首的印刷頁碼。O-RAN 文件沒有頁碼，改以章節號、表號或 YANG 行號（Lnnn）標示。

### 0.4 來源文件總表
| 文件 | 版本 | 日期 | 本地路徑（docs/MIMO/specs/） | 下載 URL |
|---|---|---|---|---|
| 3GPP TR 38.901 | V19.4.0 | 2026-07 | tr_138901v190400p.pdf | https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf |
| 3GPP TS 38.104 | V19.5.0 | 2026-08 | ts_138104v190500p.pdf | https://www.etsi.org/deliver/etsi_ts/138100_138199/138104/19.05.00_60/ts_138104v190500p.pdf |
| 3GPP TS 38.141-2 | V19.5.0 | 2026-08 | ts_13814102v190500p.pdf | https://www.etsi.org/deliver/etsi_ts/138100_138199/13814102/19.05.00_60/ts_13814102v190500p.pdf |
| 3GPP TS 38.141-1 | V19.5.0 | 2026-08 | ts_13814101v190500p.pdf | https://www.etsi.org/deliver/etsi_ts/138100_138199/13814101/19.05.00_60/ts_13814101v190500p.pdf |
| 3GPP TS 37.461 | V19.0.0 | 2025-10 | ts_137461v190000p.pdf | https://www.etsi.org/deliver/etsi_ts/137400_137499/137461/19.00.00_60/ts_137461v190000p.pdf |
| 3GPP TS 37.462 | V19.0.0 | 2025-10 | ts_137462v190000p.pdf | https://www.etsi.org/deliver/etsi_ts/137400_137499/137462/19.00.00_60/ts_137462v190000p.pdf |
| 3GPP TS 37.466 | V19.0.0 | 2025-10 | ts_137466v190000p.pdf | https://www.etsi.org/deliver/etsi_ts/137400_137499/137466/19.00.00_60/ts_137466v190000p.pdf |
| 3GPP TS 38.133 | V19.4.0 | 2026-04 | ts_138133v190400p.pdf | https://www.etsi.org/deliver/etsi_ts/138100_138199/138133/19.04.00_60/ts_138133v190400p.pdf |
| 3GPP TS 38.211 | V19.4.0 | 2026-07 | ts_138211v190400p.pdf | https://www.etsi.org/deliver/etsi_ts/138200_138299/138211/19.04.00_60/ts_138211v190400p.pdf |
| 3GPP TS 38.212 | V19.4.0 | 2026-07 | ts_138212v190400p.pdf | https://www.etsi.org/deliver/etsi_ts/138200_138299/138212/19.04.00_60/ts_138212v190400p.pdf |
| 3GPP TS 38.213 | V19.4.0 | 2026-07 | ts_138213v190400p.pdf | https://www.etsi.org/deliver/etsi_ts/138200_138299/138213/19.04.00_60/ts_138213v190400p.pdf |
| 3GPP TS 38.214 | V19.4.0 | 2026-07 | ts_138214v190400p.pdf | https://www.etsi.org/deliver/etsi_ts/138200_138299/138214/19.04.00_60/ts_138214v190400p.pdf |
| 3GPP TS 38.215 | V19.3.0 | — | ts_138215v190300p.pdf | https://www.etsi.org/deliver/etsi_ts/138200_138299/138215/19.03.00_60/ts_138215v190300p.pdf |
| 3GPP TS 38.300 | V19.3.0 | — | ts_138300v190300p.pdf | https://www.etsi.org/deliver/etsi_ts/138300_138399/138300/19.03.00_60/ts_138300v190300p.pdf |
| 3GPP TS 38.306 | V19.3.0 | — | ts_138306v190300p.pdf | https://www.etsi.org/deliver/etsi_ts/138300_138399/138306/19.03.00_60/ts_138306v190300p.pdf |
| 3GPP TS 38.321 | V19.3.0 | 2026-08 | ts_138321v190300p.pdf | https://www.etsi.org/deliver/etsi_ts/138300_138399/138321/19.03.00_60/ts_138321v190300p.pdf |
| 3GPP TS 38.331 | V19.3.0 | — | ts_138331v190300p.pdf | https://www.etsi.org/deliver/etsi_ts/138300_138399/138331/19.03.00_60/ts_138331v190300p.pdf |
| O-RAN.WG4.TS.CUS.0 | R005-v21.00 | — | oran/O-RAN.WG4.TS.CUS.0-R005-v21.00.docx | https://specifications.o-ran.org/download?id=1104 |
| O-RAN.WG4.TS.MP.0 | R005-v21.01 | — | oran/O-RAN.WG4.TS.MP.0-R005-v21.01.docx | https://specifications.o-ran.org/download?id=1105 |
| O-RAN.WG4.TS.MP-YANGs | R005-v21.01 | YANG revision 至 2026-05-07 | oran/yang-v21.01/ | https://specifications.o-ran.org/download?id=1106 |
| O-RAN M-plane YANG（舊版） | 2022-12-05 | 2022-12-05 | oran-yang/ | O-RAN SC scp-oam-modeling 鏡像（見 05 §0） |
| O-RAN.WG1.TS.Use-Cases | R005-v20.00 | — | ../O-RAN.WG1.TS.Use-Cases-Detailed-Specification-R005-v20.00.docx | — |
| AI_Powered_O-RAN_MIMO_Optimization.pdf | 非規範性 | — | ../AI_Powered_O-RAN_MIMO_Optimization.pdf | — |

說明：
- ETSI URL 依 ETSI 發佈路徑慣例組成。TR 38.901、TS 38.104、38.211、38.214、38.331 的 URL 與既有文件（spec_v1.md、GPT_search.md）一致；其餘 URL 未逐一連線驗證。例外：TS 38.141-1 與 TS 37.461／37.462／37.466 四份已實際下載成功，URL 與本地檔案**已驗證**。
- O-RAN id 1104／1105／1106 與 CUS／MP／YANG 的對應依使用者提供的資訊填寫，本文件未核對。
- ETSI 日期取自摘錄標頭；摘錄未記載者以「—」表示。

---

## 1. 分層模型總覽

```
 L0 Site / Sector 座標 ─ GCS 位置、LCS 旋轉 (α,β,γ)、O-RU 座標系、38.141-2 宣告座標系
   │  [901-002..005] [CUS-070] [MP-010 normal-vector] [1412-004] [37466-002/003/014 RET 機械/電子 tilt、bearing]
 L1 Physical Array ─ (Mg,Ng,M,N,P) / O-RAN (M,N,P,Q)、dH/dV (λ) 或 dy/dz (m)、element pattern、極化
   │  [901-010..036] [CUS-071..075] [MP-010..013]
   │      ▲ element index k = q·P·M·N + p·M·N + m·N + n   [CUS-072]
 L2 RF / TRX / eAxC ─ 38.104 TRXUA→TAB→RDN→AA（僅 1-H）、TRX、eAxC(16 bit)、增益與功率預算
   │  [104-031/032] [CUS-003/004/076] [MP-050/070/080] [1411-001..011 傳導宣告 D.x]
 L3 Beam ─ analog(TD) / digital(FD) / hybrid、beamId(15 bit, 0 = 不做 BF)、SE1/SE2/SE11/SE19 權重、GoB 屬性、tilt offset
   │  [CUS-010..033, 040..063] [MP-005, 040..049, 130/131] [104-040] [1412-010]
 L4 Logical Antenna Port (38.211) ─ PDSCH 1000+、CSI-RS 3000+、SSB 4000（單一 port）、QCL
   │  [211-001..009, 016, 023, 031..034, 040]
 L5 MIMO / CSI Config (38.214 / 38.331) ─ TCI/QCL、CSI-RS resource、CodebookConfig、maxMIMO-Layers、UE capability
   │  [214-001..085] [331-001..040] [306-001..036] [212-001..026]
 L6 Runtime / Procedure State ─ SSB sweep、CSI 報告、TCI 啟用與生效、layers、BFD/BFR、TRX control
      [213-001..021] [321-001..009] [133-001..033] [CUS-080..082] [MP-121/122] [37466-008..021 ALD/RET 狀態機]
```

說明：Iuant 介面（RETAP／TMAAP）跨兩層——RET 的**幾何結果**（機械 tilt、電子 tilt、bearing）屬 L0，其**控制協定與狀態機**（device type、程序碼、TCP busy、alarm、校正/組態旗標）屬 L6；ALD 的物理連接（ALD port、RS485／Modem option、HDLC 參數）則掛在 L2／L6 之間，本文件放在 L6 的 `ald[]`。

### 1.1 3GPP 未標準化的對應（element → TRX → port）
- 3GPP 將 antenna port 定義為邏輯概念，未規定 port 與實體元件或 RF 鏈的對應 [211-001]。DL 的 layer→port 為恆等映射，gNB precoding 對 UE 透明 [211-016][300-001]。
- TS 38.104 規定 TRXUA 內的 TX/RX 單元數為 implementation specific，RDN 以 implementation specific 方式分配功率，TAB→cell/beam 的對應為 implementation dependent [104-031][104-046]。
- TR 38.901 僅在 calibration 表中以 (M,N,P,Mg,Ng;Mp,Np) 描述 element→TXRU 的維度 [901-060]，並給出一條垂直 ULA 的 tilt 權重式 [901-030]。一般化的 sub-array 權重屬「未找到」[901-068]。

### 1.2 O-RAN 補足的部分
| 缺口 | O-RAN 的補足 | 出處 |
|---|---|---|
| 元件編號 | k = f(m,n,p,q)，同時作為權重、antMask 與 array-element-id 的索引 | [CUS-072] |
| 陣列幾何 | tx-arrays/rx-arrays：M、N、Q、間距（m）、法向量、左下元件位置、極化 | [MP-010][CUS-071] |
| RF 串流 | eAxC 16 bit = DU_Port｜BandSector｜CC｜RU_Port；每個 eAxC 同一時間只承載一個 spatial stream | [CUS-003][CUS-004] |
| 權重 | SE1（每 section）、SE11（每 PRB bundle）、SE19（多 port、compact）；權重數 = K | [CUS-041][CUS-048][CUS-056] |
| 空間流與 CSI port | `number-of-spatial-streams`：舊版 YANG 描述「DL 等於 38.214 CSI 的 antenna port 數」；v21.01 改為「O-RU 支援的 DL 與 UL 最大累計空間流數」 | [ORAN-M05][MP-070] |
| 權重檔 | 格式為 O-RU implementation specific | [MP-047] |

---
## 2. L0 — Site／Sector 座標

### 2.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L0-01 | 球座標：θ 為 zenith 角，自 +z 軸量起；φ 為 azimuth 角，在 x-y 平面內自 +x 軸量起 | θ=0 指向天頂，θ=90° 指向水平 | [3GPP-TR] | 901-001 | TR 38.901 §7.1.1, Fig 7.1.1, p.18 |
| R-L0-02 | element pattern 定義在 LCS；陣列在 GCS 中以平移表示位置、以旋轉表示朝向 | — | [3GPP-TR] | 901-002 | §7.1.2, p.19 |
| R-L0-03 | 朝向旋轉 (α 方位, β 下傾, γ 斜角)，intrinsic 旋轉順序 z→ẏ→ẍ；R = Rz(α)Ry(β)Rx(γ)，R⁻¹ = Rᵀ | 實數，度 | [3GPP-TR] | 901-003, 901-004 | §7.1.3, Eq 7.1-2～7.1-5, p.19–21 |
| R-L0-04 | GCS 方向在計算 pattern 前須轉換為 LCS 角度 (θ′,φ′)；極化 field 另需乘上 ψ 旋轉 | Eq 7.1-7/8、7.1-11～17 | [3GPP-TR] | 901-005, 901-006 | §7.1.3, p.21–23 |
| R-L0-05 | 僅有機械下傾時 α=γ=0，可使用簡化式 | Eq 7.1-18/19 | [3GPP-TR] | 901-007 | §7.1.4, p.23 |
| R-L0-06 | calibration 預設每站 3 個 sector，指向 30°、150°、270° | — | [3GPP-TR] | 901-061 | Table 7.8-1, p.100 |
| R-L0-07 | O-RAN 陣列座標系：原點位於左下元件中心；x 為 broadside，y 沿 column 向右，z 指向天頂；φ 繞 z 軸（0°＝broadside，90°＝y 軸）；θ 繞 y 軸（0°＝天頂，90°＝水平）；ψ 為極化角 | — | [ORAN-N] | CUS-070 | CUS §12.5.2, Fig 12.5.2-84 |
| R-L0-08 | O-RU 座標系等同 O-RU 內某一陣列的陣列座標系，由設計固定 | — | [ORAN-N] | CUS-070 | CUS §12.5.2 |
| R-L0-09 | SE2 的指向角 bfAzPt／bfZePt 採用 38.901 §7.1 的 LCS 定義（分別為 φ′、θ′） | — | [ORAN-N] | CUS-042 | CUS Annex F（normative） |
| R-L0-10 | 38.141-2 的宣告座標系：原點與方向由製造商宣告（D.1/D.2）；φ ∈ [−180°, 180°]；θ ∈ [−90°, 90°] 為仰角型，向下傾為正 | — | [3GPP-N] | 1412-004, 1412-010 | TS 38.141-2 §4.14, Fig 4.14-1, p.90–91 |
| R-L0-11 | 38.141-2 的 θ 與 38.901 的 zenith θ 換算：θ_141 = θ_901 − 90° | — | [DERIVED] | 1412-004 | 同上 |
| R-L0-12 | BS class 最小距離：1-C/1-H/1-O 為 WA 35 m、MR 5 m、LA 2 m；2-O 最小耦合損耗為 WA 70 dB、MR 53 dB、LA 45 dB | — | [3GPP-N] | 104-034 | TS 38.104 §4.4, p.31–32 |
| R-L0-13 | O-RAN 陣列法向量 zenith-angle 與 38.901 下傾 β 的關係 β ≈ zenith − 90° 為推論，未經 CUS 明文確認 | — | [DERIVED] | ORAN-017 | Y-UP L715 |
| R-L0-14 | 天線經緯度、方位角、高度、RET/digital tilt 為 WG1 cell shaping 的 O1 輸入（多數未指定 3GPP 參考） | — | [ORAN-N] | WG1-005 | WG1 Table 4.6.4.3-1 |
| R-L0-15 | RET tilt 的符號慣例為正值向下傾（tilt_deg > 0 ⇒ 主瓣位於天線軸正交方向之下）；與 38.141-2 宣告座標系的 θ 同號，與 38.901 zenith θ 的關係為 θ_901 = 90° + tilt_deg | — | [3GPP-N]（換算式為 [DERIVED]） | 37466-002, 1412-004 | TS 37.466 V19.0.0 §3.1, p.7–8 |
| R-L0-16 | 電氣 tilt 與機械 tilt 是**分開的兩個值**：機械 tilt 由安裝幾何固定（device data 0x26），電氣 tilt 由 RET 可調；總下傾 = 機械 + 電氣 | — | [3GPP-N] | 37466-002, 37466-014 | TS 37.466 §3.1 p.7–8；Annex B Table B.1 p.46 |
| R-L0-17 | 電氣 tilt 必須落在裝置宣告的 `[min_electrical_tilt, max_electrical_tilt]`（device data 0x07／0x06）內；超出則 SetTilt 回 `OutOfRange`。規格**未給固定絕對值域** | 值域由裝置宣告 | [3GPP-N] | 37466-012, 37466-014 | TS 37.466 §6.6.3 p.25–26；Annex B p.46 |
| R-L0-18 | RET tilt 的線上量化步距為 0.1°：`tilt_value = round(tilt_deg × 10)`，2 octets signed integer、2 補數、little endian；antenna bearing 同為 0.1° 步距（uint16，0..3599 = 0..359.9°） | 解析度 0.1° | [3GPP-N] | 37466-003, 37466-005, 37466-014 | TS 37.466 §3.1 p.8；§4.4 p.9；Annex B p.46 |

### 2.b Schema 欄位
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| site.site_id | string | — | — | — | [SIM] | — |
| site.position_gcs {x,y,z} | float×3 | — | m | — | [3GPP-TR] | 901-002 |
| site.latitude / longitude | float | −90..90／−180..180 | deg | — | [ORAN-N] | WG1-005 |
| site.antenna_height | float | — | m | — | [ORAN-N] | WG1-005 |
| sector.sector_id | uint | — | — | — | [SIM] | CUS-003（BandSector_ID 概念） |
| sector.orientation.bearing_alpha | float | 實數 | deg | 0 | [3GPP-TR] | 901-003 |
| sector.orientation.downtilt_beta | float | 實數 | deg | 0 | [3GPP-TR] | 901-003, 901-007 |
| sector.orientation.slant_gamma | float | 實數 | deg | 0 | [3GPP-TR] | 901-003 |
| bs_class | enum | WA, MR, LA | — | — | [3GPP-N] | 104-034, 1412-010 (D.6) |
| declared_coordinate_system {ref_point, orientation} | object | — | — | — | [3GPP-N] | 1412-010 (D.1, D.2) |
| sector.ret.electrical_tilt_deg | float（線上 int16，步距 0.1°） | [min_electrical_tilt_deg, max_electrical_tilt_deg]；正值向下 | deg | — | [3GPP-N] | 37466-003, 37466-012 |
| sector.ret.min_electrical_tilt_deg | float（線上 int16，步距 0.1°） | 裝置宣告（device data 0x07） | deg | — | [3GPP-N] | 37466-014 |
| sector.ret.max_electrical_tilt_deg | float（線上 int16，步距 0.1°） | 裝置宣告（device data 0x06） | deg | — | [3GPP-N] | 37466-014 |
| sector.ret.installed_mechanical_tilt_deg | float（線上 int16，步距 0.1°） | 安裝固定（device data 0x26） | deg | — | [3GPP-N] | 37466-014 |
| sector.ret.antenna_bearing_deg | float（線上 uint16 0..3599） | 0..359.9 | deg | — | [3GPP-N] | 37466-014 (0x25) |
| sector.ret.antenna_model_number | string（ASCII ≤15） | 可列印 ASCII 32..126 | — | — | [3GPP-N] | 37466-014 (0x01), 37466-006 |
| sector.ret.antenna_serial_number | string（ASCII ≤17） | 同上 | — | — | [3GPP-N] | 37466-014 (0x02) |
| sector.ret.base_station_id / sector_id_ald | string（ASCII ≤32） | 同上 | — | — | [3GPP-N] | 37466-014 (0x23/0x24) |

---

## 3. L1 — Physical Array

### 3.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L1-01 | BS 天線為均勻矩形 panel 陣列，共 Mg·Ng 個 panel（Mg 為每 column 的 panel 數，Ng 為每 row 的 panel 數）；此結構原文註明是為 calibration 而列 | Mg, Ng ≥ 1 | [3GPP-TR] | 901-010 | TR 38.901 §7.3.0, p.28 |
| R-L1-02 | panel 水平間距 d_g,H、垂直間距 d_g,V | calibration 值：2.5λ（Table 7.8-2/-3）、4λ（Table 7.8-4） | [3GPP-TR] | 901-011 | §7.3.0 p.28；Table 7.8-2～-4 |
| R-L1-03 | M 為每 column 中「同極化」element 數，N 為 column 數 | 正整數 | [3GPP-TR] | 901-012 | §7.3.0, p.28 |
| R-L1-04 | 每 panel element 總數 = M·N·P；陣列總數 = Mg·Ng·M·N·P | — | [DERIVED] | 901-012 | — |
| R-L1-05 | 編號規則：由陣列正面觀察，row 0..M−1 由下往上，column 0..N−1 往 +y 方向遞增 | — | [3GPP-TR] | 901-013 | §7.3.0, Fig 7.3-1, p.28–29 |
| R-L1-06 | element 間距 d_H／d_V | 常用 0.5λ；Table 7.8-6A/6B Config 1 為 d_H=0.5λ、d_V=0.7λ | [3GPP-TR] | 901-014 | §7.3.0, p.28 |
| R-L1-07 | 極化數 P | P ∈ {1, 2} | [3GPP-TR] | 901-015 | §7.3.0, p.28 |
| R-L1-08 | tuple 記法 (Mg, Ng, M, N, P) | — | [3GPP-TR] | 901-016 | §7.3.0, p.28 |
| R-L1-09 | calibration 表改用 (M, N, P, Mg, Ng; Mp, Np)，其中 Mp／Np 為每 panel、每極化的垂直／水平 TXRU 數 | — | [3GPP-TR] | 901-060 | Table 7.8-1A p.101、7.8-2A p.103、7.8-6A p.108、7.8-6B p.110、7.8-6C p.111 |
| R-L1-10 | 每 panel 的 TXRU（port）數 = Mp·Np·P | — | [DERIVED] | 901-060 | — |
| R-L1-11 | BS element pattern（Table 7.3-1）：垂直切面 A = −min{12((θ″−90°)/θ3dB)², SLA_V}；水平切面 A = −min{12(φ″/φ3dB)², A_max}；3D A = −min{−(A_V + A_H), A_max} | θ3dB=65°、SLA_V=30 dB、φ3dB=65°、A_max=30 dB、θ″∈[0°,180°]、φ″∈[−180°,180°] | [3GPP-TR] | 901-020, 901-021, 901-022 | Table 7.3-1, p.29 |
| R-L1-12 | BS element 最大方向增益 | G_E,max = 8 dBi | [3GPP-TR] | 901-023 | Table 7.3-1, p.29 |
| R-L1-13 | 總增益 = G_E,max + A″_dB（原文未明寫加總方式，屬慣例用法） | — | [DERIVED] | 901-023 | — |
| R-L1-14 | 手持 UT pattern（Table 7.3-2） | θ3dB=φ3dB=125°、SLA_V=A_max=22.5 dB、G_E,max=5.3 dBi | [3GPP-TR] | 901-027 | Table 7.3-2, p.31–32 |
| R-L1-15 | 手持 UT 尺寸為 15×7×0 cm，有 8 個候選位置（4 角 + 4 邊中點）；各位置的 (x′,y′,α_u,β_u,γ_u) 見 Table A.6-1；雙場型時 γ_u = 45° | — | [3GPP-TR] | 901-025, 901-036 | §7.3.0 p.29–30；Annex A.6 p.163 |
| R-L1-16 | CPE UT 尺寸為 0×20×20 cm，有 9 個候選位置；原文未提供 CPE 專用 pattern 表 | — | [3GPP-TR] | 901-028 | §7.3.0, Fig 7.3-6, p.32 |
| R-L1-17 | 手持 UT 可選擇模擬 antenna imbalance（逐 port 隨機損耗），預設不模擬 | — | [3GPP-TR] | 901-027 | Table 7.3-2 NOTE |
| R-L1-18 | 場型與功率 pattern 的關係：A″ = \|F″θ\|² + \|F″φ\|² | Eq 7.3-2 | [3GPP-TR] | 901-031 | §7.3.2, p.33 |
| R-L1-19 | 極化 Model-1：ζ 為極化斜角，ζ=0 為垂直極化，ζ=±45° 為交叉極化；以角度相關的 ψ 旋轉 | Eq 7.3-3/3a/3b | [3GPP-TR] | 901-032 | §7.3.2, p.33 |
| R-L1-20 | 極化 Model-2：極化與角度無關；F′θ = √A′·cos ζ，F′φ = √A′·sin ζ | Eq 7.3-4/7.3-5 | [3GPP-TR] | 901-033 | §7.3.2, p.33 |
| R-L1-21 | calibration 使用 Model-2；BS Config 1 為 X-pol ±45°，UT 為 X-pol 0/+90° | — | [3GPP-TR] | 901-063, 901-064 | §7.8.2, Table 7.8-2/-2A, p.101–103 |
| R-L1-22 | 通道係數逐 element 產生（u = UT element，s = BS element），以 element 位置向量 d̄ 計算平面波相位；忽略極化時 2×2 矩陣改為純量 | Eq 7.5-22 | [3GPP-TR] | 901-041, 901-042 | §7.5, p.42, p.49 |
| R-L1-23 | 大頻寬／大陣列模型適用條件：B > c/D（D 為最大孔徑） | Eq 7.6-3/4 | [3GPP-TR] | 901-044 | §7.6.2.1, p.60 |
| R-L1-24 | 近場模型以陣列實體中心為參考點 | Eq 7.6-47～51；k1 與 Beta 參數見 Table 7.6-13-1 | [3GPP-TR] | 901-046, 901-047 | §7.6.13, p.81–82 |
| R-L1-25 | SNS 模型使用陣列高 H、寬 W；建議採用 stochastic 模型；UT 側受 SNS 影響的比例為 90% | Table 7.6.14.1.2-1 等 | [3GPP-TR] | 901-048, 901-049 | §7.6.14, p.82–86 |
| R-L1-26 | calibration 陣列孔徑上限：UMa ≤1.5 m（單極化最多 5k 個 element）、UMi ≤1 m（2.22k）、InF ≤0.71 m（1.12k）、InH ≤0.25 m 矩形（256）或 0.5 m 線性（80） | — | [3GPP-TR] | 901-065 | §7.8.3, p.103 |
| R-L1-27 | O-RAN 天線模型：均勻、矩形、平面陣列；K = M·N·P·Q；M、N、P、Q 皆 > 0（0 保留） | — | [ORAN-N] | CUS-071 | CUS §12.5.1, §12.5.3 |
| R-L1-28 | dy（column 間距）、dz（row 間距）為平均中心距，0 保留 | — | [ORAN-N] | CUS-071 | CUS §12.5.3 |
| R-L1-29 | YANG 中間距以公尺表示（decimal64，5 位小數）；換算為 38.901 的波長單位：d_H = horizontal-spacing / λ，d_V = vertical-spacing / λ | — | [DERIVED] | MP-010, ORAN-014, ORAN-015 | UP grouping parameters L1392 |
| R-L1-30 | 極化列表依角度遞增排序，p = 0..P−1；YANG polarisations 清單 1..2 筆 | MINUS_45, ZERO, PLUS_45, PLUS_90 | [ORAN-N] | CUS-071, MP-010 | CUS §12.5.3；UP typedef polarisation_type L507 |
| R-L1-31 | element index：k = q·P·M·N + p·M·N + m·N + n；m 由下往上、n 由左往右（正面觀察） | 0 ≤ k < K | [ORAN-N] | CUS-072 | CUS §12.5.4 |
| R-L1-32 | CUS 對 element pattern 僅要求回報 −3 dB 與 −6 dB 的水平／垂直波束寬度，未提供 pattern 公式 | — | [ORAN-N] | CUS-071 | CUS §12.5.3 |
| R-L1-33 | array-layer Q 表示重疊陣列（對應 full-connection 模型），可用 shared 關係或 independent-power-budget=false 表示 | — | [ORAN-N] | CUS-075 | CUS Annex K |
| R-L1-34 | co-located 指相同實體 row/column；shared 指 co-located 且共用功率預算；O-RU 須透過 M-plane 回報 relations | SHARED, COALOCATED（原文拼字） | [ORAN-N] | CUS-073, MP-013 | CUS §12.5.5；UP L6003 |
| R-L1-35 | 非 BF 的 O-RU 可建模為每陣列 1 個 element；CAT-B 可用 2 個 element 表示雙極化；為提供 raw SRS，O-RU 可另外暴露單一 element 的 rx-array | — | [ORAN-N] | CUS-074 | CUS §12.5.6 |
| R-L1-36 | CAT-A 的每個 tx/rx-array 只能是單極化；CAT-B 可以是雙極化，但須為每種極化提供單極化 rx-array | — | [ORAN-N] | CUS-005 | CUS §12.2 |
| R-L1-37 | 38.104 composite antenna 由 RDN（線性、被動網路）與 AA 組成 | — | [3GPP-N] | 104-031 | TS 38.104 §4.3.2, p.30 |

### 3.b Schema 欄位（physical_arrays[]）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| name | string | 唯一 | — | — | [ORAN-N] | MP-010 |
| direction | enum | tx, rx | — | — | [ORAN-N] | MP-010 |
| band_number | uint16 | 38.104 band（例如 77 代表 n77） | — | — | [ORAN-N] | MP-072 |
| num_panels_Mg / Ng | uint | ≥1 | — | 1 | [3GPP-TR] | 901-010 |
| num_rows_M | uint16 | ≥1 | — | — | [ORAN-N]/[3GPP-TR] | MP-010, CUS-071, 901-012 |
| num_columns_N | uint16 | ≥1 | — | — | [ORAN-N]/[3GPP-TR] | MP-010, CUS-071 |
| num_polarizations_P | uint | 1..2 | — | — | [ORAN-N]/[3GPP-TR] | MP-010, 901-015 |
| num_array_layers_Q | uint8 | ≥1 | — | 1 | [ORAN-N] | MP-010, CUS-071 |
| polarisations[] {p, type} | list | type ∈ {MINUS_45, ZERO, PLUS_45, PLUS_90} | deg | — | [ORAN-N] | MP-010 |
| horizontal_spacing / vertical_spacing | decimal64(5) | >0 | m | — | [ORAN-N] | MP-010 |
| d_H_lambda / d_V_lambda | float | 由公尺換算 | λ | 0.5 | [DERIVED] | 901-014 |
| panel_spacing_dgH / dgV | float | — | λ | — | [3GPP-TR] | 901-011 |
| normal_vector {azimuth, zenith} | decimal64(4) | — | deg | — | [ORAN-N] | MP-010 |
| leftmost_bottom_position {x,y,z} | decimal64(4) | — | m | — | [ORAN-N] | MP-010 |
| element_pattern.model | enum | 38901_BS_Table7.3-1, 38901_UT_Table7.3-2, isotropic, vendor | — | 38901_BS | [3GPP-TR] | 901-020..027 |
| element_pattern.theta_3dB / phi_3dB | float | BS 65、UT 125 | deg | 65 | [3GPP-TR] | 901-020, 901-027 |
| element_pattern.SLA_V / A_max | float | BS 30、UT 22.5 | dB | 30 | [3GPP-TR] | 901-020, 901-021 |
| element_pattern.G_E_max | float | BS 8、UT 5.3 | dBi | 8 | [3GPP-TR] | 901-023 |
| element_pattern.hpbw_h/v, qpbw_h/v | float | — | deg | — | [ORAN-N] | CUS-071 |
| polarization_model | enum | model1, model2 | — | model2 | [3GPP-TR] | 901-032, 901-033 |
| K_elements | uint | = M·N·P·Q | — | — | [ORAN-N] | CUS-071 |
| element_index_formula | const | q·P·M·N + p·M·N + m·N + n | — | — | [ORAN-N] | CUS-072 |
| relations[] {peer_array, type, pairs} | list | SHARED, COALOCATED | — | — | [ORAN-N] | MP-013 |
| related_o_ru_connectors[] {name, array_element_id[]} | list | uint16 | — | — | [ORAN-N] | MP-010 |

---

## 4. L2 — RF／TRX／eAxC

### 4.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L2-01 | BS type 分為 1-C（僅 conducted，於 antenna connector）、1-H（conducted 於 TAB + OTA 於 RIB）、1-O（僅 OTA，FR1）、2-O（僅 OTA，FR2） | enum | [3GPP-N] | 104-006 | TS 38.104 §3.1, p.21 |
| R-L2-02 | TRXUA→TAB→RDN→AA→RIB 架構僅適用於 1-H；1-O/2-O 沒有 TAB；1-C 只有 antenna connector（外接裝置時改於 port B） | — | [3GPP-N] | 104-030, 104-031, 104-032, 1412-003 | §4.3.1～4.3.3, p.29–31；38.141-2 §4.2 |
| R-L2-03 | TRXUA 的 TX/RX 單元數為 implementation specific；RDN 為線性、被動網路，分配方式為 implementation specific | — | [3GPP-N] | 104-031 | §4.3.2, p.30 |
| R-L2-04 | BS type 1-O 的 TRXUA 至少須有 8 個 TX 單元與 8 個 RX 單元；2-O 原文未規定下限 | ≥8 | [3GPP-N] | 104-032 | §4.3.3, p.31 |
| R-L2-05 | 「TRXUA」僅出現於圖文字，正式用語為 transceiver unit array；composite antenna、RDN 在 §3.1 中無獨立定義 | — | [3GPP-N] | 104-027 | §3.1/§3.3 |
| R-L2-06 | 1-H 須宣告 N_cells 與 TAB connector TX min cell group；TAB→cell/beam 的對應為 implementation dependent | — | [3GPP-N] | 104-046 | §6.1, p.69 |
| R-L2-07 | N_TXU,counted = min(N_TXU,active, 8×N_cells)；N_TXU,countedpercell = N_TXU,counted / N_cells | — | [3GPP-N] | 104-046 | §6.1, p.69 |
| R-L2-08 | 傳導額定功率上限：1-C 的 P_rated,c,AC 為 MR ≤38 dBm、LA ≤24 dBm；1-H 的 P_rated,c,sys 為 MR ≤38 dBm + 10log(N_TXU,counted)、LA ≤24 dBm + 10log(N_TXU,counted)，P_rated,c,TABC 為 MR ≤38 dBm、LA ≤24 dBm；WA 均無上限 | — | [3GPP-N] | 104-047 | §6.2.1, Tables 6.2.1-1/-2, p.69–70 |
| R-L2-09 | 1-O 的 P_rated,c,TRP：WA 無上限，MR ≤ +47 dBm，LA ≤ +33 dBm；2-O 無上限 | — | [3GPP-N] | 104-043 | §9.3.1, Table 9.3.1-1, p.229 |
| R-L2-10 | TRP 準確度：1-O normal 為 ±2 dB，2-O 為 ±3 dB | — | [3GPP-N] | 104-044 | §9.3.2/9.3.3, p.230 |
| R-L2-11 | 7-2x split：CAT-A O-RU 不做 DL precoding（由 O-DU 執行）；CAT-B O-RU 做 precoding，NR 的 precoding 併入頻域 BF 權重 | CAT_A, CAT_B | [ORAN-N] | CUS-001, MP-070 | CUS §3.1, §4.2.1 |
| R-L2-12 | iFFT/FFT、CP 處理與數位 BF 一律位於 O-RU | — | [ORAN-N] | CUS-002 | CUS §4.2.2.1 |
| R-L2-13 | 支援 CAT-A 的 O-DU 須支援最多 8 個 precoded stream，亦可支援更多 | ≥8 | [ORAN-N] | CUS-002 | CUS §4.2.2.1 |
| R-L2-14 | eAxC_ID 共 16 bit，自 MSB 起依序為 DU_Port_ID｜BandSector_ID｜CC_ID｜RU_Port_ID；各子欄位的位寬由 M-plane 設定（0–16 bit，連續配置）；一台 O-RU 只使用一種格式 | 16 bit | [ORAN-N] | CUS-003, MP-050 | CUS §5.1.3.2.7, Table 5.1.3.2.7-2；MP §15.2.2 |
| R-L2-15 | 同一方向（Tx 或 Rx）的 eAxC_ID 在一台 O-RU 內必須唯一 | — | [ORAN-N] | CUS-003, MP-050 | CUS §5.1.3.2.7；MP §15.2.3 |
| R-L2-16 | 一個 eAxC 同一時間只承載一個 spatial stream；CAT-B 在 O-RU 做 precoding 時，一個 eAxC 對應一個 layer（LTE TxD 例外） | — | [ORAN-N] | CUS-004 | CUS §5.1.3.2.7 |
| R-L2-17 | TRX 為 D/A 或 A/D 轉換鏈；數位 BF 時 TRX 數可多於 stream 數，類比 BF 時 TRX 數可少於 element 數 | K ≥ N_TRX（類比）；N_TRX ≥ N_stream（數位） | [ORAN-N] | CUS-004 | CUS §3.1 NOTE |
| R-L2-18 | 階層：O-RU → panel → tx/rx-array → array element → radiator；一個 array 可指派多個 eAxC，但同一方向的一個 eAxC 不得指派給超過一個 array | — | [ORAN-N] | CUS-005 | CUS §12.2 |
| R-L2-19 | 每個 array element 的振幅與相位由 beamId 所指的權重控制，權重經由所屬 RU_port 接收 | — | [ORAN-N] | CUS-005 | CUS §12.2 |
| R-L2-20 | TX 功率預算：m_a = K·m_a,k；g_c,a = g_c,a,k + 10·log10(K)；tx-array-carrier gain 為每個 element 的增益 | dB(mW/FS) | [ORAN-N] | CUS-076, MP-080 | CUS §8.1.3.3；UP L5496 |
| R-L2-21 | tx-arrays 的 min-gain／max-gain（dB）與 independent-power-budget（bool，mandatory） | — | [ORAN-N] | MP-011 | UP L5805 |
| R-L2-22 | rx-arrays 的 gain-correction-range max/min（dB）；總 gain_correction = array-carrier 部分 + eAxC 部分 | — | [ORAN-N] | MP-012, ORAN-038, ORAN-073 | UP |
| R-L2-23 | number-of-ru-ports-ul/dl 為 uint8；值為 255 時改用 extended-*（uint16，≥256）；舊欄位 number-of-ru-ports 已 deprecated | — | [ORAN-N] | MP-070 | MC L636 |
| R-L2-24 | UL/DL port 上限 ≈ N（spatial stream 數）× M（numerology 數），另加特殊 endpoint 數 | — | [ORAN-N] | ORAN-M03, ORAN-M04 | Y-MC（舊版描述） |
| R-L2-25 | fronthaul-split-option 的 range 只允許 7（描述文字寫「2 or 7」） | 7 | [ORAN-N] | ORAN-M09, MP-070 | MC |
| R-L2-26 | Calibration：消除同一 array 內 element 之間的振幅、相位或延遲差；跨 array 校正須屬於同一 calibration group；此功能為 optional | — | [ORAN-N] | CUS-006, MP-150 | CUS §12.3；MP §15.5.1 |
| R-L2-27 | tx-array-carrier 的 active 列舉為 INACTIVE／SLEEP／ACTIVE，預設 INACTIVE；SLEEP 狀態下可關閉陣列所有 element | — | [ORAN-N] | MP-085 | UP L1701；MP §15.3.2 |
| R-L2-28 | 最大功率降低：array-max-power-reduction（每個 index，index 0 表示不降低）、carrier-max-power-reduction（≥0 dB） | dB | [ORAN-N] | MP-011, MP-081, MP-125 | UP L5509；MP §20.6 |
| R-L2-29 | 外接天線延遲 t-da-offset 以 Tc 為單位，預設 0 | — | [ORAN-N] | MP-084 | UP |
| R-L2-30 | RET 經 ALD 以 AISG 2.0（RETAP）透傳：ald-req-msg 為 binary，長度 0..1200 bytes；HDLC 速率 9600 bps；每次傳送間隔至少 3 ms；O-RAN YANG 中沒有 RET tilt leaf | — | [ORAN-N] | MP-140, MP-141 | MP §14.4.1～14.4.3 |
| R-L2-31 | ALD port：port-id 為 uint8（兩個連接器時為 0/1）；開啟 DC 後至少等待 3 s | — | [ORAN-N] | MP-142 | ALDP；MP §14.4.3 |
| R-L2-32 | Shared O-RU 由 host 負責 ALD 操作 | — | [ORAN-N] | MP-143 | MP §19.11.6 |
| R-L2-33 | 1-C 的傳導參考點是 antenna connector、1-H 是 TAB connector（傳導）＋ RIB（OTA，只有 EIRP／EIS）；1-H 的傳導需求對**每一個** TX／RX TAB connector 各自適用，量測時其餘 TAB connector 終端接載 | — | [3GPP-N] | 1411-001, 1411-002, 1411-011, 1411-028 | TS 38.141-1 V19.5.0 §3.1 p.24–26；§4.5.2 p.45–46 |
| R-L2-34 | 1-H 的傳導宣告皆為「per connector」：D.3 頻帶、D.8 single/multi-band、D.11/D.12 max BS RF BW、D.14 CBW/SCS、D.17 載波數、D.21/D.22 額定功率、D.27 band combination。TAB connector 的**總數本身沒有獨立宣告項**，須由這些 per-connector 清單長度間接推得 | — | [3GPP-N] | 1411-020, 1411-021, 1411-022, 1411-023 | TS 38.141-1 §4.6 Table 4.6-1, p.47–52 |
| R-L2-35 | `NTXU,counted = min(NTXU,active, 8 × Ncells)`；`NTXU,countedpercell = NTXU,counted / Ncells`（與 38.104 §6.1 一致，見 R-L2-07） | — | [3GPP-N] | 1411-009 | TS 38.141-1 §6.1.2, p.91 |
| R-L2-36 | `NRXU,counted = min(NRXU,active, 8 × Ncells)`；`NRXU,countedpercell = NRXU,counted / Ncells`；`NRXU,active` = §8 效能需求宣告的 demodulation branch 數（3GPP 對「RX 分支數」唯一有數值語意的定義） | — | [3GPP-N] | 1411-008, 1411-010 | TS 38.141-1 §3.2 p.27–28；§7.6.1 p.187 |
| R-L2-37 | 每個支援 TX 的 TAB connector **恰好**對映到一個同頻帶的 TX min cell group（D.34）；RX 側同理對映到一個 RX min cell group（D.33）。TAB→cell（§7.6.1 寫 cell/beam）的實際對映為 implementation dependent | — | [3GPP-N] | 1411-003, 1411-004, 1411-009, 1411-010, 1411-024 | TS 38.141-1 §3.1 p.26；§6.1.2 p.91；§7.6.1 p.187 |
| R-L2-38 | 每個 TAB connector 至少屬於一個 TAE（TAB connector beam forming）group（D.31），且宣告的 group 數須為「能覆蓋所有 connector 的最小數目」；D.32 equivalent connectors 為「同型連接器只測代表」的依據 | — | [3GPP-N] | 1411-024 | TS 38.141-1 §4.6 Table 4.6-1, p.51 |
| R-L2-39 | 每個 demodulation branch 至少宣告一個對映的 TAB connector（D.37）——這是 TAB connector ↔ RX 分支唯一的標準依據；`Prated,c,sys = Σ_connectors Prated,c,TABC`（單一 carrier），可用以換算系統級總 DL 功率 | — | [3GPP-N] | 1411-007, 1411-025 | TS 38.141-1 §3.2 p.28；Table 4.6-1 p.51 |
| R-L2-40 | **負面規則**：38.141-1 Table 4.6-1 中沒有 MIMO 層數、antenna port 數、`NTXU,active`／`NRXU,active` 的宣告項，也完全沒有 beam／指向角／beamwidth 宣告（後者全在 38.141-2）；層數與 port 數屬 L4/L5 與 UE 能力，不得放進 L2 | — | [3GPP-N] | 1411-020, 1411-026, 1411-028 | TS 38.141-1 §4.6 Table 4.6-1, p.47–55 |

### 4.b Schema 欄位（rf）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| bs_type | enum | 1-C, 1-H, 1-O, 2-O | — | — | [3GPP-N] | 104-006 |
| ru_category | enum | CAT_A, CAT_B | — | — | [ORAN-N] | MP-070 |
| num_tx_units / num_rx_units | uint | 1-O 時 ≥8 | — | — | [3GPP-N] | 104-031, 104-032 |
| n_cells | uint | ≥1 | — | — | [3GPP-N] | 104-046 |
| tab_connectors[] {id, tx_min_cell_group} | list | 僅 1-H | — | — | [3GPP-N] | 104-024, 104-046 |
| n_txu_counted | uint | min(N_TXU,active, 8·N_cells) | — | — | [3GPP-N] | 104-046 |
| rated_carrier_trp | float | 依 BS class 的上限 | dBm | — | [3GPP-N] | 104-043, 1412-013 (D.37) |
| eaxc_format {o_du_port_bitmask, band_sector_bitmask, ccid_bitmask, ru_port_bitmask} | uint16×4 | 位元連續、總和 ≤16 | — | — | [ORAN-N] | MP-050 |
| endpoints[] {name, direction, eaxc_id, array, configured_bf_profile_id, bf_methods[]} | list | eaxc_id 為 uint16，同方向唯一 | — | — | [ORAN-N] | MP-050, MP-061, ORAN-031 |
| number_of_ru_ports_dl / ul | uint8（extended 時為 uint16） | — | — | — | [ORAN-N] | MP-070 |
| number_of_spatial_streams(_dl/_ul) | uint8 | — | — | — | [ORAN-N] | MP-070 |
| tx_array_carriers[] {name, center_freq, bandwidth, active, gain, carrier_max_power_reduction, t_da_offset, reference_level} | list | active ∈ {INACTIVE, SLEEP, ACTIVE} | Hz, dB, Tc | active=INACTIVE | [ORAN-N] | MP-080..085, ORAN-070 |
| tx_array.min_gain / max_gain | decimal64(4) | — | dB | — | [ORAN-N] | MP-011 |
| tx_array.independent_power_budget | bool | — | — | — | [ORAN-N] | MP-011 |
| max_rms_power_per_element m_a_k | float | — | W | — | [ORAN-N] | CUS-076 |
| calibration {self_calibration_support, coordinated_calibration_support, calibration_period} | object | — | min | false | [ORAN-N] | MP-150, MP-151 |
| ald_ports[] {port_id, dc_control_support, supported_connector} | list | ANTENNA_CONNECTOR, RS485_PORT | — | — | [ORAN-N] | MP-142 |
| ~~ret_tilt_deg~~ → 見 L0 `sector.ret.electrical_tilt_deg` | float（線上 int16，步距 0.1°） | 由 device data 0x06/0x07 宣告的 [min,max] | deg | — | [3GPP-N] | 37466-003, 37466-012, 37466-014 |
| declarations.n_cells | uint | ≥1，per operating band（僅 1-H，D.24） | — | — | [3GPP-N] | 1411-023 |
| declarations.n_rxu_active | uint | ≥1，= demodulation branch 數 | — | — | [3GPP-N] | 1411-008 |
| declarations.n_rxu_counted | uint | min(n_rxu_active, 8·n_cells) | — | — | [3GPP-N] | 1411-010 |
| declarations.prated_c_sys_dbm | float | = Σ Prated,c,TABC（單一 carrier） | dBm | — | [3GPP-N] | 1411-007 |
| connectors[].connector_id | uint / string | 標準無此欄位（僅為 schema 索引） | — | — | [SIM] | 1411-020 |
| connectors[].kind | enum | antenna_connector（1-C）, tab_connector（1-H） | — | — | [3GPP-N] | 1411-001, 1411-002 |
| connectors[].band_capability | enum | single-band, multi-band（D.8） | — | — | [3GPP-N] | 1411-021, 1411-006 |
| connectors[].operating_bands[] | list\<band\> | D.3，per connector | — | — | [3GPP-N] | 1411-021 |
| connectors[].channel_bandwidths_by_scs | map\<scs, list\<MHz\>\> | D.14 | MHz | — | [3GPP-N] | 1411-022 |
| connectors[].max_bs_rf_bandwidth_mhz | float | D.11（單頻）／D.12（多頻），per band | MHz | — | [3GPP-N] | 1411-022 |
| connectors[].max_carriers_single_band | uint | D.17，per band | — | — | [3GPP-N] | 1411-022 |
| connectors[].rated_carrier_output_power_dbm | float | D.21，per (band, connector)；依 DL QAM 能力可 1..3 組 | dBm | — | [3GPP-N] | 1411-023, 1411-027 |
| connectors[].rated_total_output_power_dbm | float | D.22，per (band, connector) | dBm | — | [3GPP-N] | 1411-023 |
| connectors[].tx_min_cell_group_id | uint | 支援 TX 者恰好 1 個（per band，D.34） | — | — | [3GPP-N] | 1411-003, 1411-024 |
| connectors[].rx_min_cell_group_id | uint | 支援 RX 者恰好 1 個（per band，D.33） | — | — | [3GPP-N] | 1411-004, 1411-024 |
| connectors[].tae_group_ids[] | list\<uint\> | 至少 1 個（per band，D.31） | — | — | [3GPP-N] | 1411-024 |
| connectors[].equivalent_group_id | uint / null | D.32 | — | null | [3GPP-N] | 1411-024 |
| connectors[].demod_branch_ids[] | list\<uint\> | D.37，每個 branch 至少 1 個 connector | — | — | [3GPP-N] | 1411-025 |
| iuant_modem_spurious_min_hz | const | 2e7（modem ON 時 spurious 只量 >20 MHz） | Hz | 2e7 | [3GPP-N] | 1411-012 |
| port_to_trx_mapping | matrix | — | — | identity | [SIM] | 無標準（見 1.1；104-031、211-001） |
| rf_weight_matrix W_RF (K×N_TRX) | complex matrix | — | — | full-connection | [SIM] | 無標準；僅有 hybrid 的 h(k) 映射 [CUS-071][MP-043] 與 901-030 ULA 權重 |

---
## 5. L3 — Beam（analog／digital，beamId）

### 5.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L3-01 | beam 為天線陣列輻射 pattern 的主瓣；beam centre direction 為半功率輪廓的幾何中心；beam peak direction 為 EIRP 最大的方向；beam direction pair 由兩者組成；beamwidth 以兩個正交切面的半功率寬度表示 | — | [3GPP-N] | 104-001..005, 1412-001 | TS 38.104 §3.1 p.20；38.141-2 §3.1 p.25–27 |
| R-L3-02 | 1-H/1-O/2-O 須對每個 beam 宣告：beam identity、reference beam direction pair、beamwidth、rated beam EIRP、OTA peak directions set，以及各 maximum steering direction 的 beam direction pair 與其 EIRP、beamwidth | — | [3GPP-N] | 104-040 | TS 38.104 §9.2.1, p.228 |
| R-L3-03 | 38.141-2 宣告項目：D.3 beam identifier（最少 5 種 beam：最窄 θ、最窄 φ、最寬 θ、最寬 φ、最高 EIRP）；D.8 reference beam direction pair；D.9 OTA peak directions set；D.10 四個 maximum steering direction（Φmax/Φmin/θmax/θmin）；D.11 rated beam EIRP；D.12 beamwidth；D.13 equivalent beams；D.14 parallel beams | — | [3GPP-N] | 1412-010 | TS 38.141-2 §4.6, Table 4.6-1, p.50–63 |
| R-L3-04 | 其他宣告：D.34–D.36 OTA coverage range；D.37/D.38 rated TRP；D.57/D.58 FBW 低／高頻段的 rated beam EIRP（已宣告時不再宣告 D.11）；D.64 機械下傾 | — | [3GPP-N] | 1412-013, 1412-014 | 同上 |
| R-L3-05 | OTA peak directions set 必須是 OTA coverage range 的子集 | — | [3GPP-N] | 104-014 | TS 38.104 §3.1, p.23 |
| R-L3-06 | EIRP 準確度：1-H/1-O normal 為 ±2.2 dB；1-O extreme 為 ±2.7 dB；2-O normal 為 ±3.4 dB、extreme 為 ±4.5 dB | — | [3GPP-N] | 104-042 | §9.2.2/9.2.3, p.229 |
| R-L3-07 | EIRP 測試容許誤差（normal）：1-H/1-O 在 f ≤3 GHz 為 ±3.3 dB、3–7.125 GHz 為 ±3.5 dB；2-O 依頻段為 ±5.1／±5.4／±5.6／±6.4 dB | — | [3GPP-N] | 1412-002 | TS 38.141-2 Table 6.2.5-1, p.95 |
| R-L3-08 | 只要 beam peak direction 位於 OTA peak directions set 內，TRP 不隨 beamforming 設定改變 | — | [3GPP-N] | 104-043 | §9.3.1, p.229 |
| R-L3-09 | 宣告為 equivalent 且 parallel 的 beam，僅需測試代表 beam；EIRP 以兩個正交極化相加（EIRP = EIRPp1 + EIRPp2） | — | [3GPP-N] | 1412-015, 1412-002 | 38.141-2 §6.1, §6.2.4 |
| R-L3-10 | FBW > 6% 的頻段須宣告兩組額定值 P_rated,c,FBWlow／P_rated,c,FBWhigh | — | [3GPP-N] | 104-041 | §9.2.1, p.228 |
| R-L3-11 | 傳統 ULA 的垂直 electrical tilt 權重：w_m = (1/√M)·exp(−j2π(m−1)d_V cos θ_etilt / λ)；此式僅為固定垂直 tilt，不是一般 beamforming | θ_etilt ∈ [0°,180°]，90° 為 broadside；calibration 值 UMa/UMi 102°、indoor 110° | [3GPP-TR] | 901-030, 901-061 | TR 38.901 §7.3.1, Eq 7.3-1, p.32；Table 7.8-1 |
| R-L3-12 | BF 分為頻域、時域與 hybrid；方法共五類：PDBF、WDBF、ABBF、CIBF、DMRS-BF | — | [ORAN-N] | CUS-010 | CUS §12.4.1 |
| R-L3-13 | YANG beamforming-method-type 共 7 個值：NOBF、PDBF、WDBF、ABBF、CIBF、DMRS_BF_EQ、DMRS_BF_NEQ | enum | [ORAN-N] | MP-005 | UP typedef L536 |
| R-L3-14 | PDBF、WDBF、ABBF 使用 beamId；CIBF 與 DMRS-BF 不使用 beamId，改用 ueId | — | [ORAN-N] | CUS-010 | CUS §12.4.1 |
| R-L3-15 | 同一 RE 上若任一 layer 使用 ABBF，所有 layer 都必須使用 ABBF | — | [ORAN-N] | CUS-010 | CUS §12.4.1 c) |
| R-L3-16 | 支援要求：PDBF 在 O-DU 為 M、在 O-RU 為 CM；WDBF 在兩端皆為 CM（O-RU 只要內部計算權重即必須支援）；ABBF、CIBF、DMRS-BF、multiple beamId tables、NULL-STEERING 皆為 O | — | [ORAN-N] | CUS-011 | CUS Table 10.2.4-1 |
| R-L3-17 | beamId 為 15 bit unsigned；0 表示不做 BF（O-RU 不施加權重，訊號平均送至所有 element）；有效值 1..32767 | 預設 0 | [ORAN-N] | CUS-033, ORAN-063 | CUS §7.5.3.9 |
| R-L3-18 | 未啟用 multiple beamId tables 時，beamId 在整台 O-RU 共用（所有 eAxC 及 UL/DL 共用）；啟用時改依 array-carrier 所設定的 table 解讀；table 索引為 1..255，第一筆為預設的全域 table（大小 32767） | — | [ORAN-N] | CUS-033, MP-050b, MP-082 | CUS §7.5.3.9；MP §15.4.6 |
| R-L3-19 | 非 BF 的 O-RU 若收到含 beamId 的 C-plane，該 beamId 必須為 0 | — | [ORAN-N] | CUS-011 | CUS Table 10.2.4-1 |
| R-L3-20 | beamId 不要求連號；每個 domain 的 beamId 區段 = [initial-beam-id, initial-beam-id + max-number-of-beam-ids − 1] | max-number-of-beam-ids 為 uint16 ≤32767 | [ORAN-N] | CUS-012, MP-044 | CUS §12.4.2.1；BF L237 |
| R-L3-21 | PDBF 的 beam 屬性：beam-type（COARSE/FINE）、beam-group-id（同 group 可同時傳送）、coarse-fine 關係、鄰居 beam；重疊的 beam 不得同時排程，相鄰的 beam 應盡量避免同時排程 | — | [ORAN-N] | CUS-012, MP-045 | CUS §12.4.2.2；BF L464 |
| R-L3-22 | BF YANG 中沒有每個 beam 的方位角、仰角或波束寬度 leaf；權重檔格式為 implementation specific，存放於 o-ran/beamforming/；每個 capabilities-group 至少需能存放 2 個檔案（出廠唯讀檔 + 可修改檔）；啟用失敗時回復出廠檔 | — | [ORAN-N] | MP-045, MP-047 | MP §15.4.3, §12.2 |
| R-L3-23 | 以 RPC activate-beamforming-config-by-capability-group 啟用權重檔（舊 RPC 已 deprecated） | ACCEPTED/REJECTED | [ORAN-N] | MP-048 | BF L1076 |
| R-L3-24 | Beam tilt（數位，作用於整組 predefined beam）：elevation/azimuth-tilt-offset-angle 為 int16，範圍 −90..90 度，預設 0；elevation 負值表示向天頂上移；實際套用角度 = (angle DIV granularity) × granularity；granularity 為 0..30（0 表示不支援）；最小值範圍 −90..0，最大值範圍 0..90；以 capabilities-group 為 key | — | [ORAN-N] | MP-049, CUS-012 | BF L798–L1169；MP §15.4.4 |
| R-L3-25 | 若 run-time-tilt-offset-supported 為 false，須先將該頻段所有 array-carrier 設為 INACTIVE 才能修改 tilt；O-RU reset 後 tilt 回到預設值 | — | [ORAN-N] | MP-049, ORAN-B21 | BF |
| R-L3-26 | BEAM-TILT 為數位 tilt，不改變天線實體位置，也不需操作 ALD | — | [ORAN-N] | MP-049 | MP §15.4.4, §15.4.7.5 |
| R-L3-27 | WDBF：同一 slot 內，每個 beamId 的權重最多更新一次，且須在該 beamId 於 slot 中第一次出現時帶上；若同一 slot 需要不同權重，須改用新的 beamId；PRACH 以 sequence duration 視為一個 slot | — | [ORAN-N] | CUS-014 | CUS §12.4.3.1 |
| R-L3-28 | beam-update-contention-control：啟用時，同一 context 中相同 startSymbolId 的後續訊息也必須帶權重（僅適用 ST1/ST3）；beam-context-gap-period 為 16 bit，單位 µs，0xFFFF 表示 infinite | — | [ORAN-N] | CUS-015, ORAN-034 | CUS §12.4.3.2 |
| R-L3-29 | 權重值在壓縮前為分數，I/Q 絕對值不超過 1；權重個數 = K；時域 BF 顆粒度：頻率為 CC 或 BAND，時間為 SLOT 或 SYMBOL | — | [ORAN-N] | CUS-016, MP-044 | CUS §12.4.3.3；BF L439 |
| R-L3-30 | Hybrid（FD 與 TD 皆可更新）：K = K′·p′；權重向量長度 = K′·(p′+1)；p′ 由 p-dash 回報；0 < K′ ≤ K；h(k) 映射由 fd-weights-mapping 回報 | 例：K=16、K′=4、p′=4 時長度為 20 | [ORAN-N] | CUS-017, CUS-071, MP-043, MP-044 | CUS §12.4.3.4.2, §12.5.3；BF L410 |
| R-L3-31 | Hybrid（FD 可更新、TD 固定）：向量前 K′ 個為 FD 權重（可壓縮），後 K′ 個為 TD beam 編號（不可壓縮） | — | [ORAN-N] | CUS-018 | CUS §12.4.3.4.3 |
| R-L3-32 | ST4 cmdType 1 TIME_DOMAIN_BEAM_CONFIG：啟用後，SE1/3/10/11 只能帶 FD 資訊；tdBeamGrp 與 tdBeamNum 各 15 bit；每個 tdBeamGrp 含 K′ 個 tdBeamNum；numSlots 設為 0；只能使用 ARRAY-COMMAND | — | [ORAN-N] | CUS-019, ORAN-004 | CUS §12.4.3.4.4, §7.2.9.2.1 |
| R-L3-33 | ABBF 本質上是時域 BF，以 SE2 傳送屬性；O-RU 須回報 6 個屬性的有效範圍（對應 YANG leaf 未找到） | — | [ORAN-N] | CUS-020 | CUS §12.4.4 |
| R-L3-34 | CIBF：ST6 週期性傳送每個 ueId 的通道 H（不受收發窗限制）；ST5 每 slot 傳送排程；權重由 O-RU 計算；ueId 對通道資訊的映射為整台 O-RU 共用 | — | [ORAN-N] | CUS-021, CUS-035 | CUS §7.2.7, §12.4.5 |
| R-L3-35 | CIBF 權重公式（informative）：MRC、ZF、RZF/MMSE；DL 以 Ψ 正規化以滿足總功率限制 | — | [ORAN-N] | CUS-022 | CUS Annex J.5 |
| R-L3-36 | WDBF 數學模型：yᵢ = wᵢxᵢ，其中 wᵢ ∈ C^{K×L}；hybrid 時 yᵢ = wᵢ·w′ᵢ·xᵢ | informative | [ORAN-N] | CUS-023 | CUS Annex J.3 |
| R-L3-37 | DMRS-BF 僅適用於 NR PUSCH；EQ 與 NEQ 在整台 O-RU 內只能擇一；ueId 的低位元表示 layer、高位元表示 UE；ueid-max-layer-bits 為 1..4 | 例：4 bit 時每 UE 最多 16 layer、最多 2047 個 UE | [ORAN-N] | CUS-024, MP-046 | CUS §12.6.1；BF L790 |
| R-L3-38 | Null steering 僅適用於 predefined beam：null point 需同時設定 azimuth 與 zenith，elevation null stripe 只設定 zenith；角度單位為 0.1°；null-width 預設 1；控制方法為 NULL-PER-ARRAY 或 NULL-PER-ARRAY-CARRIER；變更設定需要先停用再啟用 array-carrier；若未宣告 max-total-null-(point/stripe)-width，視為不支援該類 null；角度採用 CUS §12.5.2 的陣列座標系 | — | [ORAN-N] | CUS-013, MP-130, MP-131, MP-086 | CUS §12.4.2.3；MP §15.4.7；UP L772, L5898 |
| R-L3-39 | endpoint-beam-capacity：max-beams-per-symbol/slot 等欄位為 uint16，上限 32767；缺少此欄位或值為 0 表示該 endpoint 不支援 BF；O-DU 必須遵守 O-RU 回報的上限 | — | [ORAN-N] | MP-062, ORAN-060, CUS-091 | UP L2118；CUS §7.8.2 |
| R-L3-40 | beamforming-trough-attributes-supported 對應 ABBF，beamforming-trough-ue-channel-info-supported 對應 CIBF；ue-specific-beamforming 的 max-number-of-ues-15bit 為 1..32767 | — | [ORAN-N] | MP-046 | BF L690, L734 |
| R-L3-41 | Shared cell 的 selective transmission 以 PDBF 進行，不得與 multiple beamId tables 併用 | — | [ORAN-N] | CUS-025 | CUS §13.3.1 |
| R-L3-42 | WG1 GoB 最佳化經 O1 設定的參數：水平/垂直波束寬度、beam 方位角與下傾、每 beam／方向的最大與平均發射功率（依 TS 28.541） | — | [ORAN-N] | WG1-002 | WG1 §4.6.3.1 |

### 5.b Section Extension 對照（摘錄 Table 7.6.1-1 中與 beam/MIMO 相關者）
| SE | 名稱 | 主要欄位（位寬） | 適用 ST | 出處 |
|---|---|---|---|---|
| 1 | beamforming weights | bfwCompHdr(8) bfwCompParam bfwI/bfwQ(1–16)×K | 1, 3 | CUS-040, CUS-041 |
| 2 | beamforming attributes | bfaCompHdr(16) bfAzPt bfZePt bfAz3dd bfZe3dd(0–8) bfAzSl bfZeSl(3) | 1, 3 | CUS-042 |
| 3 | DL precoding（僅 LTE TxD/LD-CDD，CAT-B） | codebookIndex(8) layerId(4) txScheme(4) numLayers(4) … beamIdAP1–3(15) | 1, 3 | CUS-043 |
| 6 | non-contiguous PRB（RBG mask） | rbgSize(3) rbgMask(28) symbolMask(14) priority(2) | 0,1,3,5,10,11 | CUS-044 |
| 7 | eAxC mask | eAxCmask(16) | 0, 1, 3 | CUS-045 |
| 8 | regularization factor | regularizationFactor(16) | 5 | CUS-046 |
| 10 | multiple ports grouping | beamGroupType(2) numPortc(6，最多 64) beamId/ueId(15) portListIndex(8) | 1, 3, 5 | CUS-047 |
| 11 | flexible BF weights（每 PRB bundle） | disableBFWs(1) RAD(1) bundleOffset(6) numBundPrb(8) …；extLen 16 bit | 1, 3 | CUS-048 |
| 14 | nulling-layer info（CIBF） | nullLayerInd(8) | 5 | CUS-051 |
| 16 | antenna mapping for UL CIBF | antMask(64，最多 64 天線) | 5 | CUS-053 |
| 17 | user port group | numUeId(4，1..8) | 5（搭配 SE10 10b） | CUS-054 |
| 19 | compact multi-port BF info | disableBFWs(1) repetition(1) priority(2) numPortc(6) symbolMask(14) bfwCompHdr(8)；每 port 另有 portReMask(12) portSymbolMask(14) beamId(15) 與權重；extLen 16 bit | 1, 3 | CUS-056 |
| 20 | dedicated puncturing | numPuncPatterns(8) …；extLen 16 bit | 1,3,5,10,11 | CUS-057 |
| 21 | variable PRB group size for CI | ciPrbGroupSize(8；搭配 ST6 時為 2–254) prgSize(2) | 5, 6 | CUS-058 |
| 24 | PUSCH DMRS config | userGroupSize(5，0–12) dmrsPortNumber(5，0–11) … | 5 | CUS-061 |
| 27 | O-DU controlled dimensionality reduction | beamType(2) numElements（Table 寫 6b，內文寫 8b，0 表示 256） beamId(15) | 5（搭配 SE24） | CUS-063 |
| 29 | cyclic delay（CAT-B） | cdScgSize(4) cdScgPhaseStep(8) | 1, 3, 5 | CUS-064 |
| 32 | rank/TPMI measurement | numOfUeAntPorts(4：2 或 4) tpmiIndex(6：0–27，63 表示無) | 5 | CUS-065 |

共通欄位：extType 7 bit、ef 1 bit；extLen 一般為 8 bit，SE11/SE19/SE20 為 16 bit [CUS-040]。SE1、SE2、SE3、SE11、SE19 只能搭配 ST1/ST3 [CUS-031]。SE23 為調變壓縮，與 mMIMO 無關 [CUS-060]。

### 5.c BF 方法 ↔ Section Type ↔ SE ↔ M-plane（依 CUS-(b) 表整理）
| 方法 | 識別 | ST | 主要 SE | M-plane capability | 出處 |
|---|---|---|---|---|---|
| NOBF | beamId=0 | 1/3，或 U-plane only | — | uplane-only-dl-mode-enable（僅限非 BF 的 CAT-A） | CUS-093, ORAN-003 |
| PDBF | beamId | 1/3 | 無（SE19 可設 disableBFWs=1） | static-properties、beam-information、beam-tilt | CUS-012, MP-044/045/049 |
| WDBF（FD/TD） | beamId + 權重 | 1/3 | SE1/SE11/SE19 | rt-bf-weights-update-support、beamforming-type、granularity、compression | CUS-014..016, MP-042/044 |
| WDBF hybrid | beamId | 1/3 + ST4 cmd 1 | SE1/SE11 | hybrid-beams、p-dash、fd-weights-mapping | CUS-017..019, MP-043 |
| ABBF | beamId + 屬性 | 1/3 | SE2 | beamforming-trough-attributes-supported | CUS-020, MP-046 |
| CIBF | ueId | ST6 + ST5 | SE8/10/14/16/17/21 | ue-specific-beamforming | CUS-021, MP-046 |
| DMRS-BF | ueId（UE + layer） | ST5（+ ST9/10/11） | SE24（必要）、SE25–28/30–32 | dmrs-bf-general-capabilities | CUS-024, MP-046 |
| LTE precoding | beamId + beamIdAP1–3 | 1/3 | SE3 | ru-supported-category | CUS-043 |
| Energy saving | antMask | ST4 cmd 3/4/5 | — | trx-control-capability-info | CUS-080..082, MP-121 |

### 5.d Schema 欄位（beam_capability 與 beams）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| bf_supported | bool | — | — | — | [ORAN-N] | MP-040 |
| capabilities_groups[] {id, band_number, tx_arrays[], rx_arrays[]} | list | id 為 uint16 | — | — | [ORAN-N] | MP-041 |
| rt_bf_weights_update_support | bool | — | — | — | [ORAN-N] | MP-042 |
| beamforming_type | enum | frequency, time, hybrid | — | — | [ORAN-N] | MP-042 |
| initial_beam_id / max_number_of_beam_ids | uint16 | 上限 32767 | — | — | [ORAN-N] | MP-044 |
| frequency_granularity / time_granularity | enum | CC, BAND／SLOT, SYMBOL | — | — | [ORAN-N] | MP-044 |
| p_dash | uint16 | — | — | 1 | [ORAN-N] | MP-044, CUS-019 |
| K_prime_fd_weights | uint | 0 < K′ ≤ K | — | K | [ORAN-N] | CUS-071 |
| fd_weights_mapping[] {k_prime, array_elements[]} | list | — | — | — | [ORAN-N] | MP-043 |
| supported_bf_methods[] | enum list | NOBF, PDBF, WDBF, ABBF, CIBF, DMRS_BF_EQ, DMRS_BF_NEQ | — | — | [ORAN-N] | MP-005, MP-061 |
| bf_compression_methods[] | enum list | no, block floating point, block scaling, µ-law, beamspace I, beamspace II | — | no（16-bit） | [ORAN-N] | CUS-041 |
| endpoint_beam_capacity {max_beams_per_symbol, max_beams_per_slot, max_beam_updates_per_symbol, max_beam_updates_per_slot} | uint16 | 0..32767 | — | 缺少時表示不支援 BF | [ORAN-N] | MP-062 |
| multiple_beamid_tables {supported_max, table_indexes[]} | uint8 | 1..255 | — | 停用 | [ORAN-N] | MP-050b, MP-071 |
| beams[] {beam_id, beam_type, beam_group_id, neighbour_beams[], coarse_fine_relation[]} | list | beam_id 1..32767；beam_type 為 COARSE 或 FINE | — | — | [ORAN-N] | MP-045 |
| beams[].pointing {azimuth, zenith}, beamwidth {az, ze}, sidelobe {az, ze} | float | YANG 中未定義；可沿用 SE2 語意 | deg, dB | — | [SIM]（語意依 CUS-042） | CUS-042, MP-045 |
| beams[].weights (K complex) | complex[] | \|I\|,\|Q\| ≤ 1 | — | — | [ORAN-N] | CUS-016, CUS-041 |
| declared_beams[] {id, ref_pair, peak_set, max_steering_pairs×4, rated_eirp, beamwidth, equivalent[], parallel[]} | list | — | dBm, deg | — | [3GPP-N] | 1412-010, 104-040 |
| beam_tilt {elevation_offset, azimuth_offset, granularity, min, max, run_time_supported} | int16/uint8 | −90..90／0..30 | deg | 0 | [ORAN-N] | MP-049 |
| null_steering {method, intended_nulls[] {azimuth, zenith, width, freq}, beam_id_ranges[]} | object | 角度為 int16，單位 0.1° | 0.1 deg | width=1 | [ORAN-N] | MP-130, MP-131 |
| weight_file_format | string | implementation specific | — | — | [ORAN-N] | MP-047 |
| etilt_theta_deg（ULA legacy） | float | 0..180 | deg | 102 | [3GPP-TR] | 901-030, 901-061 |

---

## 6. L4 — Logical Antenna Port（TS 38.211）

### 6.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L4-01 | antenna port 以「通道可推論性」定義，屬邏輯概念 | — | [3GPP-N] | 211-001 | TS 38.211 §4.4.1, p.14 |
| R-L4-02 | QCL 大尺度參數：delay spread、Doppler spread、Doppler shift、average gain、average delay、spatial Rx parameters | — | [3GPP-N] | 211-002 | §4.4.1, p.14 |
| R-L4-03 | UL port 編號：PUSCH DM-RS 自 0 起；SRS/PUSCH 自 1000 起；PUCCH 自 2000 起；PRACH 為 4000 | — | [3GPP-N] | 211-003 | §6.2, p.33 |
| R-L4-04 | DL port 編號：PDSCH 自 1000 起；PDCCH 自 2000 起；CSI-RS 自 3000 起；SS/PBCH 自 4000 起；PRS 自 5000 起 | — | [3GPP-N] | 211-004 | §7.2, p.121 |
| R-L4-05 | 除非另有規定，UE 不得假設兩個 port 為 QCL | — | [3GPP-N] | 211-005 | §7.2, p.121 |
| R-L4-06 | PDSCH 與其 DM-RS 的通道僅在同一 slot 且同一 PRG 內可互相推論 | — | [3GPP-N] | 211-006 | §7.2, p.121 |
| R-L4-07 | 沒有 CSI-RS 時，PDSCH DM-RS 與 SSB 為 QCL；同一 CDM group 內的 DM-RS 互為 QCL；與 TCI 關聯的 DMRS 為 Type A、Type D 與 average gain 的 QCL | — | [3GPP-N] | 211-007 | §7.4.1.1.2, p.133 |
| R-L4-08 | 同一 CSI-RS resource 內的所有 port 為 QCL（Type A、Type D、average gain） | — | [3GPP-N] | 211-008 | §7.4.1.5.3, p.141 |
| R-L4-09 | 相同 block index 且相同中心頻率的 SSB 為 QCL（含 spatial Rx）；其他 SSB 除 38.213 規定外不得假設 QCL | — | [3GPP-N] | 211-009 | §7.4.3.1, p.151 |
| R-L4-10 | DL layer→port 為恆等映射；port 集合由 DCI 的 Antenna port(s) 欄位決定（38.212） | — | [3GPP-N] | 211-016, 212-001 | §7.3.1.4, p.124–125 |
| R-L4-11 | DL codeword→layer：1–4 層使用 1 個 CW，5–8 層使用 2 個 CW（5=2+3、6=3+3、7=3+4、8=4+4） | layer 1..8 | [3GPP-N] | 211-015, 300-001 | Table 7.3.1.3-1, p.124 |
| R-L4-12 | PDSCH DM-RS 最大正交 port 數：basic type1 為 4（單符號）／8（雙符號），type2 為 6／12；enhanced（dmrs-TypeEnh）type1 為 8／16，type2 為 12／24 | port 1000–1023 | [3GPP-N] | 211-023, 300-001 | Table 7.4.1.1.2-5, p.135；38.300 §5.2.1 |
| R-L4-13 | type1 有 2 個 CDM group，type2 有 3 個 CDM group | — | [3GPP-N] | 211-021, 211-022 | Tables 7.4.1.1.2-1/-2, p.134 |
| R-L4-14 | DM-RS 時域位置：mapping type A 的 l0 為 2 或 3（pos3）；type B 的 l0 = 0；dmrs-AdditionalPosition=pos3 僅在 dmrs-TypeA-Position=pos2 時支援 | — | [3GPP-N] | 211-024 | §7.4.1.1.2, p.132 |
| R-L4-15 | PUSCH DM-RS port 結構與 DL 相同，編號從 0 起：basic type1 為 0–3／0–7，enhanced type2 最多 0–23 | — | [3GPP-N] | 211-025 | Table 6.4.1.1.3-5, p.104 |
| R-L4-16 | UL precoding：non-codebook 時 W 為單位矩陣；codebook 時 W 依 port 數查表（2/4 port 用 Tables 6.3.1.5-1～-7，3 port 用 -48～-50，8 port 用 -9～-47）；未設定 txConfig 時 W = 1 | TPMI 範圍見各表 | [3GPP-N] | 211-011, 211-012 | §6.3.1.5, p.36–40 |
| R-L4-17 | 8-port UL 的 port 映射 f(i)：codebook1 為 0..7；codebook2 為 0,1,4,5,2,3,6,7；codebook3 為 0,4,1,5,2,6,3,7；codebook4 為 0..7 | — | [3GPP-N] | 211-012 | Table 6.3.1.5-8, p.40 |
| R-L4-18 | CSI-RS 單一 resource 的 port 數 N ∈ {1,2,4,8,12,16,24,32}；聚合資源 N_tot ∈ {48,64,128}，(N_tot,K,N) ∈ {(48,2,24), (48,3,16), (64,4,16), (64,2,32), (128,4,32)} | — | [3GPP-N] | 211-031 | §7.4.1.5.3, Table 7.4.1.5.3-6, p.140, p.143 |
| R-L4-19 | CSI-RS port 編號：p = 3000 + p′；N_tot ≤ 32 時 p′ = s + jL（L 為 CDM group 大小，L ∈ {1,2,4,8}）；聚合資源時依 portMappingMethod（method1/method2）重新編號 | — | [3GPP-N] | 211-032 | §7.4.1.5.3, p.140–141 |
| R-L4-20 | CSI-RS RE 位置依 Table 7.4.1.5.3-1（row 1–18）；每一 row 的 port 數 = CDM group 數 × L | — | [3GPP-N] | 211-034 | Table 7.4.1.5.3-1, p.142 |
| R-L4-21 | frequencyDomainAllocation 位元長度：row1 為 4、row2 為 12、row4 為 3、其他為 6；l0 ∈ 0..13，l1 ∈ 2..12 | — | [3GPP-N] | 211-033, 331-002 | §7.4.1.5.3, p.140；38.331 p.862 |
| R-L4-22 | density：X=1 可用 0.5/1/3；X=2、16、24、32 可用 0.5/1；X=4、8、12 只能用 1 | — | [3GPP-N] | 331-002 | 38.331 p.863 |
| R-L4-23 | TRS 的 density ρ = 3、N = 1；UE 不預期 CSI-RS 與 DM-RS 使用相同 RE | — | [3GPP-N] | 211-031 | p.140 |
| R-L4-24 | SSB 占 4 個符號 × 240 個子載波；PSS/SSS/PBCH/PBCH DM-RS 全部使用單一 port 4000；beam sweeping 以不同 SSB index 實現 | — | [3GPP-N] | 211-040 | §7.4.3.1, p.150–151 |
| R-L4-25 | SSB 候選數（非共享頻譜）：Case A/C ≤3 GHz 為 4，否則為 8；Case B 為 4 或 8；Case D、E、F、G 為 64 | L̄max ∈ {4,8,10,20,64}，Lmax ∈ {4,8,64} | [3GPP-N]（數值為 [DERIVED]） | 213-001, 213-002, 211-041 | TS 38.213 §4.1, p.10–11 |
| R-L4-26 | SSB index 的取得：L̄max=4 時由 PBCH DM-RS 取得 2 LSB；L̄max>4 時取得 3 LSB；L̄max=64 時另由 PBCH payload 取得 3 MSB | — | [3GPP-N] | 213-002 | §4.1, p.11 |
| R-L4-27 | ssb-PositionsInBurst 為 bitmap，最左位元對應 SSB index 0，1 表示實際傳送；ssb-periodicityServingCell ∈ {5,10,20,40,80,160} ms，缺省時為 5 ms；初始選擇細胞時假設週期為 20 ms | — | [3GPP-N] | 331-030, 213-003 | 38.331 p.1232–1233；38.213 §4.1 |
| R-L4-28 | SRS resource 的 port 數 ∈ {1,2,4,8}，p_i = 1000+i（nonCodebook 時依 38.214 決定）；符號數 ∈ {1,2,4,8,10,12,14}；comb K_TC ∈ {2,4,8}，對應最大 cyclic shift 數 8/12/6 | — | [3GPP-N] | 211-050, 211-051 | §6.4.1.4, p.112–114 |
| R-L4-29 | PT-RS 使用所關聯 DM-RS port 的 precoding；K_PT-RS ∈ {2,4}；L_PT-RS ∈ {1,2,4} | — | [3GPP-N] | 211-060, 211-061 | §7.4.1.2.2, p.136–137 |
| R-L4-30 | CSI-RSRP 一般使用 port 3000；作為 L1-RSRP 時可使用 3000 與 3001 | — | [3GPP-N] | 215-002 | TS 38.215 §5.1.2, p.10 |
| R-L4-31 | RSRP 參考點：FR1 為 UE 天線接頭；FR2 為同一 receiver branch 的元件合成訊號；使用分集時，回報值不得低於任一分支的量測值 | — | [3GPP-N] | 215-003 | §5.1.1/5.1.2 |
| R-L4-32 | SS-RSRP 只在相同 SSB index 且相同 PCI 的訊號間平均；作為 L1-RSRP 時不受 SMTC 限制 | — | [3GPP-N] | 215-001, 215-004 | §5.1.1, p.9 |

### 6.b Schema 欄位（logical_port_capability）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| pdsch_dmrs.type | enum | type1, type2 | — | type1 | [3GPP-N] | 211-020, 331-014 |
| pdsch_dmrs.type_enh | bool | — | — | false | [3GPP-N] | 211-020 |
| pdsch_dmrs.max_length | enum | len1, len2 | — | len1 | [3GPP-N] | 331-014 |
| pdsch_dmrs.additional_position | enum | pos0..pos3（len2 時限 pos0/pos1） | — | pos2 | [3GPP-N] | 214-023, 214-024 |
| pdsch_dmrs.max_orthogonal_ports | uint | 4, 6, 8, 12, 16, 24 | — | — | [3GPP-N] | 211-023 |
| csi_rs_port_base | const | 3000 | — | 3000 | [3GPP-N] | 211-004 |
| ssb.port | const | 4000 | — | 4000 | [3GPP-N] | 211-040 |
| ssb.L_max | enum | 4, 8, 64 | — | — | [3GPP-N] | 213-002 |
| ssb.case | enum | A..G | — | — | [3GPP-N] | 213-001 |
| ssb.positions_in_burst | bitstring | 長度 = L_max | — | — | [3GPP-N] | 331-030 |
| ssb.periodicity_ms | enum | 5, 10, 20, 40, 80, 160 | ms | 5 | [3GPP-N] | 331-030 |
| srs.max_ports_per_resource | enum | 1, 2, 4, 8 | — | 1 | [3GPP-N] | 211-050, 306-023b |
| ssb_to_beam_map[] {ssb_index, beam_id} | list | — | — | — | [SIM]（規範只定義 QCL 規則，見 211-009；O-RAN beamId 不等於 SSB index，見 ORAN-063） | 211-009, ORAN-063 |

---
## 7. L5 — MIMO／CSI 設定（TS 38.214／38.331／38.306／38.212）

### 7.a 規則：TCI／QCL
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L5-01 | qcl-Type 定義：typeA = {Doppler shift, Doppler spread, average delay, delay spread}；typeB = {Doppler shift, Doppler spread}；typeC = {Doppler shift, average delay}；typeD = {Spatial Rx parameter} | — | [3GPP-N] | 214-001, 331-010 | TS 38.214 §5.1.5, p.50 |
| R-L5-02 | 一個 TCI-State 含 1 或 2 個 DL RS（qcl-Type1 必要，qcl-Type2 可選）；兩個 RS 的 QCL type 不得相同 | — | [3GPP-N] | 214-002, 331-010 | §5.1.5, p.50；38.331 p.1284 |
| R-L5-03 | referenceSignal 為 csi-rs（NZP-CSI-RS-ResourceId）或 ssb（SSB-Index）；RS 只有在 qcl-Type 為 typeC 或 typeD 時才能位於其他 serving cell | — | [3GPP-N] | 331-010 | 38.331 p.1284–1285 |
| R-L5-04 | legacy TCI 設定數上限 M 由 UE 能力 maxNumberConfiguredTCI-StatesPerCC 決定，ASN.1 硬上限 maxNrofTCI-States = 128 | 能力值 ∈ {4,8,16,32,64,128}，FR2 至少 64 | [3GPP-N] | 214-002, S331-003, 306-004, 331-021 | 38.214 p.50；38.331 p.1661；38.306 p.171 |
| R-L5-05 | unified TCI 的 dl-OrJointTCI-StateList 最多 128 個；同時決定 DL QCL 與 UL 空間濾波；UL TCI 上限 maxUL-TCI-r17 = 64 | — | [3GPP-N] | 214-003, 331-040 | p.50；38.331 §6.4 |
| R-L5-06 | TCI-UL-State 的 referenceSignal 可為 ssb、csi-rs 或 srs | — | [3GPP-N] | 331-011 | 38.331 p.1286 |
| R-L5-07 | MAC CE 最多啟用 8 個 TCI state（或 pair），映射到 DCI TCI 欄位的 codepoint | ≤8 codepoint | [3GPP-N] | 214-004, 321-005 | 38.214 p.51；38.321 §6.1.3.14 |
| R-L5-08 | unified TCI MAC CE（6.1.3.47）最多啟用 16 個 TCI state；DL/joint TCI ID 為 7 bit，UL TCI ID 為 6 bit | ≤16 | [3GPP-N] | 321-006 | 38.321 §6.1.3.47, p.290 |
| R-L5-09 | UE 能力 maxNumberActiveTCI-PerBWP ∈ {1,2,4,8}；UE 回報 X 時，不預期同時啟用超過 X 個 QCL typeD 假設 | — | [3GPP-N] | 306-004, 331-021 | 38.306 p.171 |
| R-L5-10 | DCI 1_1 的 TCI 欄位：未啟用 tci-PresentInDCI 時為 0 bit，否則為 3 bit；DCI 1_2 為 0～3 bit；TCI selection 為 0 或 2 bit | — | [3GPP-N] | 212-002, 212-003, 212-006 | TS 38.212 §7.3.1.2.2/3 |
| R-L5-11 | periodic CSI-RS 以 qcl-InfoPeriodicCSI-RS 指向一個 TCI-State；typeD 的來源可為 SSB 或 periodic CSI-RS | — | [3GPP-N] | 214-070, 331-001 | 38.214 §5.2.2.3.1 |

### 7.b 規則：PDSCH／PUSCH 層數與 codeword
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L5-20 | PDSCH 只有一種傳輸方案：最多 8 層，使用 port 1000–1023 | 1..8 | [3GPP-N] | 214-020 | 38.214 §5.1.1, p.18 |
| R-L5-21 | SU-MIMO 每 UE 最多 8 個 DM-RS port；MU-MIMO 每 UE 最多 4 個 | — | [3GPP-N] | 300-001 | 38.300 §5.2.1, p.47–48 |
| R-L5-22 | PDSCH 層數上限：PDSCH-ServingCellConfig.maxMIMO-Layers（1..8，套用於所有 BWP）；PDSCH-Config.maxMIMO-Layers-r16（1..8，每 BWP；未設定時沿用 serving cell 值） | 1..8 | [3GPP-N] | 331-012, 331-013 | 38.331 p.1056, p.1061 |
| R-L5-23 | maxNrofCodeWordsScheduledByDCI ∈ {n1, n2} | — | [3GPP-N] | 331-012, S331-007 | 38.331 p.1051 |
| R-L5-24 | PRG 大小 ∈ {2, 4, wideband}；DCI 1_0/4_0/4_1 固定為 2 PRB；同一 PRG 內 precoder 相同 | — | [3GPP-N] | 214-022 | §5.1.2.3, p.32 |
| R-L5-25 | 未設定 DM-RS 參數前的預設：單層、port 1000、type1、單符號 front-loaded | — | [3GPP-N] | 214-023 | §5.1.6.2, p.65 |
| R-L5-26 | DCI 1_1 Antenna port(s) 欄位為 4～8 bit，依 dmrs-Type／TypeEnh／maxLength 選表（Tables 7.3.1.2.2-1…-10）；兩個 TCI state 時改用「A」版表 | 1/-1A:4、2/-2A:5、3/-3A:5、4/-4A:6、7:5、8:7、9:6、10:8 | [3GPP-N] | 212-001 | 38.212 §7.3.1.2.2, p.260–280 |
| R-L5-27 | PUSCH 傳輸方案分為 codebook 與 nonCodebook；未設定 txConfig 時不得以 DCI 0_1/0_2/0_3 排程，DCI 0_0 為單 port | txConfig ∈ {codebook, nonCodebook} | [3GPP-N] | 214-080, 331-016 | 38.214 §6.1.1, p.225 |
| R-L5-28 | codebook PUSCH：以 SRI、TPMI 與 rank 決定 precoder；codebookSubset ∈ {fullyAndPartialAndNonCoherent, partialAndNonCoherent, nonCoherent}；3 port 只允許 nonCoherent | — | [3GPP-N] | 214-081, 331-016 | §6.1.1.1, p.226–228 |
| R-L5-29 | nonCodebook PUSCH：每個 SRS resource 只有 1 個 port；每個 set 最多 1/2/3/4/8 個 resource（依 UE 能力）；以 SRI 決定 precoder 與 rank | — | [3GPP-N] | 214-082 | §6.1.1.2, p.229–230 |
| R-L5-30 | PUSCH 層數上限：PUSCH-ServingCellConfig.maxMIMO-Layers（1..4）＋ maxMIMO-Layers-v1810（5..8）；PUSCH-Config.maxRank（1..4）＋ maxRank-v1810（5..8） | 1..8 | [3GPP-N] | 331-016, 331-017 | 38.331 p.1107, p.1118 |
| R-L5-31 | UL 最多 4 層或 8 層；1–4 層使用 1 CW，5–8 層使用 2 CW；使用 transform precoding 時只支援單層 | — | [3GPP-N] | 300-002, 211-012 | 38.300 §5.3.1, p.51 |
| R-L5-32 | DCI 0_1 SRI 位寬：nonCodebook 為 ⌈log2 Σ_{k=1}^{min(Lmax,N_SRS)} C(N_SRS,k)⌉，codebook 為 ⌈log2 N_SRS⌉；Precoding information 欄位依 port 數與 maxRank 查表（8 port 時 3～10 bit） | — | [3GPP-N] | 212-010, 212-011 | 38.212 §7.3.1.1.2, p.155–160 |
| R-L5-33 | DCI 0_1 UL DM-RS antenna ports 欄位為 2～6 bit；CSI request 為 0～6 bit（reportTriggerSize）；SRS request 為 2/3 bit；PTRS-DMRS association 為 0/1/2/4 bit | — | [3GPP-N] | 212-012, 212-013, 212-015 | p.161–163 |
| R-L5-34 | SRS usage ∈ {beamManagement, codebook, nonCodebook, antennaSwitching}；usage 為 beamManagement 時，每個 set 同一時刻只能傳送一個 resource | nrofSRS-Ports ∈ {port1, ports2, ports4}，-n8 ∈ {ports8, ports8tdm} | [3GPP-N] | 214-083, 331-018 | 38.214 §6.2.1, p.277；38.331 |
| R-L5-35 | antenna switching 支援的 xTyR 組合：1T2R、1T4R、2T4R、1T=1R、2T=2R、4T=4R、1T6R、2T6R、1T8R、2T8R、4T8R、8T8R、3T=3R、3T6R（依 UE 能力） | — | [3GPP-N] | 214-084 | §6.2.1.2, p.286–287 |
| R-L5-36 | UE 能力 MIMO-LayersDL ∈ {2, 4, 8}，MIMO-LayersUL ∈ {1, 2, 4}；maxNumberMIMO-LayersPDSCH 在 4Rx 為強制的頻段至少 4 層，FR2 至少 2 層；未回報表示該載波不支援 MIMO | — | [3GPP-N] | 331-023, 306-018 | 38.331 p.1418；38.306 p.313 |
| R-L5-37 | UE 能力 pusch-TransCoherence ∈ {nonCoherent, partialCoherent, fullCoherent}；full 隱含支援 partial 與 non，partial 隱含支援 non | — | [3GPP-N] | 306-024, 331-021 | 38.306 p.148 |

### 7.c 規則：CSI 框架與 CSI-RS
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L5-40 | CSI 可包含的量：CQI、PMI、CRI、SSBRI、LI、RI、L1-RSRP、L1-SINR，以及 Rel-18/19 新增的量（TDCP、預測量、CJT calibration 等） | — | [3GPP-N] | 214-030 | 38.214 §5.2.1, p.81 |
| R-L5-41 | 結構：CSI-ReportConfig（N≥1）引用 CSI-ResourceConfig（M≥1），後者含 S≥1 個 resource set；aperiodic 報告由 trigger state 串接 | maxNrofCSI-ReportConfigurations = 48；maxNrofCSI-ResourceConfigurations = 112 | [3GPP-N] | 214-031, 331-004, 331-040 | p.81–82；38.331 §6.4 |
| R-L5-42 | reportConfigType ∈ {periodic, semiPersistentOnPUCCH, semiPersistentOnPUSCH, aperiodic}；resourceType ∈ {aperiodic, semiPersistent, periodic}；同一報告所連結的資源必須具有相同的時域行為 | — | [3GPP-N] | 214-032, 214-033, 331-004 | p.82–83 |
| R-L5-43 | periodic／semi-persistent 資源的 S = 1（group-based v1710/v1800 時 S = 2） | — | [3GPP-N] | 214-033 | p.83 |
| R-L5-44 | P/SP/AP 組合依 Table 5.2.1.4-1：periodic 報告只能搭配 periodic CSI-RS；aperiodic CSI-RS 只能搭配 aperiodic 報告 | — | [3GPP-N] | 214-035 | Table 5.2.1.4-1, p.84–85 |
| R-L5-45 | CSI 計算順序：CRI → RI → PMI → CQI → LI | — | [3GPP-N] | 214-034 | §5.2.1.4, p.84 |
| R-L5-46 | reportQuantity 值域（原文逐字）：none、cri-RI-PMI-CQI、cri-RI-i1、cri-RI-i1-CQI、cri-RI-CQI、cri-RSRP、cri-SINR、ssb-Index-RSRP、ssb-Index-SINR、cri-RI-LI-PMI-CQI、各 -Index 變形、tdcp、Rel-19 的 p-CRI 等 | — | [3GPP-N] | 214-039, 331-008 | §5.2.1.4.2, p.91 |
| R-L5-47 | NZP-CSI-RS 參數：nrofPorts ∈ {p1,p2,p4,p8,p12,p16,p24,p32}；powerControlOffset ∈ [−8, 15] dB（步進 1 dB）；powerControlOffsetSS ∈ {−3, 0, 3, 6} dB | — | [3GPP-N] | 214-070, 331-001, 331-002 | 38.214 p.192；38.331 p.862, p.1022 |
| R-L5-48 | CSI 資源上限：每 set 最多 64 個 NZP resource；每 cell 最多 192 個 NZP resource、64 個 set；每個 config 最多 16 個 set、128 個 resource；每 set 最多 64 個 SSB resource；每 CSI-ResourceConfig 只能有 1 個 SSB set（Ext 時為 2） | — | [3GPP-N] | 331-040, S331-004 | 38.331 §6.4, p.1655–1665 |
| R-L5-49 | CSI-FrequencyOccupation：startingRB 與 nrofRBs 都必須是 4 的倍數；nrofRBs ≥ min(24, BWP 寬度) | — | [3GPP-N] | 331-003 | 38.331 p.833 |
| R-L5-50 | Rel-19 聚合資源：K ∈ [2,4] 個 resource 須有相同的 qcl-info、powerControlOffset、powerControlOffsetSS，且位於 1 或 2 個相鄰 slot 內（中間不得有 DL/UL 切換） | — | [3GPP-N] | 214-071 | §5.2.2.3.1, p.193 |
| R-L5-51 | repetition 只能在所有連結的 reportQuantity 為 cri-RSRP、cri-SINR、其 -Index 變形或 none 時設定；在 LTM 中只能設為 off | — | [3GPP-N] | 214-038, 331-005 | 38.214 p.193；38.331 p.1026 |
| R-L5-52 | trs-Info 表示該 resource set 中所有 resource 使用相同 antenna port | — | [3GPP-N] | 331-005 | 38.331 p.1027 |
| R-L5-53 | UE 能力 csi-RS-IM-ReceptionForFeedback：包含每 CC 可設定的 NZP CSI-RS 數、跨資源 port 總數、同時資源數及同時 port 總數；UE 必須回報 | — | [3GPP-N] | 306-028a, 306-030, 306-031 | 38.306 p.102 |
| R-L5-54 | portSubsetIndicator：Rel-15 為最長 32 bit，bit i 對應 port 3000+i，1 表示啟用；Rel-19 為 48/64/128 bit；僅用於 CSI-ReportConfig 的 sub-configuration，且只能搭配 Type I codebook | — | [3GPP-N] | 214-069 | §5.2.1.4.2, p.99–100 |

### 7.d 規則：Codebook
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L5-60 | Type I SP 2 port：rank ≤ 2；twoTX-CodebookSubsetRestriction 為 6 bit | — | [3GPP-N] | 214-051, 331-009 | Table 5.2.2.2.1-1, p.133 |
| R-L5-61 | Type I SP 4～32 port：P_CSI-RS = 2·N1·N2；(N1,N2)/(O1,O2) 依 Table 5.2.2.2.1-2；N2 = 1 時 i1,2 = 0 且不回報 | 見 7.f 表 | [3GPP-N] | 214-052 | p.133–135 |
| R-L5-62 | Type I SP 最大 rank 為 8；ri-Restriction 為 8 bit（r0 對應 1 層）；CBSR 長度 Ac = N1·O1·N2·O2；codebookMode ∈ {1, 2} | — | [3GPP-N] | 214-052, 214-054, 331-009 | p.134 |
| R-L5-63 | Type I SP 預編碼：W = (1/√P)·[v_{l,m}; φ_n·v_{l,m}]，φ_n = e^{jπn/2}；規範不以 W1·W2 乘積形式書寫 | — | [3GPP-N] | 214-053 | p.134–135 |
| R-L5-64 | typeI-SinglePanel-r19：用於 48/64/128 port（聚合 K 個 resource）；(N1,N2) ∈ 48:{(8,3),(6,4)}、64:{(16,2),(8,4)}、128:{(16,4),(8,8)}；O1 = O2 = 4；rank ≤ 8；codebookMode-r19 ∈ {modeA, modeB}；n1-n2-r19 為 ENUMERATED（不帶 BIT STRING） | — | [3GPP-N] | 214-055, 331-009 | §5.2.2.2.1a, p.139–140；38.331 p.797 |
| R-L5-65 | Type I MP：8/16/32 port；P = 2·Ng·N1·N2；Ng = 2 時 codebookMode 為 1 或 2，Ng = 4 時只能為 1；rank ≤ 4；ri-Restriction 為 4 bit；可用 (Ng,N1,N2) 見 7.f 表（原摘錄未以 PDF 目視核對） | — | [3GPP-N] | 214-056, 331-009 | §5.2.2.2.2, p.145–146 |
| R-L5-66 | typeI-MultiPanel-r19：48/64/128 port；Ng = K；(O1,O2) = (4,4)；rank ≤ 4；ng-n1-n2-cbsr-r19 位元數：two-four-three 192、two-six-two 192、two-eight-two 256、four-four-two 128、two-four-four 256、four-four-four 256、four-eight-two 256；ri-Restriction-r19 為 4 bit | — | [3GPP-N] | 214-057, S331-010, 331-009 | §5.2.2.2.2a；38.331 p.798 |
| R-L5-67 | Type II（Rel-15）：4～32 port；L ∈ {2,3,4}（P = 4 時 L 只能為 2）；NPSK ∈ {4, 8}；rank ≤ 2；typeII-RI-Restriction 為 2 bit；CBSR 長度與 Type I 不同（16/43/32/59/48/75/64/107/107/96/139/139/128） | — | [3GPP-N] | 214-058, 331-009 | §5.2.2.2.3, p.152–156；38.331 p.794 |
| R-L5-68 | Type II PS（Rel-15）：P ∈ {4,8,12,16,24,32}；d ∈ {1,2,3,4} 且 d ≤ min(P/2, L)；rank ≤ 2；RI restriction 為 2 bit | — | [3GPP-N] | 214-059, 331-009 | §5.2.2.2.4, p.158–159 |
| R-L5-69 | typeII-r16：rank ≤ 4；paramCombination-r16 ∈ 1..8（Table 5.2.2.2.5-1）；P = 4 時不得使用 3～8；P < 32 時不得使用 7、8；RI restriction 為 4 bit；numberOfPMI-SubbandsPerCQI-Subband ∈ 1..2 | — | [3GPP-N] | 214-060, 331-009 | §5.2.2.2.5, p.161–162 |
| R-L5-70 | typeII-PortSelection-r16：d ≤ L；paramCombination 1..6；rank ≤ 4 | — | [3GPP-N] | 214-061 | §5.2.2.2.6, p.169 |
| R-L5-71 | typeII-PortSelection-r17：paramCombination-r17 ∈ 1..8；M = 2 時 valueOfN ∈ {2, 4}；rank ≤ 4 | — | [3GPP-N] | 214-062, 331-009 | §5.2.2.2.7, p.170–171 |
| R-L5-72 | Rel-18 CJT：N_TRP ∈ {1..4}；rank ≤ 4；paramCombination-CJT-r18 ∈ 1..7；CJT-PS 的 paramCombination 為 1..5；CBSR-r18 的長度表不含 six-two | — | [3GPP-N] | 214-063, 214-064, 331-009 | §5.2.2.2.8/9 |
| R-L5-73 | Rel-18 Doppler：K ∈ {4,8,12}（aperiodic）或單一 P/SP resource；N4 ∈ {1,2,4,8}（PS 版本為 1）；paramCombination-Doppler-r18 ∈ 1..9；rank ≤ 4 | — | [3GPP-N] | 214-065, 214-066, 331-009 | §5.2.2.2.10/11 |
| R-L5-74 | Rel-19 Type II 系列：eTypeII-r19（48/64/128 port，paramCombination 1..8）；typeII-FePortSelection-r19（valueOfN-r19，48/64 port，paramCombination 1..7；38.214 另規定不得使用 8）；typeII-Doppler-r19（48/64/128 port，paramCombination-Doppler 1..9）；rank 皆 ≤ 4 | — | [3GPP-N] | 214-067, 331-009 | §5.2.2.2.5a/9a/11a |
| R-L5-75 | 一個 CSI-ReportConfig 只能設定 codebookConfig、-r16、-r17、-r18、-r19 其中之一；-v1730 只能與 -r17 並存；CodebookConfig-r19 的頂層為 CHOICE | — | [3GPP-N] | 331-008, 331-009 | 38.331 p.848 |
| R-L5-76 | UE codebook 能力：maxNumberTxPortsPerResource ∈ {p2..p32}；Type I SP 為必須回報；FR1 單一 active resource 時至少須支援 4 port（wideband 時 8 port），FR2 至少 2 port；額外 codebook 的 port 數下限為 p4 | — | [3GPP-N] | 306-015, 306-017, 331-022 | 38.306 p.74–75 |
| R-L5-77 | CQI 表：table1/2/4 的目標 BLER 為 0.1，table3 為 0.00001；1024QAM 使用 Table 5.2.2.1-5 | — | [3GPP-N] | 214-050 | §5.2.2.1, p.130 |

### 7.e 規則：Beam 報告
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L5-80 | CRI／SSBRI 為 resource set 內的序號（k 對應第 k+1 筆），不是 resource ID 或 SSB index | — | [3GPP-N] | 214-044 | §5.2.1.4.2, p.96, p.101 |
| R-L5-81 | repetition = off 時回報 CRI；repetition = on 時不回報 CRI | — | [3GPP-N] | 214-036 | §5.2.1.4, p.85 |
| R-L5-82 | repetition = on 表示 set 內 resource 使用相同空間濾波且位於不同 OFDM 符號；BM 用的 CSI-RS 每個 resource 只能是 1 或 2 port，且同一 set 內 port 數必須相同 | — | [3GPP-N] | 214-037 | §5.1.6.1.2, p.64 |
| R-L5-83 | L1-RSRP 最多量測 64 個 resource；groupBasedBeamReporting disabled 時回報 nrofReportedRS 個，enabled 時回報 2 個（可同時接收） | nrofReportedRS ∈ {n1..n4}（缺省為 1），v1900 另有 {n6, n8}；N ≤ N_max ∈ {2,4,6,8}（依能力） | [3GPP-N] | 214-040, 331-008, S331-001 | 38.214 p.93；38.331 p.849 |
| R-L5-84 | L1-RSRP 資源設定最多 16 個 set、每 set 最多 64 個 resource、總數最多 128 個 | — | [3GPP-N] | 214-041 | §5.2.1.4.3, p.102 |
| R-L5-85 | L1-RSRP 位寬：絕對值 7 bit，範圍 [−140, −44] dBm，步進 1 dB；差分 4 bit，步進 2 dB，以同一份報告的最大值為參考；報告多於 1 個 RS 或使用 group-based 時採用差分 | — | [3GPP-N] | 214-042, 212-023 | p.102–103；38.212 Table 6.3.1.1.2-6 |
| R-L5-86 | L1-SINR：絕對值 7 bit，範圍 [−23, 40] dB，步進 0.5 dB；差分 4 bit，步進 1 dB；最多 16 個 set、64 個 resource | — | [3GPP-N] | 214-043, 212-024 | §5.2.1.4.4, p.105 |
| R-L5-87 | CRI 位寬 = ⌈log2 K_s^CSI-RS⌉，SSBRI 位寬 = ⌈log2 K_s^SSB⌉；CapabilityIndex 為 2 bit | — | [3GPP-N] | 212-021, 212-023 | 38.212 Table 6.3.1.1.2-3/-6 |
| R-L5-88 | Type I SP 的 RI 位寬：1 port 為 0、2 port 為 min(1,⌈log2 n_RI⌉)、4 port 為 min(2,…)、>4 port 為 ⌈log2 n_RI⌉；WB CQI 為 4 bit；第 2 個 TB 的 CQI 只在 rank 5–8 時出現；子頻差分 CQI 為 2 bit | — | [3GPP-N] | 212-021 | Table 6.3.1.1.2-3, p.51–52 |
| R-L5-89 | Type II 的 RI 位寬 = min(1, ⌈log2 n_RI⌉)；Type I MP 為 min(2, …) | — | [3GPP-N] | 212-022 | Tables 6.3.1.1.2-4/-5 |
| R-L5-90 | Rel-19 AI/ML 預測：量測集合與預測集合各最多 64 個 resource；預測 RSRP 的位寬與 L1-RSRP 相同；另有 ⌈log2 T⌉ bit 的 time instance indicator | — | [3GPP-N] | 214-045, 212-025, 300-006 | §5.2.1.4.3a, p.103–104 |
| R-L5-91 | UE 能力：maxNumberRxBeam ∈ 2..8（FR2 強制支援 Rx beam switching）；maxNumberNonGroupBeamReporting ∈ {n1, n2, n4}；groupBeamReporting；beamReportTiming（依 SCS 以 symbol 數表示）；maxNumberSSB-BFD 與 maxNumberCSI-RS-BFD 的 ASN.1 值域為 1..64（38.306 註明本版最大可回報 16） | — | [3GPP-N] | 306-001, 306-002, 306-003, 306-007, 306-012, 306-013, 331-021 | 38.306 §4.2.7.2；38.331 p.1418 |
| R-L5-92 | beamManagementSSB-CSI-RS：maxNumberSSB-CSI-RS-ResourceOneTx 在 FR2 須 ≥8；maxNumberCSI-RS-Resource 在 FR1 至少為 n8；maxNumberAperiodicCSI-RS-Resource 至少為 n4 | — | [3GPP-N] | 306-006, 306-026 | 38.306 p.60 |

### 7.f 查表：Type I (N1,N2)／(O1,O2)／CBSR 位元數
| P | (N1,N2) | (O1,O2) | Type I SP CBSR（bit） | Type II CBSR（bit） | 出處 |
|---|---|---|---|---|---|
| 4 | (2,1) | (4,1) | 8 | 16 | 214-052, 331-009 附錄 A |
| 8 | (2,2) | (4,4) | 64 | 43 | 同上 |
| 8 | (4,1) | (4,1) | 16 | 32 | 同上 |
| 12 | (3,2) | (4,4) | 96 | 59 | 同上 |
| 12 | (6,1) | (4,1) | 24 | 48 | 同上 |
| 16 | (4,2) | (4,4) | 128 | 75 | 同上 |
| 16 | (8,1) | (4,1) | 32 | 64 | 同上 |
| 24 | (4,3) | (4,4) | 192 | 107 | 同上 |
| 24 | (6,2) | (4,4) | 192 | 107 | 同上 |
| 24 | (12,1) | (4,1) | 48 | 96 | 同上 |
| 32 | (4,4) | (4,4) | 256 | 139 | 同上 |
| 32 | (8,2) | (4,4) | 256 | 139 | 同上 |
| 32 | (16,1) | (4,1) | 64 | 128 | 同上 |

Type I MP 的 (Ng,N1,N2)：8 port 為 (2,2,1)；16 port 為 (2,4,1)、(4,2,1)、(2,2,2)；32 port 為 (2,8,1)、(4,4,1)、(2,4,2)、(4,2,2)；對應 CBSR 位元數為 8/16/8/64/32/16/128/64 [214-056][331-009]。

### 7.g 查表：各 codebook 摘要（依 [214-068]）
| codebookType | Rel | port 數 | 最大 rank | RI restriction（bit） |
|---|---|---|---|---|
| typeI-SinglePanel（2 port） | 15 | 2 | 2 | 含於 6-bit CBSR |
| typeI-SinglePanel | 15 | 4–32 | 8 | 8 |
| typeI-SinglePanel-r19 | 19 | 48/64/128 | 8 | 8 |
| typeI-MultiPanel | 15 | 8/16/32 | 4 | 4 |
| typeI-MultiPanel-r19 | 19 | 48/64/128 | 4 | 4 |
| typeII | 15 | 4–32 | 2 | 2 |
| typeII-PortSelection | 15 | 4–32 | 2 | 2 |
| typeII-r16 | 16 | 4–32 | 4 | 4 |
| typeII-PortSelection-r16 | 16 | 4–32 | 4 | 4 |
| typeII-PortSelection-r17 | 17 | 4–32 | 4 | 4 |
| typeII-CJT-r18／-CJT-PortSelection-r18 | 18 | 每 resource 4–32，N_TRP ≤ 4 | 4 | 4 |
| typeII-Doppler-r18／-DopplerPortSelection-r18 | 18 | 4–32 | 4 | 4 |
| eTypeII-r19／typeII-FePortSelection-r19（valueOfN-r19）／typeII-Doppler-r19 | 19 | 48/64/128（FePS 為 48/64） | 4 | 4 |

### 7.h Schema 欄位（mimo_capability 與 codebook config）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| max_mimo_layers_pdsch_cell | int | 1..8 | — | — | [3GPP-N] | 331-013 |
| max_mimo_layers_pdsch_bwp | int | 1..8 | — | 同 cell 值 | [3GPP-N] | 331-012 |
| max_mimo_layers_pusch | int | 1..4（v1810 為 5..8） | — | — | [3GPP-N] | 331-017 |
| pusch.max_rank | int | 1..4（v1810 為 5..8） | — | — | [3GPP-N] | 331-016 |
| pusch.tx_config | enum | codebook, nonCodebook | — | 缺省時為單 port | [3GPP-N] | 331-016, 214-080 |
| pusch.codebook_subset | enum | fullyAndPartialAndNonCoherent, partialAndNonCoherent, nonCoherent | — | — | [3GPP-N] | 331-016 |
| max_codewords_per_dci | enum | n1, n2 | — | n1 | [3GPP-N] | 331-012 |
| prg_size | enum | 2, 4, wideband | PRB | — | [3GPP-N] | 214-022 |
| ue_cap.max_layers_dl | enum | 2, 4, 8 | — | — | [3GPP-N] | 331-023, 306-018 |
| ue_cap.max_layers_ul_cb / noncb | int | — | — | — | [3GPP-N] | 306-019, 306-020 |
| ue_cap.max_configured_tci_per_cc | enum | 4, 8, 16, 32, 64, 128 | — | — | [3GPP-N] | 331-021, 306-004 |
| ue_cap.max_active_tci_per_bwp | enum | 1, 2, 4, 8 | — | — | [3GPP-N] | 331-021 |
| ue_cap.max_number_rx_beam | int | 2..8 | — | — | [3GPP-N] | 331-021, 306-001 |
| ue_cap.max_tx_ports_per_resource | enum | 2, 4, 8, 12, 16, 24, 32 | — | — | [3GPP-N] | 331-022, 306-015 |
| ue_cap.pusch_trans_coherence | enum | nonCoherent, partialCoherent, fullCoherent | — | — | [3GPP-N] | 331-021, 306-024 |
| ue_cap.supported_srs_tx_port_switch | enum | xTyR 組合 | — | — | [3GPP-N] | 214-084 |
| codebook.type | enum | 7.g 表中的 codebookType | — | typeI-SinglePanel | [3GPP-N] | 214-068, 331-009 |
| codebook.n1, n2, ng | int | 7.f 表 | — | — | [3GPP-N] | 214-052, 214-056 |
| codebook.o1, o2 | int | 4 或 1 | — | — | [3GPP-N] | 214-052 |
| codebook.mode | enum | 1, 2（r19 為 modeA、modeB） | — | 1 | [3GPP-N] | 331-009 |
| codebook.cbsr_bits | bitstring | 長度依 7.f 表 | — | 全為 1 | [3GPP-N] | 331-009 |
| codebook.ri_restriction | bitstring | 8、4 或 2 bit | — | 全為 1 | [3GPP-N] | 214-054, 331-009 |
| codebook.number_of_beams_L | enum | 2, 3, 4 | — | — | [3GPP-N] | 214-058 |
| codebook.phase_alphabet_size | enum | 4, 8 | — | — | [3GPP-N] | 331-009 |
| codebook.subband_amplitude | bool | — | — | — | [3GPP-N] | 331-009 |
| codebook.port_selection_sampling_size_d | enum | 1..4 | — | — | [3GPP-N] | 214-059 |
| codebook.param_combination | int | r16：1..8；r17：1..8；r19：1..8／1..7；Doppler：1..9 | — | — | [3GPP-N] | 331-009 |

---
## 8. L6 — Runtime／Procedure State

### 8.a 規則
| ID | 規則 | 數值／範圍 | 標記 | 出處 | 文件位置 |
|---|---|---|---|---|---|
| R-L6-01 | 初始預設 beam：尚未套用 indicated TCI（unified）或尚未收到 MAC CE（legacy）前，PDSCH/PDCCH DM-RS 與初始接入時選定的 SSB 為 QCL（typeA，適用時含 typeD） | — | [3GPP-N] | 214-006, 214-009 | 38.214 §5.1.5, p.51, p.54 |
| R-L6-02 | UE 以 SSB 所關聯的 PRACH occasion 與 preamble 隱式告知 gNB 所選的 beam；映射順序依序為 preamble → 頻率 → 時間 → slot | ssb-perRACH-Occasion 為 N，每個 SSB 的 preamble 數為 R | [3GPP-N] | 213-004 | 38.213 §8.1, p.64–65 |
| R-L6-03 | legacy MAC CE 的生效時間：slot n + 3·N_slot^{subframe,μ} + (2^μ/2^{μ_Kmac})·k_mac 之後的第一個 slot | 地面網路 k_mac = 0 時約為 ACK 後 3 ms | [3GPP-N] | 214-008 | §5.1.5, p.53 |
| R-L6-04 | unified TCI 生效時間：送出正向 ACK 後至少 beamAppTime 個 symbol 的第一個 slot，以套用 CC 中最小 SCS 的 active BWP 計算 | beamAppTime-r17 ∈ {1,2,4,7,14,28,42,56,70,84,98,112,224,336} symbol | [3GPP-N] | 214-007, S331-006, 133-033 | §5.1.5, p.52；38.331 p.1053 |
| R-L6-05 | 純 beam 指示的 DCI（不含 DL assignment）以 CS-RNTI 加擾，並以特定欄位值辨識 | — | [3GPP-N] | 214-005 | p.51 |
| R-L6-06 | 排程偏移 ≥ timeDurationForQCL 時才依 DCI 的 TCI 接收；偏移較小時，使用最近監聽 slot 中 controlResourceSetId 最小之 CORESET 的 QCL；typeD 衝突時 PDCCH 優先 | timeDurationForQCL 為 UE 能力 | [3GPP-N] | 214-010, 214-011 | p.54–55 |
| R-L6-07 | TCI known 條件：切換命令在 beam 報告 RS 最後一次傳送後 1280 ms 內收到；切換前至少送出 1 次 L1-RSRP 報告；切換期間可偵測；SNR ≥ −3 dB | — | [3GPP-N] | 133-030 | TS 38.133 §8.10.2, p.868–869 |
| R-L6-08 | MAC CE TCI 切換延遲：known 時為 n + T_HARQ + 3·N_slot + TO_k·(T_first-SSB + T_SSB-proc)；unknown 時另加 T_L1-RSRP（FR2 的 Rx beam 細化時間；FR1 為 0）；T_SSB-proc = 2 ms | — | [3GPP-N] | 133-031, 133-033 | §8.10.3, §8.15.3 |
| R-L6-09 | DCI 觸發的 TCI 切換（known）於 n + timeDurationForQCL 後生效 | — | [3GPP-N] | 133-032 | §8.10.4 |
| R-L6-10 | SP CSI 報告於 PUCCH 由 MAC CE 6.1.3.16 啟用（n + 3·N_slot 後生效）；於 PUSCH 由 SP-CSI-RNTI 加擾的 DCI 啟用；SP CSI-RS 由 MAC CE 6.1.3.12 啟用；AP trigger state 最多映射 63 個 | — | [3GPP-N] | 214-035, 321-009 | 38.214 §5.2.1.5.2；38.321 §6.1.3.12/13/16 |
| R-L6-11 | L1-RSRP 量測週期（SSB）：FR1 non-DRX 為 max(T_Report, ⌈M·P⌉·T_SSB)；FR2 另乘 N（N=8，支援 fastBeamSweepingMultiRx 時可為 2/4/6）；M 為 1（有時間限制）或 3 | — | [3GPP-N] | 133-020 | TS 38.133 §9.5.4.1 |
| R-L6-12 | L1-RSRP 量測週期（CSI-RS）：repetition = off 時 N = 1；repetition = on 時 N = ⌈maxNumberRxBeam / N_res_per_set⌉；aperiodic 時 M = 1 | — | [3GPP-N] | 133-021 | §9.5.4.2 |
| R-L6-13 | RSRP 回報對映：L1 有效值為 RSRP_16（< −140 dBm）至 RSRP_113（≥ −44 dBm）；L3 範圍為 −156～−31 dBm；RSRP_127 只用於門檻設定 | uint7 | [3GPP-N] | 133-022, 133-023 | §10.1.6, Table 10.1.6.1-1 |
| R-L6-14 | 差分 RSRP：DIFFRSRP_k 表示 −2k ≥ ΔRSRP > −2k−2（k = 0..14）；k = 15 表示 ≤ −30 dB | uint4 | [3GPP-N] | 133-024 | Table 10.1.6.1-2 |
| R-L6-15 | SINR 對映：SINR_k 表示 −23.5+0.5k ≤ SINR < −23+0.5k；差分 SINR 步進 1 dB，範圍至 −15 dB | uint7／uint4 | [3GPP-N] | 133-025, 133-026 | §10.1.16.1 |
| R-L6-16 | RLM：Qout 對應 BLER_out，Qin 對應 BLER_in；Configuration #0 為 BLER_out 10%、BLER_in 2%；門檻的 dB 值由 UE 實作決定 | — | [3GPP-N] | 133-001, 133-002 | §8.1.1, Table 8.1.1-1, p.582 |
| R-L6-17 | RLM-RS 最大數量 N_RLM：Lmax = 4 時為 2，Lmax = 8 時為 4，Lmax = 64 時為 8 | — | [3GPP-N] | 133-003 | Table 8.1.1-2, p.583 |
| R-L6-18 | 假想 PDCCH 參數：RLM Qout 為 AL8、+4 dB；Qin 為 AL4、0 dB；BFD 為 AL8、0 dB；皆為 DCI 1-0、2 個符號、24 PRB | — | [3GPP-N] | 133-004, 133-012 | Tables 8.1.2.1-1/-2, 8.5.2.1-1 |
| R-L6-19 | BFD 集合：q0 為目前監測的 beam（BFD-RS），q1 為候選 beam；Rel-17 起可有兩組（per TRP）；q0 未設定時，隱式取自 CORESET TCI 中的 RS（最多 2 個，雙 RS 時取 typeD） | maxNrofFailureDetectionResources = 10；maxNrofCandidateBeams = 16（r16 為 64） | [3GPP-N] | 213-010, 213-011, S331-005, 331-040 | 38.213 §6, p.19 |
| R-L6-20 | q0 必須是單 port RS；q1 為 1 或 2 port 的 CSI-RS，密度為每 RB 1 或 3 個 RE；SCell 的 q0 只能是 periodic CSI-RS，且每個 CC 最多評估 2 個 | — | [3GPP-N] | 213-011, 133-010 | 38.213 §6；38.133 §8.5.1 |
| R-L6-21 | Qout_LR 對應假想 PDCCH BLER = 10%（固定值）；Qin_LR = rsrp-ThresholdSSB（L1-RSRP），CSI-RS 需先以 powerControlOffsetSS 縮放 | — | [3GPP-N] | 213-012, 133-011 | 38.213 §6；38.133 §8.5.1, p.770–771 |
| R-L6-22 | 僅當 q0 中「所有」RS 都差於 Qout,LR 時，PHY 才發出 BFI；非 DRX 時的週期 = max(q0 中最短 RS 週期, 2 ms) | — | [3GPP-N] | 213-013 | 38.213 §6, p.20 |
| R-L6-23 | BFD 評估週期（SSB）：FR1 non-DRX 為 max(50, ⌈5·P⌉·T_SSB) ms；FR2 另乘 N（FR2-1 為 8，FR2-2 為 12） | — | [3GPP-N] | 133-013 | 38.133 §8.5.2.2 |
| R-L6-24 | MAC BFD：每收到一次 BFI 就重新啟動 beamFailureDetectionTimer 並將 BFI_COUNTER 加 1；BFI_COUNTER ≥ beamFailureInstanceMaxCount 時，SCell 觸發 BFR，SpCell 發起 RA；timer 到期或相關參數重新設定時，BFI_COUNTER 歸零 | maxCount ∈ {1,2,3,4,5,6,8,10}；timer ∈ {1,2,3,4,5,6,8,10}（單位為 Qout,LR 回報週期）；recoveryTimer ∈ {10,20,40,60,80,100,150,200} ms | [3GPP-N] | 321-001, 321-002, S331-009, 331-019, 331-020 | 38.321 §5.17, p.141–143 |
| R-L6-25 | BFR：PHY 依要求回報 q1 中 L1-RSRP ≥ Qin,LR 的候選；SpCell 以 q_new 對應的 PRACH 發起 RA，並自 slot n + 4 + 2^μ·k_mac 起在 recoverySearchSpaceId 監聽 | — | [3GPP-N] | 213-014, 213-015 | 38.213 §6, p.20 |
| R-L6-26 | 收到回應 PDCCH 後 28 個 symbol 起：CORESET 0 使用 q_new 的 QCL；PUCCH 使用最後一次 PRACH 的空間濾波；unified TCI 下所有通道皆跟隨 q_new | 28 symbols | [3GPP-N] | 213-016, 213-017 | p.20–21 |
| R-L6-27 | BFR 完成條件：SpCell 的 RA 成功時，將 BFI_COUNTER 歸零並停止 recovery timer；SCell 在收到對應 HARQ process 的 UL grant 時完成 | — | [3GPP-N] | 321-003 | 38.321 §5.17, p.144 |
| R-L6-28 | BFR MAC CE：長度可變；ServCellIndex 小於 8 時 bitmap 為 1 octet，否則為 4 octet；每個 MAC PDU 最多一個 BFR MAC CE | — | [3GPP-N] | 321-008 | §6.1.3.23, p.267 |
| R-L6-29 | 每個 serving cell 最多同時維持 4 個 pathloss 估計；PL = referenceSignalPower − 經高層濾波的 RSRP；未設定 pathloss RS 時，以取得 MIB 的 SSB 估計 | — | [3GPP-N] | 213-020, 213-021 | 38.213 §7, p.25, p.33–36 |
| R-L6-30 | beam level mobility 不需 RRC 參與（由 L1/L2 處理）；Rel-19 支援 UE-initiated beam report 的 Mode A 與 Mode B | — | [3GPP-N] | 300-003, 300-004 | 38.300 §9.2.3.1, p.97 |
| R-L6-31 | TRX_CONTROL（ST4 cmdType 3）與 TRX_CONTROL_BIDIR（cmdType 5）以 antenna mask 控制：1 表示啟用，0 表示停用；LSB 對應 k = 0；新 mask 取代舊 mask；只能使用 ARRAY-COMMAND；mask 必須屬於 O-RU 回報的 valid mask 列表 | — | [ORAN-N] | CUS-081 | CUS §16.2 |
| R-L6-32 | 被停用的 element 仍須傳送權重，其值設為 0；PDBF 使用預存的含零權重向量 | — | [ORAN-N] | CUS-081 | CUS §16.2 |
| R-L6-33 | antMask 長度為 2..2048 bytes（對應 2..16384 個 element）；log2MaskBits 的有效值為 1..14（mask 最少 16 bit）；sleepMode 為 2 bit（0..3）；全零 mask 合法，但不等同 ASM | — | [ORAN-N] | CUS-082 | CUS §7.5.3.51/52/54 |
| R-L6-34 | 每個 tx/rx-array 各有一組 sleep mode（0..3）與 wake-up duration（依 L < M < N 遞增）；defined-duration sleep 的時長須 ≥ wake-up duration；symbolMask 非全 0 或全 1 時只能使用 sleep mode 0 | — | [ORAN-N] | CUS-080, MP-121 | CUS §16.1；MC L599 |
| R-L6-35 | M-plane TRX control：antenna-bitmask 的位元數 = 陣列 element 數，以 base64 編碼；設定前預設為全 1；必須以最大的重疊陣列為對象；回報的 mask 清單必須包含全 1；未回報清單表示任何 mask 都支援 | — | [ORAN-N] | MP-121, MP-122 | MP §20.3.1.2, §20.3.2.2/3 |
| R-L6-36 | C-plane 與 M-plane 的 TRX control 互斥：送出其中一種命令前，須確認另一種的 mask 為全 1 | — | [ORAN-N] | MP-122 | MP §20.3.2.5 |
| R-L6-37 | 資料層控制：只能對 eAxC 目前皆未被 O-DU 使用的 energy-sharing-group 觸發 | — | [ORAN-N] | MP-124 | MP §20.3.3.2 |
| R-L6-38 | deep hibernate：有 array-carrier 處於 active 時，必須拒絕 deep-hibernate RPC | — | [ORAN-N] | MP-126 | MP §20.5 |
| R-L6-39 | 最大功率控制：若新值使功率降低幅度增加，O-DU 須先降低功率（例如減少排程的 PRB）再下發新設定 | — | [ORAN-N] | MP-125 | MP §20.6.3 |
| R-L6-40 | WG1 NES：可關閉部分 RF channel（例如 64 個中關閉 32 個）；若所有 SSB/PRACH beam 都被 mask，屬例外情況 | — | [ORAN-N] | WG1-008 | WG1 §4.21.3.2 |
| R-L6-41 | ALD device type 只有三種（1 octet code）：0x01 Single-Antenna RET、0x11 Multi-Antenna RET、0x02 TMA；device type 決定適用的程序集（單天線 RETAP／多天線 RETAP／TMAAP）。primary device = RAN node，secondary device = RET／TMA | — | [3GPP-N] | 37462-002, 37466-001, 37466-007 | TS 37.462 V19.0.0 §4.7 Table 4.7.1, p.8–9 |
| R-L6-42 | RET tilt 程序：單天線 `SetTilt 0x33`／`GetTilt 0x34`，多天線 `AntennaSetTilt 0x81`／`AntennaGetTilt 0x82`；四者皆為 Class 1 且 mandatory；多天線程序多帶 1 octet antenna number（1 起算），天線不存在回 `FormatError` | antenna_number 1..255 | [3GPP-N] | 37466-005, 37466-011, 37466-012, 37466-013, 37466-019, 37466-020, 37466-021 | TS 37.466 §6.3 p.13；§6.6.3/6.6.4 p.25–26；§6.7.2/6.7.3 p.29–30 |
| R-L6-43 | 時限：`SetTilt`／`AntennaSetTilt` 回應 < 2 分鐘；`Calibrate` 回應 < 4 分鐘 | <2 min／<4 min | [3GPP-N] | 37466-012, 37466-015, 37466-019 | TS 37.466 §6.6.3 p.25；§6.6.1 p.23–24 |
| R-L6-44 | tilt 移動過程中實際 tilt value 不得超出 `[current, requested]` 區間 5 個單位（= 0.5°）——致動器過衝上限 | 5 單位 = 0.5° | [3GPP-N] | 37466-012, 37466-019 | TS 37.466 §6.6.3 p.25–26 |
| R-L6-45 | `SelfTest 0x0A` 期間致動器移動不得超過總 tilt 行程的 ±5%（自當前位置起算），完成後所有參數回復初值；回應 = `OK` + 0..N 個 AlarmCode | ±5% | [3GPP-N] | 37466-018 | TS 37.466 §6.5.6, p.18–19 |
| R-L6-46 | `{SelfTest, Calibrate, SetTilt}` 為 Time-Consuming Procedure（TCP）；TCP 執行中**最多再並行 1 個 EP**，且 `ClearActiveAlarms`／`SendConfigurationData`／其他 TCP 為 disallowed（應回 `Busy`）；`GetTilt`／`Set/GetDeviceData` 為 optional-parallel | 並行上限 1 | [3GPP-N] | 37466-010 | TS 37.466 §6.2.3, Table 6.2.3.1, p.11–12 |
| R-L6-47 | 前置條件旗標：未 `Calibrate` → tilt 程序回 `NotCalibrated`；未 `SendConfigurationData` → 回 `NotConfigured`；tilt 超出 `[min,max]` → 回 `OutOfRange`。configuration data（drive 位置 ↔ beam tilt 對映）payload 為 **vendor specific**，長度 ≤ MaxDataReceiveLength | — | [3GPP-N] | 37466-012, 37466-013, 37466-015, 37466-016 | TS 37.466 §6.6.1–6.6.4, p.23–26 |
| R-L6-48 | 裝置狀態機：`OperatingMode`（application software 存在）／`DownloadMode`（缺 software，僅支援下載）；不支援下載功能時只有 OperatingMode。alarm 通知需先 `AlarmSubscribe`（reset 後失效）；`AlarmIndication 0x07` 為 Class 2，payload = N 組 (alarm_code, state_flag)，`state_flag 0 = cleared / 1 = raised`；任何 reset 清除所有 alarm state。AlarmCode ⊂ ReturnCode | — | [3GPP-N] | 37466-008, 37466-009, 37466-017 | TS 37.466 §6.1 p.10–11；§6.2.1 p.11；§6.6.5 p.26–27 |
| R-L6-49 | **RET 機電 tilt（TS 37.466，單位 0.1°、經 Iuant/AISG 透傳、由 device data 0x06/0x07 限界）與 O-RAN 數位 beam tilt offset（[MP-049]，int16 −90..90 deg、granularity uint8 0..30 deg、經 M-plane RPC 設定）是兩套獨立參數**，單位／解析度／值域／控制路徑皆不同，schema 必須分開存放，不可互相換算取代（MP §15.4.4 亦明文區分） | — | [3GPP-N] + [ORAN-N] | 37466-003, 37466-030, MP-049, MP-141 | TS 37.466 §3.1 p.8；MP §15.4.4 |
| R-L6-50 | O-RAN 架構下 RET 控制經 `rpc ald-communication` 將 RETAP 訊息以 binary 透傳（`ald-req-msg ≤ 1200 octets`，遠大於 HDLC N ≥ 78，故一個 RPC 可承載完整 EP）；O-RU 不解讀內容 ⇒ tilt 的語意、單位、值域與時限全部來自 TS 37.466 | ≤1200 octets | [3GPP-N] + [ORAN-N] | 37466-030, 37462-001, MP-140, MP-141 | TS 37.466 §5 p.9；MP §14.4.1–14.4.3 |
| R-L6-51 | Iuant L1 至少支援 RS485 或 Modem 兩種選項之一；預設速率 9.6 kbps，選配 38.4 kbps（兩者）與 115.2 kbps（**僅 RS485**）；**Modem option 只適用於 UTRA／E-UTRA BS 與 NR BS type 1-C**，1-H／1-O 需用 RS485 或 O-RU ALD port。量測時內建 Iuant BS modem 預設關閉，modem ON 時 spurious 只量 > 20 MHz | 9600/38400/115200 bps ±3% | [3GPP-N] | 37461-001, 1411-012, MP-142 | TS 37.461 V19.0.0 §4.1, p.6；TS 38.141-1 §4.5.3, p.47 |

### 8.b Schema 欄位（RuntimeState）
| 欄位 | 型別 | 範圍／列舉 | 單位 | 預設 | 標記 | 出處 |
|---|---|---|---|---|---|---|
| active_antenna_mask[array] | bitstring | 長度 = K；1 表示啟用 | — | 全 1 | [ORAN-N] | CUS-081, MP-122 |
| sleep_mode[array] | int | 0..3 | — | — | [ORAN-N] | CUS-082 |
| carrier_state[carrier] | enum | INACTIVE, SLEEP, ACTIVE | — | INACTIVE | [ORAN-N] | MP-085 |
| active_beams[] {eaxc_id, beam_id, symbol, prb_range, weights_ref} | list | beam_id 0..32767 | — | — | [ORAN-N] | CUS-032, CUS-033 |
| ssb_beam_state {selected_ssb_index, ss_rsrp} | object | — | dBm | — | [3GPP-N] | 213-002, 215-001 |
| csi_rs_resources[] {id, nrof_ports, mapping_row, cdm_type, density, first_symbol, freq_alloc, power_control_offset, power_control_offset_ss, periodicity, qcl_tci_id} | list | 見 R-L4-18～22、R-L5-47 | dB | — | [3GPP-N] | 331-001, 331-002 |
| csi_rs_resource_sets[] {id, resources[], repetition, trs_info} | list | 每 set ≤ 64；repetition ∈ {on, off} | — | 缺省視為 off | [3GPP-N] | 331-005 |
| csi_report_configs[] {id, report_config_type, report_quantity, codebook, group_based, nrof_reported_rs} | list | — | — | — | [3GPP-N] | 331-008 |
| tci_states[] {id, qcl_type1 {rs, type}, qcl_type2} | list | ≤ 128 | — | — | [3GPP-N] | 331-010 |
| active_tci_codepoints[] | list | ≤ 8 codepoint；unified 時 ≤ 16 個 state | — | — | [3GPP-N] | 321-005, 321-006 |
| indicated_tci {dl, ul, app_slot} | object | — | slot | — | [3GPP-N] | 214-007 |
| pdsch_layers | int | 1..8 | — | 1 | [3GPP-N] | 214-020 |
| pdsch_dmrs_ports[] | int list | 1000..1023 | — | [1000] | [3GPP-N] | 212-001, 214-023 |
| num_codewords | int | 1..2（由 layers 推得） | — | 1 | [3GPP-N] | 211-015 |
| pusch_layers / tpmi / sri | int | — | — | — | [3GPP-N] | 214-081 |
| reports[] {time, cri/ssbri, l1_rsrp_code, diff_code, ri, pmi, cqi, li} | list | L1-RSRP 碼 16..113；差分碼 0..15 | — | — | [3GPP-N] | 133-023, 133-024, 212-021 |
| bfd {q0[], q1[], bfi_counter, bfd_timer, recovery_timer, q_new, state} | object | state ∈ {normal, bfd, recovering} | — | bfi_counter = 0 | [3GPP-N]（state 列舉為 [SIM]） | 213-010, 321-002 |
| pathloss_rs[] | list | ≤ 4 | — | — | [3GPP-N] | 213-020 |
| beam_tilt_state {elevation, azimuth} | int16 | −90..90（**數位** beam tilt offset，與 RET 機電 tilt 不同，見 R-L6-49） | deg | 0 | [ORAN-N] | MP-049 |
| ald[].device_type | enum | 0x01 single_antenna_ret, 0x11 multi_antenna_ret, 0x02 tma | — | — | [3GPP-N] | 37462-002 |
| ald[].app_part | enum | RETAP, TMAAP | — | — | [3GPP-N] | 37466-001 |
| ald[].device_state | enum | OperatingMode, DownloadMode | — | OperatingMode | [3GPP-N] | 37466-008 |
| ald[].num_antennas | uint8 | 1..255（多天線 RET 由 `AntennaGetNumberOfAntennas 0x88` 取得） | — | 1 | [3GPP-N] | 37466-021 |
| ald[].antenna[].antenna_number | uint8 | 1 起算 | — | — | [3GPP-N] | 37466-005 |
| ald[].antenna[].tilt_value | int16 | 單位 0.1°，值域見 R-L0-17 | 0.1 deg | — | [3GPP-N] | 37466-003, 37466-013 |
| ald[].calibrated | bool | false ⇒ tilt 程序回 `NotCalibrated` | — | false | [3GPP-N] | 37466-015 |
| ald[].configured | bool | false ⇒ 回 `NotConfigured` | — | false | [3GPP-N] | 37466-016 |
| ald[].busy | bool | TCP 執行中；並行 EP 上限 1 | — | false | [3GPP-N] | 37466-010 |
| ald[].active_alarms[] | list\<uint8\> | AlarmCode ⊂ ReturnCode（值表在 37.466 Annex A，未摘錄） | — | [] | [3GPP-N] | 37466-009, 37466-017 |
| ald[].alarm_subscribed | bool | reset 後歸 false | — | false | [3GPP-N] | 37466-017 |
| ald[].layer1_option | enum | RS485, Modem（Modem 僅 bs_type 1-C） | — | — | [3GPP-N] | 37461-001 |
| ald[].data_rate_bps | enum | 9600, 38400, 115200（115200 僅 RS485），±3% | bps | 9600 | [3GPP-N] | 37461-001 |
| ald[].hdlc_max_frame_octets | uint | ≥78（4..N） | octets | 78 | [3GPP-N] | 37462-001 |
| ald[].hdlc_window_size | uint | 1..7（強制支援 1） | — | 1 | [3GPP-N] | 37462-001 |
| ald[].oran_ald_port_id | uint8 | 0 或 1（兩個連接器時） | — | — | [ORAN-N] | MP-142 |
| ald[].tma_subunit[] {max_gain_db, min_gain_db, gain_resolution_db, supports_bypass} | list | 增益線上為 uint8，單位 dB/4（0.25 dB 步進）；supports_bypass = Table B.4 bit 0 | dB | — | [3GPP-N] | 37466-023 |

---

## 9. 跨層一致性規則（validator 可直接實作）

| ID | 規則（條件式） | 標記 | 出處 |
|---|---|---|---|
| V-01 | codebook 為 typeI-SinglePanel 且 P > 2 ⇒ nrofPorts == 2·n1·n2，且 (n1,n2,o1,o2) ∈ Table 5.2.2.2.1-2 | [3GPP-N] | 214-052 |
| V-02 | codebook 為 typeI-MultiPanel ⇒ nrofPorts == 2·ng·n1·n2 ∈ {8,16,32}；ng == 4 ⇒ codebookMode == 1 | [3GPP-N] | 214-056 |
| V-03 | codebook 為 typeI-SinglePanel-r19 或 typeI-MultiPanel-r19 ⇒ P_total == 2·(ng·)n1·n2 ∈ {48,64,128}；o1 = o2 = 4；MP-r19 時 ng == K | [3GPP-N] | 214-055, 214-057 |
| V-04 | 單一 CSI-RS resource：nrofPorts ∈ {1,2,4,8,12,16,24,32}（≤ 32） | [3GPP-N] | 211-031, 331-002 |
| V-05 | N_tot ∈ {48,64,128} ⇒ (N_tot, K, N) ∈ {(48,2,24),(48,3,16),(64,4,16),(64,2,32),(128,4,32)}，且 K 個 resource 的 qcl-info／powerControlOffset／powerControlOffsetSS 相同 | [3GPP-N] | 211-031, 214-071 |
| V-06 | CSI-RS mapping：(nrofPorts, density, cdm-Type) 必須能對應到 Table 7.4.1.5.3-1 的某一列；density 須符合 R-L4-22；frequencyDomainAllocation 的位元長度須與 row 相符 | [3GPP-N] | 211-034, 331-002 |
| V-07 | 以 CDM group 數 × L 計算的 port 數 == nrofPorts | [DERIVED] | 211-034 |
| V-08 | cbsr_bits 的長度 == 7.f 表中 (codebook 版本, n1, n2) 對應的值；Type I SP 時 == N1·O1·N2·O2 | [3GPP-N] | 214-054, 331-009 |
| V-09 | ri_restriction 的長度：Type I SP 為 8；Type I MP 為 4；typeII（r15）與 typeII-PS 為 2；r16/r17/r18/r19 Type II 為 4 | [3GPP-N] | 331-009 |
| V-10 | 回報的 rank ≤ codebook 的最大 rank（7.g 表），且 ri_restriction 中對應的 bit == 1 | [3GPP-N] | 214-054, 214-068 |
| V-11 | pdsch_layers ≤ min(maxMIMO-Layers（BWP，若有），maxMIMO-Layers（cell），UE maxNumberMIMO-LayersPDSCH，8) | [3GPP-N] | 331-012, 331-013, 306-018, 214-020 |
| V-12 | pdsch_layers ≤ codebook 最大 rank（有 PMI 回報時），且 ≤ O-RU 的 number-of-spatial-streams-dl | [DERIVED] | 214-068, MP-070 |
| V-13 | pdsch_layers ≤ nrofPorts（CSI-RS）與 UE Rx 數；層數不得超過 port 數 | [DERIVED] | 211-016, 214-052 |
| V-14 | num_codewords == (pdsch_layers ≤ 4 ? 1 : 2)；2 CW ⇒ maxNrofCodeWordsScheduledByDCI == n2 | [3GPP-N] | 211-015, 300-001, 331-012 |
| V-15 | len(pdsch_dmrs_ports) == pdsch_layers；各 port 須落在 (type, typeEnh, maxLength) 對應的支援集合內（Table 7.4.1.1.2-5） | [3GPP-N] | 211-023, 212-001 |
| V-16 | 每 UE 的 DM-RS port 數：SU-MIMO ≤ 8，MU-MIMO ≤ 4 | [3GPP-N] | 300-001 |
| V-17 | pusch_layers ≤ min(maxMIMO-Layers（1..4 或 v1810 的 5..8）, maxRank, UE max layers CB/nonCB)；使用 transform precoding ⇒ pusch_layers == 1 | [3GPP-N] | 331-016, 331-017, 300-002 |
| V-18 | nonCodebook ⇒ 每個 SRS resource 的 nrofSRS-Ports == 1 | [3GPP-N] | 214-082 |
| V-19 | 3 port UL codebook ⇒ codebookSubset == nonCoherent | [3GPP-N] | 214-081 |
| V-20 | beamId == 0 ⇒ 不做 BF（不施加權重）；O-RU 不支援 BF ⇒ 所有 beamId 皆為 0 | [ORAN-N] | CUS-033, CUS-011 |
| V-21 | 1 ≤ beamId ≤ 32767；beamId ∈ [initial-beam-id, initial-beam-id + max-number-of-beam-ids − 1]（依所屬 domain） | [ORAN-N]／[DERIVED] | CUS-033, MP-044 |
| V-22 | 每個 symbol／slot 使用的相異 beamId 數 ≤ endpoint-beam-capacity 的對應上限；上限為 0 或缺少 ⇒ 不得使用 BF | [ORAN-N] | MP-062, CUS-091 |
| V-23 | WDBF：同一 slot 中，同一 beamId 的相異權重集合數 ≤ 1 | [ORAN-N] | CUS-014 |
| V-24 | K == M·N·P·Q；len(weights) == K（beamspace 壓縮例外）；len(antenna_mask) == K（ST4 時補齊至 2^log2MaskBits，多出的位元為 0） | [ORAN-N] | CUS-071, CUS-041, CUS-082 |
| V-25 | hybrid 時 K == K′·p′，且 fd_weights_mapping 覆蓋所有 element 恰好一次 | [ORAN-N] | CUS-017, CUS-071 |
| V-26 | 對每個 k，0 ≤ k < K，且 k == q·P·M·N + p·M·N + m·N + n | [ORAN-N] | CUS-072 |
| V-27 | popcount(o_du_port_bitmask \| band_sector_bitmask \| ccid_bitmask \| ru_port_bitmask) ≤ 16，四個 bitmask 兩兩互斥且各自為連續位元（v21 MP 允許不填滿 16 bit，SMO 以 padding 補足） | [ORAN-N] | CUS-003, MP-050, ORAN-030 |
| V-28 | 同方向的 eaxc_id 在同一 O-RU 內唯一；同方向的一個 eaxc_id 只屬於一個 array | [ORAN-N] | MP-050, CUS-005 |
| V-29 | ru_category == CAT_A ⇒ 每個 array 的 P == 1 | [ORAN-N] | CUS-005 |
| V-30 | 1 ≤ len(polarisations) ≤ 2，且 len == P | [ORAN-N] | MP-010 |
| V-31 | spacing（m）> 0；d_λ = spacing · f_c / c | [DERIVED] | MP-010, 901-014 |
| V-32 | bs_type == 1-O ⇒ num_tx_units ≥ 8 且 num_rx_units ≥ 8；bs_type ∈ {1-O, 2-O} ⇒ 不存在 TAB | [3GPP-N] | 104-032 |
| V-33 | n_txu_counted == min(n_txu_active, 8·n_cells) | [3GPP-N] | 104-046 |
| V-34 | 改變 beam 時，TRP 保持不變（前提為 peak direction 位於 OTA peak directions set 內） | [3GPP-N] | 104-043 |
| V-35 | 每個 declared beam 須有 5 個 direction pair（reference + 4 個 max steering），且 peak set ⊆ coverage range | [3GPP-N] | 1412-010, 104-014 |
| V-36 | TCI-State：qcl_type2 存在 ⇒ qcl_type2.type ≠ qcl_type1.type；typeA/B 的 RS 不得位於其他 cell | [3GPP-N] | 214-002, 331-010 |
| V-37 | len(tci_states) ≤ min(128, UE maxNumberConfiguredTCI-StatesPerCC)；active codepoint ≤ 8；unified 的 active state ≤ 16 | [3GPP-N] | 214-002, 214-003, 321-005, 321-006 |
| V-38 | repetition == on ⇒ 連結的 reportQuantity ∈ {cri-RSRP, cri-SINR, 其 -Index 變形, none}，不回報 CRI，且 set 內所有 resource 的 nrofPorts 相同且 ∈ {1,2} | [3GPP-N] | 214-036, 214-037, 214-038 |
| V-39 | groupBasedBeamReporting == disabled ⇒ 回報數 == nrofReportedRS（缺省為 1）≤ UE N_max；enabled ⇒ 回報數 == 2 | [3GPP-N] | 214-040, 331-008 |
| V-40 | L1-RSRP 報告：第一筆為 7-bit 絕對值，其餘為 4-bit 差分；差分值 ≤ 0 | [3GPP-N] | 214-042, 133-024 |
| V-41 | q0：每個 RS 皆為單 port，且（隱式時）數量 ≤ 2；q1 的 CSI-RS 為 1 或 2 port 且 density ∈ {1,3} | [3GPP-N] | 213-011 |
| V-42 | 使用 SSB 作為 beam 時：ssb_index < Lmax，且對應的 ssb-PositionsInBurst 位元為 1 | [3GPP-N]／[DERIVED] | 213-002, 331-030 |
| V-43 | 每個 serving cell 的 pathloss RS ≤ 4 | [3GPP-N] | 213-020 |
| V-44 | beam_tilt offset ∈ [min_supported, max_supported] ⊆ [−90, 90]，且套用值為 granularity 的整數倍 | [ORAN-N] | MP-049 |
| V-45 | M-plane 與 C-plane 的 TRX control 不得同時使用非全 1 的 mask | [ORAN-N] | MP-122 |
| V-46 | 使用 SE10 或 SE19 時 numPortc ≤ 64；使用 SE16 時天線數 ≤ 64；使用 SE27 時 N ≤ 256 | [ORAN-N] | CUS-090 |
| V-47 | 支援 CAT-A 的 O-DU：precoded stream 支援數 ≥ 8 | [ORAN-N] | CUS-002 |
| V-48 | codebook 的 port 數 ≤ UE maxNumberTxPortsPerResource（聚合時另依 r19 能力） | [3GPP-N] | 306-015, 331-022 |
| V-49 | n_rxu_counted == min(n_rxu_active, 8·n_cells)；n_rxu_countedpercell == n_rxu_counted / n_cells（TX 側為 V-33） | [3GPP-N] | 1411-010 |
| V-50 | bs_type == 1-H ⇒ 每個支援 TX 的 connector 的 tx_min_cell_group_id 恰為 1 個（per band）；每個支援 RX 的 connector 的 rx_min_cell_group_id 恰為 1 個 | [3GPP-N] | 1411-009, 1411-010, 1411-024 |
| V-51 | 每個 demodulation branch 至少被一個 connector 的 demod_branch_ids 引用；len(distinct demod_branch_ids) == n_rxu_active | [3GPP-N]／[DERIVED] | 1411-008, 1411-025 |
| V-52 | bs_type == 1-H ⇒ 每個 connector 的 len(tae_group_ids) ≥ 1（per band） | [3GPP-N] | 1411-024 |
| V-53 | prated_c_sys_dbm == 10·log10(Σ_connectors 10^(rated_carrier_output_power_dbm/10))（單一 carrier 的功率和） | [3GPP-N]／[DERIVED] | 1411-007 |
| V-54 | min_electrical_tilt_deg ≤ electrical_tilt_deg ≤ max_electrical_tilt_deg，且 round(electrical_tilt_deg×10) 為整數且落在 int16 範圍內（否則 SetTilt 回 OutOfRange／FormatError） | [3GPP-N] | 37466-003, 37466-012, 37466-014 |
| V-55 | antenna_bearing_deg ∈ [0, 359.9] 且 round(×10) ∈ 0..3599；installed_mechanical_tilt_deg 亦須為 0.1° 整數倍 | [3GPP-N] | 37466-014 |
| V-56 | ald.busy == true（TCP 執行中）⇒ 同時進行的其他 EP ≤ 1，且不得為 {SetTilt, Calibrate, SelfTest, ClearActiveAlarms, SendConfigurationData, Download*}；違反時回 Busy | [3GPP-N] | 37466-010 |
| V-57 | ald.layer1_option == Modem ⇒ bs_type == 1-C；ald.data_rate_bps == 115200 ⇒ layer1_option == RS485；ald.hdlc_max_frame_octets ≥ 78 | [3GPP-N] | 37461-001, 37462-001 |

---

## 10. Beamforming + MIMO 運作流程

> 「P1／P2／P3」為 TR 38.802 研究階段與業界使用的名稱，不出現在本文件引用的任何規範中；規範中對應的機制是 SSB sweep 與 NZP-CSI-RS 的 repetition off/on [03 前言][214-036]。

| 步驟 | 內容 | 出處 |
|---|---|---|
| 0. 組態 | RRC 設定 SSB（Case、Lmax、ssb-PositionsInBurst）、CSI-RS resource/set、TCI-State、CSI-ReportConfig；O-RU 經 M-plane 回報陣列、beam 能力與 endpoint，O-DU 設定 eAxC 與 array-carrier | 213-001, 213-002, 331-030, 214-031, MP-010, MP-044, MP-050 |
| 1. 初始接入（SSB sweep，慣稱 P1） | gNB 在 half frame 內送出最多 Lmax 個 SSB（port 4000，以不同 index 區分）；UE 量測 SS-RSRP，由 PBCH 取得 SSB index，並在關聯的 PRACH occasion 發送 Msg1；此後預設 QCL 為該 SSB | 211-040, 211-009, 215-001, 213-002, 213-004, 214-006, 214-009 |
| 1'. O-RU 側 | SSB／PRACH 以 ST1/ST3 的 beamId（PDBF）下發，或採用 static PRACH beam-id；beamId 不等於 SSB index | CUS-032, CUS-033, ORAN-063 |
| 2. CSI-RS Tx beam 細化（慣稱 P2） | NZP-CSI-RS set 設 repetition = off，reportQuantity 為 cri-RSRP；periodic CSI-RS 以 qcl-InfoPeriodicCSI-RS 指向 SSB（typeD）；UE 回報 nrofReportedRS 個 CRI + L1-RSRP，或 group-based 2 個；量測週期見 38.133 | 214-037, 214-038, 214-070, 214-040, 214-042, 133-021 |
| 3. UE Rx beam 細化（慣稱 P3） | repetition = on：gNB 使用相同 Tx 濾波，UE 掃描 Rx beam，不回報 CRI；FR2 的量測時間以 maxNumberRxBeam 放大 | 214-036, 214-037, 133-021, 306-001 |
| 4. CSI 報告 | 依 CRI → RI → PMI → CQI → LI 順序計算；選定 codebook（7.g 表）並套用 RI/CBSR 限制；位寬依 38.212；TDD 可改用 antenna-switching SRS 的互易性 | 214-034, 214-039, 214-068, 212-021, 214-084 |
| 5. TCI 指示與 beam 生效 | legacy：MAC CE 啟用 ≤ 8 個，約 3 ms 後生效，再由 DCI 選擇 codepoint（需滿足 timeDurationForQCL）；unified：MAC CE 啟用 ≤ 16 個，DCI 指示後於 ACK 後 ≥ beamAppTime 生效；known/unknown 延遲依 38.133 | 214-004, 214-008, 214-010, 321-005, 321-006, 214-007, 133-030, 133-031 |
| 6. PDSCH precoding 與 layers | 最多 8 層，port 1000–1023；layer 數 = DCI 指示的 DM-RS port 數；1–4 層使用 1 CW、5–8 層使用 2 CW；precoder 對 UE 透明，在同一 PRG 內固定 | 214-020, 212-001, 211-015, 214-022, 300-001 |
| 7. O-DU → O-RU 下發 beam | CAT-A：O-DU 完成 precoding，每個 eAxC 對應一個 precoded stream，O-RU 以 beamId（PDBF）或 SE1/SE11/SE19 權重做 BF；CAT-B：precoding 併入權重（SE1/SE11/SE19），或以 CIBF（ST6 通道 + ST5 排程 + SE8 正則化）由 O-RU 計算；多個 layer 可用 SE10 合併；hybrid 可搭配 ST4 cmd 1 | CUS-001, CUS-004, CUS-041, CUS-047, CUS-048, CUS-056, CUS-021, CUS-046, CUS-019 |
| 7'. UL | codebook PUSCH（SRI + TPMI）或 nonCodebook（SRI）；O-RU 端可採 DMRS-BF（ST5 + SE24），並以 SE32 請求 rank/TPMI 建議 | 214-081, 214-082, CUS-024, CUS-061, CUS-065 |
| 8. BFD | q0 中所有 RS 皆差於 Qout,LR（BLER 10%）時發出 BFI，週期為 max(最短週期, 2 ms)；MAC 計數達上限即觸發 BFR | 213-011, 213-013, 133-011, 321-002 |
| 9. BFR | 回報 q1 中 L1-RSRP ≥ rsrp-ThresholdSSB 的候選；SpCell 發起 RA（CFRA 優先）並自 n+4 起監聽；SCell 送 BFR MAC CE；收到回應 28 symbol 後改用 q_new；完成後回到步驟 5 | 213-014, 213-015, 213-016, 321-003, 321-008, 300-005 |
| 10. 節能（antenna mask） | O-DU 經 ST4 TRX_CONTROL（C-plane）或 M-plane antenna-bitmask 關閉部分 element；被關閉 element 的權重填 0；mask 須屬於 valid 列表；兩種控制方式互斥；可配合 sleep mode 與 ASM | CUS-080, CUS-081, CUS-082, MP-121, MP-122, WG1-008 |
| 11. 覆蓋調整（非即時） | 數位 tilt（beam-tilt offset RPC）、更換權重檔、null steering（需停用再啟用 carrier）；RET 經 AISG 透傳 | MP-049, MP-047, MP-131, MP-141 |

---
## 11. 與 GPT 版本（GPT_search.md = G、spec_v1.md = S）的差異與勘誤（已去重）

| # | GPT 內容 | 正確內容 | 出處 |
|---|---|---|---|
| 1 | S 將 38.104 標為 V19.4.0 | 本地檔案與引用版本為 V19.5.0 | 01-H1 |
| 2 | G/S 把 TRXUA→TAB→RDN→AA 當作所有 BS 的架構 | 此架構僅適用於 1-H；1-O/2-O 沒有 TAB；1-C 只有 antenna connector | 104-030..032 |
| 3 | G/S 未提 1-O 的最少單元數 | 1-O 至少需有 8 個 TX 單元與 8 個 RX 單元 | 104-032 |
| 4 | G/S 稱「3GPP 沒有 element/TRX mapping」 | 38.901 calibration 表有 (M,N,P,Mg,Ng;Mp,Np) 記法與 port mapping 描述 | 901-060..066 |
| 5 | G/S 未說明 tuple 順序 | §7.3.0 使用 (Mg,Ng,M,N,P)；calibration 表使用 (M,N,P,Mg,Ng;Mp,Np) | 901-016, 901-060 |
| 6 | G 使用 front_back／side_lobe 等名稱 | 原文名稱為 SLA_V=30 dB、A_max=30 dB（A_max 同時是水平切面與 3D pattern 的上限；S 的說明不完整） | 901-020..022 |
| 7 | G/S 未提 UT pattern | 手持 UT 為 125°、22.5 dB、5.3 dBi | 901-027 |
| 8 | S 對 ±45° 的說明未區分模型 | ±45° 為 Model-1 的定義；calibration 採用 Model-2，BS 為 ±45°，UT 為 0/+90° | 901-032, 901-063 |
| 9 | S：「最直接的 beamforming parameter 是 38.901 §7.3.1 的 antenna port mapping」 | 該式僅為 legacy ULA 的固定垂直 tilt，且屬 TR；規範中的 beam 以 SSB index、CRI、TCI、QCL-TypeD 表示；DL precoding 對 UE 透明（38.211 §7.3.1.4） | 901-030, 211-016, 214-001 |
| 10 | G：element 總數 = Mg·Ng·M·N·P | 數學上正確，但屬推導，原文未寫出 | 901-012 |
| 11 | G/S 未提 38.104 的 beam 宣告與 EIRP/TRP 規則 | 見 §9.2.1、§9.2.2/9.2.3、§9.3.1、§6.1、§10.2；完整宣告清單在 38.141-2（38.104 的 Annex D 為干擾訊號特性） | 104-040..049, 1412-010 |
| 12 | G/S 把 TRXUA、composite antenna、RDN 當作 §3.1 的正式定義 | 三者皆非 §3.1 定義，只出現在圖文字或 §4.3.2 本文 | 104-027 |
| 13 | G/S 認為 CSI-RS port 上限只有 32 | 單一 resource 的上限為 32；Rel-19 以聚合 K 個 resource 支援 48/64/128 port | 211-031, 214-055, 214-071 |
| 14 | G 以「32 ports ≠ 32 layers」說明但缺少依據 | PDSCH／PUSCH 最多 8 層；maxMIMO-Layers 為 1..8 | 211-015, 211-012, 331-013 |
| 15 | G 只引用 antenna port 定義的前半 | 需搭配 QCL 定義（spatial Rx）才能說明 beam | 211-002 |
| 16 | S：portSubsetIndicator 的 bit i 對應 3000+i，最長 32 bit | Rel-15 為正確；Rel-19 另有 48/64/128 bit 版本，僅用於 sub-configuration 且限搭 Type I；聚合 port 的編號另依 portMappingMethod | 214-069, 211-032 |
| 17 | G/S 未提 SSB 為單 port 及 SSB index 的 QCL 規則 | SSB 使用 port 4000；相同 index 才互為 QCL | 211-040, 211-009 |
| 18 | G/S 未提 DM-RS port 上限與 DCI antenna port 表 | basic 為 8/12，enhanced 為 16/24；DCI 欄位為 4～8 bit | 211-023, 212-001 |
| 19 | G/S 的 codebook 列舉只有 3～4 種 | 另有 r16、r17、r18（CJT、Doppler）、r19 共 13 種以上；CodebookConfig 另有 -r16/-r17/-v1730/-r18/-r19 等 IE | 214-068, 331-009 |
| 20 | G 範例未說明 max_rank 與 codebook 的關係 | Type I SP ≤ 8；MP ≤ 4；Type II/PS ≤ 2；eType II 系列 ≤ 4 | 214-068 |
| 21 | G/S 缺少 beam management 程序 | 見本文件 §8、§10 | 214-*, 213-*, 321-* |
| 22 | G 未引用 Table 5.2.2.2.1-2 | (N1,N2)/(O1,O2) 定義於 38.214 Table 5.2.2.2.1-2 | 214-052 |
| 23 | S 的 Type I SP CBSR 大小表 | 數值正確；但 ASN.1 分支全名為 `…-TypeI-SinglePanel-Restriction`，且 S 漏列 typeI-SinglePanel-codebookSubsetRestriction-i2（16 bit） | 331-009（04-E1/E2） |
| 24 | S 的 Type II 只列 RI restriction | 遺漏 n1-n2-codebookSubsetRestriction，其位元數與 Type I 不同 | 331-009（04-E5） |
| 25 | S 的 portSelectionSamplingSize 未標為 OPTIONAL | 應為 OPTIONAL（Need R） | 331-009（04-E6） |
| 26 | S 的 CodebookConfig-r19 結構 | 頂層與 type1 皆為 CHOICE；S 缺少 typeI-CodebookSubsetRestriction-r19、SoftScalingRank-r19、ng-n1-n2-cbsr-r19 的位元數、type2（etypeII-r19 等）與 cri-* 欄位 | 331-009（04-E8～E13） |
| 27 | S 的 n1-n2-r19 未註明前提 | 需聚合 K 個 resource，O1 = O2 = 4，且為 ENUMERATED（不帶 BIT STRING） | 214-055, 331-009 |
| 28 | G 的 n1-n2 描述 | 漏了「and codebook subset restriction」 | 331-009（04-E14） |
| 29 | S 的 csi_rs_resource_mapping | 數值正確；但漏標 firstOFDMSymbolInTimeDomain2 的 Need R 與擴充標記 | 331-002（04-E15） |
| 30 | S 的參考文獻只列 IE 名稱 | 應附章節與頁碼（例如 CodebookConfig 位於 §6.3.2 pp.793–801） | 04-E16 |
| 31 | G/S 未提層數上限所在的 IE | PDSCH-ServingCellConfig/PDSCH-Config 的 maxMIMO-Layers；PUSCH 的 maxMIMO-Layers(-v1810)、maxRank(-v1810) | 331-012, 331-013, 331-016, 331-017 |
| 32 | G/S 未提 L1-RSRP 位寬、nrofReportedRS、TCI 數量、BFD 參數 | 見 R-L5-83～85、R-L5-04～08、R-L6-24 | 214-042, S331-001, 321-001 |

---

## 12. 未解決／未找到清單

### 12.1 原文不一致（依較新版本或原文處理，並記錄於此）
| # | 內容 | 本文件的處理 | 出處 |
|---|---|---|---|
| 1 | CUS SE27 numElements：Table 7.6.1-1 寫 6b，§7.7.27.3 寫 8 bits（0–255，0 表示 256） | 以內文 8 bit 為準，並標註存疑 | CUS-040, CUS-063 |
| 2 | CUS SE20 numPuncPrb：Table 寫 10b，內文寫 8 bits；numPuncPatterns 值域寫 6 bit 格式，但 Field length 為 8 bits | 以內文為準，並標註存疑 | CUS-040, CUS-057 |
| 3 | CUS SE32 在表中名稱為 measurement report，標題為 measurement request | 採用標題名稱 | CUS-040 |
| 4 | CUS Annex J.1 寫「four distinct methods」，但 §12.4.1 列出 5 種（含 DMRS-BF） | 依 §12.4.1 與 YANG 的 7 個列舉值 | CUS-010, MP-005 |
| 5 | 38.211 §6.3.1.3 寫 UL「up to four layers」，但 §6.3.1.5 定義了 8 port、最多 8 層；38.300 寫 UL 支援最多 4 或 8 層 | 以 8-port 表與 38.300 為準；待查 CR | 211-010, 211-012, 300-002 |
| 6 | MP §15.4.7.2 使用名稱 max-total-null-width，YANG 為 max-total-null-point-width | 以 YANG 名稱為準 | MP-130 |
| 7 | MP §15.4.4 寫 tilt「per band」，YANG 以 capabilities-group 為 key | 以 YANG 為準 | MP-049 |
| 8 | number-of-spatial-streams 的描述：2022-12-05 版寫「DL 等於 38.214 CSI 的 antenna port 數」；v21.01 改為「DL 與 UL 最大累計空間流數」，並新增 -dl/-ul | 以 v21.01 為準；「等於 CSI port 數」僅作為舊版參考，不列為強制規則 | ORAN-M05, MP-070 |
| 9 | fronthaul-split-option 描述寫「2 or 7」，range 只允許 7 | 以 range 為準 | ORAN-M09 |
| 10 | 舊版 YANG 的 frequency-granularity description 與欄位名稱不符 | 依欄位名稱解讀 | ORAN-B07 |
| 11 | YANG 原文拼字：COALOCATED、suported、Estension、DMRX/DMS | schema 保留原文拼字 | MP-013, MP-004, 07 §12.1 |
| 12 | 38.901 §7.3.2 引用的 Table 7.1-1 不存在；Table 7.8-6C NOTE 3 引用的 Table 7.5.14-1 應為 Table 7.6.14.2-1 | 記錄為原文錯誤 | 901-033, 901-067 |
| 13 | 38.104 §9.3.2 引用 38.141-1 Annex B，但 1-O 屬 OTA，疑應為 38.141-2 | 記錄為疑似原文錯誤 | 104-044 |
| 14 | 38.104 §3.1 使用「equivalent isotropic radiated power」，§3.3 使用「Effective」 | 記錄為用詞差異 | 104-009 |
| 15 | nrofReportedRS 的 N_max 描述為 2/4/6/8，UE 能力 maxNumberNonGroupBeamReporting 的 ASN.1 值域為 {n1,n2,n4}（6/8 可能對應其他版本欄位，摘錄未收錄） | 以 38.331 描述為準，並標註待查 | 331-008, 331-021 |
| 16 | maxNumberSSB-BFD／CSI-RS-BFD：ASN.1 值域為 1..64，38.306 註明本版最大可回報 16 | 兩者並列 | 331-021, 306-012, 306-013 |
| 17 | 38.214 §5.2.2.2.9a 寫 valueOfN-r19 不得使用 paramCombination 8；38.331 的 typeII-FePortSelection-r19 值域為 1..7 | 一致，以 1..7 為準 | 214-067, 331-009 |
| 18 | 38.141-1 D.33（TAB connector RX min cell group）的 Description 寫 "…with transmission on all TAB connectors…"，但 §3.1 的定義寫 "…with **reception** on…" | 以 §3.1 定義為準（RX 側為 reception），記錄為原文疑似錯誤 | 1411-004, 1411-024（09 §E #1） |
| 19 | 38.141-1 §6.1.2 寫 TAB→**cells** 為 implementation dependent，§7.6.1 寫 TAB→**cells/beams** | 並列記錄；兩處語意相同 | 1411-009, 1411-010（09 §E #2） |
| 20 | 38.141-1 D.38/D.39/D.40 皆寫 "as in D.15"，但 D.15 的內容是 CA-only operation 宣告，而非 CA 能力清單 | 依 D.15 原文解讀（CA capable connector 的判定），記錄為引用可能不精確 | 1411-025（09 §E #3） |
| 21 | 37.466 原文拼字／格式：§6.7.3 "Unsigned interger"、Annex B "not intialized"、Table 6.3.4 "it the TMA subunit"、Annex B bearing 寫 "0 – 359,9 degree"（歐式小數逗號）；Table B.1 欄位順序為 0x01,0x02,0x03,0x08–0x0B,0x04,0x05,0x06,0x07,0x21… | 分別視為 integer／initialized／if／0–359.9°（編碼 0..3599）；欄位以 FieldNumber 尋址，順序無語意 | 37466-014, 37466-020, 37466-023（09 §E #4–#8） |

### 12.2 未找到或未摘錄
| # | 項目 | 狀態 |
|---|---|---|
| 1 | TS 38.141-1（1-H 的傳導宣告：TX/RX min cell group、per-connector 宣告等） | **已解決**：V19.5.0 已下載並摘錄，見 `extracts/09_38141-1_ALD.md` [1411-020]～[1411-028]、R-L2-33～40。唯「TAB connector 總數」與 `NTXU,active`／`NRXU,active` 本身仍無獨立宣告 ID（見本表 #23） |
| 2 | TS 37.466／37.462／37.461（RET tilt 的值域與單位） | **已解決**：V19.0.0 已下載並摘錄，見 `09` [37466-003]（int16 × 0.1°，正值向下）、[37466-014]（值域由 device data 0x06/0x07 宣告）、[37462-002]（device type）。AISG 2.0 原文仍未取得（見本表 #29） |
| 3 | TR 38.802（P1/P2/P3 的定義出處） | 本地沒有 |
| 4 | TS 28.541／28.552／28.662（O1 beam NRM、retTiltValue、bCIO） | 本地沒有 [WG1-002/004/005] |
| 5 | 38.901 一般化的 sub-array（element→TXRU）權重 | 未找到 [901-068] |
| 6 | 38.901 Model-2 引用的 Table 7.1-1 | 原文不存在 |
| 7 | O-RAN YANG 中每個 beam 的指向角、波束寬度 leaf；權重檔格式 | 未找到；格式為 implementation specific [MP-045/047] |
| 8 | SE2 角度的量化步距；ABBF 六個屬性有效範圍對應的 YANG leaf | 未找到 [CUS-042, CUS-020] |
| 9 | SE8 regularizationFactor 16-bit 值與雜訊變異數的換算 | 未找到 [CUS-046] |
| 10 | CUS §8.1.3.3 CAT-A/B 的功率不等式 | 未逐條抽取 [CUS-076] |
| 11 | Table 7.7.6.2-1（rbgSize 對應的 PRB 數） | docx 中為圖形欄位，未抽出 [CUS-044] |
| 12 | 38.133 CSI-RS-based RLM/BFD/CBD 表、P_CBD、L1 的定義、UL 與 mTRP unified TCI（§8.16、§8.21–8.24） | 有出處但未摘錄 [08 末] |
| 13 | Qout/Qin 對應的 SNR dB 值 | 由 UE 實作決定，規範未給 [133-001] |
| 14 | beam centre direction 的量測程序 | 38.141-2 未提供 [1412-002] |
| 15 | Table 5.2.2.2.7-1 的 α/β 數值；Type I MP 表未以 PDF 目視核對 | 待核對 [214-062, 214-056] |
| 16 | nrofReportedRS-r19 的值域 | 未找到 [214-040] |
| 17 | DCI 1_1 的 CSI request 欄位 | V19.4.0 中不存在 [212-005] |
| 18 | 38.306 twoLayersInterferenceMeasurement、dmrs-TypeB | 全文無此名稱 [306-027, 306-034] |
| 19 | 38.212 CSI 欄位排列順序表的內容 | 僅列出表號 [212-026] |
| 20 | 本地 2022-12-05 YANG 中與 SE19/SE20／DMRS-BF 相關的 leaf | 已由 v21.01 補查（MP-003/004）；SE19 沒有專屬 capability leaf，改以 supported-section-extensions 回報 |
| 21 | O-RAN download id 與文件的對應、部分 ETSI URL | 未連線驗證 |
| 22 | element→TRX 映射矩陣（W_RF）、port→TRX 映射 | 無標準，schema 以 [SIM] 欄位提供 |
| 23 | TS 38.141-1 中「TAB connector 總數」的獨立宣告項，以及 `NTXU,active`／`NRXU,active` 的宣告 ID | 未找到；只能由 per-connector 宣告（D.3/D.8/D.11/D.14/D.21/D.22/D.27）清單長度 + D.32/D.33/D.34 間接推得 [1411-020] |
| 24 | TS 38.141-1 中「MIMO 層數」「antenna port 數」宣告 | 未找到；Table 4.6-1 完全沒有此類宣告（見 R-L2-40）[1411-026] |
| 25 | TS 38.141-1 中 beam／指向角／beamwidth 宣告 | 未找到；全部在 38.141-2 [1411-028][1412-010] |
| 26 | TS 37.466 中 RET tilt 的**固定**絕對值域 | 未找到；規格只給編碼（int16 × 0.1°）與「由 device data 0x06/0x07 宣告」[37466-003][37466-014] |
| 27 | 由 RET 讀取 beamwidth／gain | **本版不支援**；Table B.1 欄位 0x04/0x05 標 "Not supported in this release"（operating band 欄位 0x03/0x08–0x0B 亦同）[37466-014][37466-024] |
| 28 | MultiRET／MHA／RAE（O-RAN [MP-140] 提到的其他 ALD 類型） | 未找到；TS 37.462 只定義 3 種 device type（0x01/0x11/0x02）[37462-002] |
| 29 | AISG 2.0 原文（vendor code 表、RETAP 擴充程序） | 本地沒有此文件；3GPP 只引用 vendor code 與 TMA subunit type bit 1 [37462-003][37466-023] |
| 30 | RET configuration data（drive 位置 ↔ beam tilt 對映表）的格式 | **vendor specific**，3GPP 未標準化 [37466-016] |
| 31 | Iuant 與 O-RAN `ald-communication` 的正式對映（哪一方負責組 RETAP 訊息） | 3GPP 側未找到（Iuant 為 gNB 內部介面，未提 O-RAN）；O-RAN 側只說透傳 [MP-141][37466-030] |
| 32 | 37.466 Annex A（return/alarm code 值表）、Annex C（軟體下載序列）、Annex E（I-frame/INFO-field 格式）、Annex F（operating band 編碼範例） | 有出處（p.45、49、51、52–54），未逐條摘錄 [09 §F #11] |
| 33 | 37.466 §6.5.1–6.5.5／6.5.9–6.5.14／6.6.6–6.6.7／6.7.1／6.7.4–6.7.8／6.7.10／6.8.1–6.8.13 的完整參數表 | 有出處，未逐條摘錄（只取 tilt／calibrate／config／alarm／self-test 相關）[09 §F #12] |
| 34 | 37.461 §4.3.1–4.3.12（modem RF 特性）與 37.462 §4.6 state model／§4.8 XID／§4.9–4.10 link establishment | 有出處，未摘錄（與天線幾何／波束無關）[09 §F #13/#14] |
