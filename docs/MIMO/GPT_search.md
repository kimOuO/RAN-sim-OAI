
可以，而且我查過 Release 19 後，我會先修正一個很重要的觀念：

**3GPP 並沒有一份跨 38.901、38.104、38.331 的官方「AntennaConfig」總 schema。**
真正存在的是三套不同目的的描述：

* TR 38.901：描述 **physical antenna array / channel-model antenna**
* TS 38.104：描述 **TRXUA、RDN、antenna array 的 RF 架構與邊界**
* TS 38.211 / 38.214 / 38.331：描述 **UE 所看到的 logical antenna ports、CSI-RS、rank、PMI/codebook**

因此如果你現在是在做 simulator，最合理的方法是建立一份 **3GPP-aligned unified antenna schema**，把三層接在一起，但明確標示哪些欄位是 3GPP 原生、哪些是 simulator 為了 mapping 自己補的。

下面我直接把它整理成一份可以實作的 spec。

---

# 1. 先把 Layer 3 補清楚：Antenna Port 到底是什麼？

Layer 3 最大的陷阱，就是看到：

```text
8 ports
16 ports
32 ports
```

很容易以為：

```text
32 ports = 32 根 antenna
```

**不是。**

38.211 對 antenna port 的定義非常抽象：

> 同一 antenna port 上的一個 symbol 所經歷的 channel，可以由同一 port 上另一個 symbol 的 channel 推知。 ([歐洲電信標準協會][1])

所以：

```text
Antenna element
= 真正的物理輻射元件

RF/TRX
= 真正的射頻硬體路徑

Antenna port
= UE / PHY 看到的邏輯 channel identity
```

例如：

```text
Physical elements
X X X X
X X X X
X X X X
X X X X
    │
    │ beamforming
    ▼
RF/TRX
    │
    ▼
CSI-RS Port 3000
```

一個 CSI-RS port 完全可以是**很多 physical elements 經過 beamforming 後形成的邏輯 port**。

---

## CSI-RS 的 `nrofPorts`

38.331 Release 19 的 ASN.1 真的定義：

```asn1
nrofPorts ENUMERATED {
    p1,
    p2,
    p4,
    p8,
    p12,
    p16,
    p24,
    p32
}
```

也就是一個 CSI-RS resource 可以配置：

$$
N_{\text{CSI-RS ports}}
\in
\{1,2,4,8,12,16,24,32\}
$$

這是正式 protocol schema。 ([歐洲電信標準協會][2])

所以如果 gNB RRC configuration 告訴 UE：

```yaml
nrofPorts: p8
```

意思是：

> 「你現在拿來做 channel measurement 的這組 CSI-RS，有 8 個 logical antenna ports。」

不是：

> 「基地台後面只有 8 根實體 antenna。」

---

# 2. Layer 3 的 Port → PMI → RI → MIMO 關係

UE 大概是在做：

```text
CSI-RS ports
     │
     ▼
UE measure channel
     │
     ▼
estimate H
     │
     ├── RI
     │   Rank Indicator
     │
     │   「我覺得可以同時傳幾層」
     │
     ├── PMI
     │   Precoding Matrix Indicator
     │
     │   「我覺得用哪個 precoder 比較好」
     │
     └── CQI
         Channel Quality Indicator
```

所以例如：

```text
32 CSI-RS ports
```

完全不代表：

```text
32 layers
```

可能實際：

```text
CSI-RS ports = 32

UE channel rank = 4

PDSCH layers = 4
```

38.214 本身就定義 Type-I/Type-II codebook、PMI、RI 等 procedure；例如 Type-I codebook 有對多層 CSI reporting 的 precoder 定義。 ([歐洲電信標準協會][3])

因此三個數字一定要分開：

$$
\boxed{
N_{\text{physical elements}}
\neq
N_{\text{TRX}}
\neq
N_{\text{CSI-RS ports}}
\neq
N_{\text{layers}}
}
$$

它們有關係，但沒有固定相等。

---

# 3. 所以我建議你的 3GPP-aligned Antenna Schema 長這樣

這不是 3GPP 官方 ASN.1；這是我按照目前 Release 19 幾份 spec 整合出來的 **Normalized Antenna Data Model**。

```yaml
antenna_system:

  spec:
    profile: "3gpp-aligned"
    release: 19

  # ==========================================
  # Layer 1 — Physical Antenna Array
  # 3GPP TR 38.901
  # ==========================================

  physical_array:

    panel_grid:
      Mg: 1
      Ng: 1

    elements_per_panel:
      M: 8
      N: 4

    polarization:
      P: 2

    element_spacing:
      dV_lambda: 0.5
      dH_lambda: 0.5

    panel_spacing:
      dgV_lambda: null
      dgH_lambda: null

    orientation:
      bearing_deg: 0
      downtilt_deg: 0
      slant_deg: 0

    element_pattern:
      model: "3GPP_TR_38.901_reference"
      horizontal_3dB_beamwidth_deg: 65
      vertical_3dB_beamwidth_deg: 65
      max_directional_gain_dBi: 8
      front_back_attenuation_dB: 30
      side_lobe_attenuation_dB: 30

    derived:
      physical_positions: 32
      polarized_elements: 64


  # ==========================================
  # Layer 2 — RF / TRX
  # 3GPP TS 38.104
  # ==========================================

  rf_system:

    bs_interface_type: "1-H"

    trxua:

      tx_units:
        count: 32

      rx_units:
        count: 32

    transceiver_array_boundary:
      type: "TAB"

    radio_distribution_network:
      type: "implementation_specific"

      # simulator extension
      trx_to_element_mapping: null


  # ==========================================
  # Layer 3 — Logical antenna / CSI / MIMO
  # TS 38.211 / 38.214 / 38.331
  # ==========================================

  logical_phy:

    csi_rs:

      nrofPorts: p32

      frequency_domain_allocation: null
      cdm_type: null
      density: null

    mimo:

      codebook_type: "typeI-SinglePanel"

      rank:
        configured_max: 8
        active: 4

      layers:
        active: 4

    # simulator extension
    port_to_trx_mapping: null
```

這樣就已經把你現在一直討論的三個世界切乾淨了。

---

# 4. Layer 1 哪些是真的 3GPP？

38.901 Release 19 V19.4.0 明確定義 BS antenna 為 uniform rectangular panel array，並用：

$$
\boxed{(M_g,N_g,M,N,P)}
$$

描述。

其中 \(M_g,N_g\) 是 panel grid；\(M,N\) 是每 panel 的 element arrangement；\(P=1\) 或 \(2\) 分別代表 single-/dual-polarized。並且另外描述 \(d_H,d_V,d_{g,H},d_{g,V}\)。 ([歐洲電信標準協會][4])

因此：

$$
N_{\text{position}}
=
M_gN_gMN
$$

而如果把 polarization branch 分開：

$$
N_{\text{pol-elements}}
=
M_gN_gMNP
$$

例如：

```yaml
Mg: 1
Ng: 1
M: 8
N: 4
P: 2
```

就是：

$$
1\times1\times8\times4=32
$$

個 antenna locations，以及：

$$
32\times2=64
$$

個 polarized elements。

另外 38.901 的 reference element pattern 確實使用 65° vertical、65° horizontal、8 dBi maximum directional gain，以及 30 dB attenuation parameters。 ([歐洲電信標準協會][4])

注意這些 **65° / 8 dBi 是 38.901 channel-model reference element**，不是所有商用基地台硬體的強制值。

---

# 5. Layer 2 哪些是真的 3GPP？

這層我會稍微修改你原本的 schema。

38.104 的結構是：

```text
              TRXUA
       ┌─────────────────┐
       │ TX / RX units   │
       └────────┬────────┘
                │
               TAB
                │
       ┌────────▼────────┐
       │       RDN       │
       └────────┬────────┘
                │
       ┌────────▼────────┐
       │ Antenna Array   │
       └─────────────────┘
```

Release 19 V19.5.0 明確寫：

* TRXUA 中 transmitter units 數量 implementation specific
* receiver units 數量 implementation specific
* TX/RX 可以組成 transceiver units
* transmitter/receiver units 能處理 parallel independent modulated symbol streams
* RDN 將 TRXUA 的 RF power 分配到 antenna array，mapping 同樣 implementation specific。 ([歐洲電信標準協會][5])

所以你的 schema 不應該寫：

```yaml
64T64R:
  elements: 192
```

而應該寫：

```yaml
trxua:
  tx_units: 64
  rx_units: 64

rdn:
  mapping: implementation_specific

physical_array:
  polarized_elements: 192
```

然後另外一張 matrix 描述兩者關係。

---

# 6. 我甚至建議 mapping 用 Matrix，而不是 hard-code 關係

這會對你後面做 beamforming 非常有用。

例如有：

$$
N_{TX}=4
$$

以及：

$$
N_{element}=16
$$

可以定義：

$$
\mathbf W_{RF}
\in
\mathbb C^{16\times4}
$$

也就是：

```text
              RF chains

             TX0 TX1 TX2 TX3
              │   │   │   │
             ┌───────────────┐
Element 0    │ w00 ...       │
Element 1    │ w10 ...       │
Element 2    │ w20 ...       │
...          │               │
Element 15   │          w15,3│
             └───────────────┘
```

一個 coefficient：

$$
w_{m,n}
$$

代表：

> TX chain \(n\) 對 antenna element \(m\) 的 amplitude + phase weight。

這樣你就完全不需要假設：

```text
TX0 → element0
TX1 → element1
...
```

---

# 7. Layer 3 我建議再獨立成 `logical_phy`

因為它根本不是「天線硬體」。

最小版本可以只有：

```yaml
logical_phy:

  csi_rs:
    nrofPorts: p32

  codebook:
    type: typeI-SinglePanel

  mimo:
    max_rank: 8
```

其中 `nrofPorts` 的合法值直接跟 38.331 一致：

```yaml
enum:
  - p1
  - p2
  - p4
  - p8
  - p12
  - p16
  - p24
  - p32
```

([歐洲電信標準協會][2])

而 38.331 的 `CodebookConfig` 本身還真的存在：

```text
CodebookConfig
 └─ codebookType
     ├─ type1
     │   ├─ typeI-SinglePanel
     │   └─ typeI-MultiPanel
     │
     └─ type2
         ...
```

Release 19 還進一步擴充了 Type-I / Type-II 的配置與 RI restrictions。 ([歐洲電信標準協會][2])

---

# 8. 但這裡有一個非常重要的 naming trap

你會在 codebook 裡又看到：

```text
N1
N2
Ng
```

**不要把它跟 38.901 的 \(M,N,M_g,N_g\) 直接畫等號。**

例如 38.331 的 `n1-n2` field description 是：

> 第一維和第二維的 **antenna ports 數量**

而不是 physical elements。 ([歐洲電信標準協會][2])

所以：

```text
38.901:

M, N
= physical antenna element geometry
```

而：

```text
38.331 / 38.214:

N1, N2
= logical/codebook antenna-port dimensions
```

名字看起來很像，但不是同一層。

這個你們 simulator 一定要避免混在一起。

---

# 9. 因此，我會正式把 Schema 定義成這樣

如果你要開始真的寫程式，我推薦下面這個版本：

```yaml
AntennaSystemSpec:

  identity:
    id: string
    three_gpp_release: 19

  physical_array:
    # TR 38.901

    Mg: integer >= 1
    Ng: integer >= 1

    M: integer >= 1
    N: integer >= 1

    P:
      enum: [1, 2]

    spacing:
      dH_lambda: float
      dV_lambda: float
      dgH_lambda: float | null
      dgV_lambda: float | null

    orientation:
      bearing_deg: float
      downtilt_deg: float
      slant_deg: float

    element_pattern:
      model: reference | custom

      theta_3dB_deg: float
      phi_3dB_deg: float
      max_gain_dBi: float
      front_back_limit_dB: float

    derived:
      panel_count:
        Mg * Ng

      physical_positions:
        Mg * Ng * M * N

      polarized_elements:
        Mg * Ng * M * N * P


  rf_system:
    # TS 38.104

    bs_type:
      enum:
        - type1-C
        - type1-H
        - type1-O
        - type2-O

    trxua:
      tx_units: integer
      rx_units: integer

    rdn:
      mapping_type:
        enum:
          - implementation_specific

      # unified simulator extension
      rf_weight_matrix:
        dimensions:
          - polarized_elements
          - tx_units


  logical_ports:
    # TS 38.211 / 38.331

    csi_rs:
      nrofPorts:
        enum:
          - 1
          - 2
          - 4
          - 8
          - 12
          - 16
          - 24
          - 32

    codebook:
      type:
        enum:
          - typeI-SinglePanel
          - typeI-MultiPanel
          - typeII

      n1: optional
      n2: optional
      ng: optional

    # simulator mapping, NOT standardized by 3GPP
    port_to_trx_mapping:
      dimensions:
        - tx_units
        - csi_rs_ports
```

我認為這已經很接近你要的：

> **「純天線、但能把 3GPP 三層串起來的 data schema。」**

---

# 10. 接下來 Beamforming 不應該修改 `physical_array`

這點非常重要。

假設你的天線永遠是：

```yaml
physical_array:
  Mg: 1
  Ng: 1
  M: 8
  N: 4
  P: 2
```

也就是：

```text
32 positions
64 polarized elements
```

今天 beam 朝 0°：

```text
             ↑
             ↑
          beam
             │
 X X X X X X X X
```

明天 beam 朝 +30°：

```text
                      /
                     /
                    /
 X X X X X X X X
```

physical schema **一個字都不用改**。

真正改的是：

```yaml
beamforming:
  weights: ...
```

---

# 11. Beamforming Schema 我會這樣擴充

```yaml
beamforming:

  architecture:
    enum:
      - digital
      - analog
      - hybrid

  active_mode:
    beam_id: beam_01

  beams:

    - id: beam_01

      target:
        azimuth_deg: 20
        elevation_deg: -8

      analog_precoder:
        enabled: true

        W_RF:
          dimensions:
            - polarized_elements
            - rf_chains

      digital_precoder:
        enabled: true

        W_BB:
          dimensions:
            - rf_chains
            - layers
```

數學上：

$$
\mathbf x
=
\mathbf W_{RF}
\mathbf W_{BB}
\mathbf s
$$

---

## Digital Beamforming

例如：

```yaml
architecture: digital

W_RF: identity

W_BB:
  rows: 32
  columns: 4
```

概念：

```text
4 layers
   ↓
W_BB
   ↓
32 RF chains
   ↓
32 antenna branches
```

---

## Analog Beamforming

```yaml
architecture: analog

rf_chains: 1

W_RF:
  rows: 64
  columns: 1
```

就是：

```text
       1 RF
        │
       W_RF
   ┌────┼────┐
   ↓    ↓    ↓
 element element element ...
```

靠 phase shifter 形成 beam。

---

## Hybrid Beamforming

```yaml
architecture: hybrid

layers: 4
rf_chains: 8
elements: 64

W_BB:
  shape: [8, 4]

W_RF:
  shape: [64, 8]
```

所以：

```text
4 layers

   ↓ W_BB

8 RF chains

   ↓ W_RF

64 polarized elements
```

這是你的 unified schema 最有價值的地方。

---

# 12. MIMO 我則會另外做成「mode」，不要放進 physical antenna

例如同一套硬體：

```yaml
physical:
  elements: 64

rf:
  tx_units: 32

logical:
  csi_rs_ports: 32
```

可以存在不同 mode。

### Mode A：正常 Massive MIMO

```yaml
mimo_mode:
  id: full_capacity

  active_tx_units: 32

  csi_rs_ports: 32

  max_rank: 8

  active_layers: 4
```

物理 antenna：

```text
64 elements
```

完全沒改。

---

### Mode B：同硬體，只換 beam

```yaml
mimo_mode:
  id: beam_right

  active_tx_units: 32

  csi_rs_ports: 32

  active_layers: 4

beamforming:
  target_azimuth_deg: 30
```

依然：

```text
64 elements
32 TX
32 CSI ports
4 layers
```

只是：

$$
W
$$

變了。

---

### Mode C：Energy-saving / RF-chain reduction

```yaml
mimo_mode:
  id: energy_saving

  active_tx_units: 16

  csi_rs_ports: 16

  active_layers: 2
```

這次不只是 beam 轉向。

而是：

```text
32 TX available
       ↓
16 TX active
```

因此 spatial degrees of freedom 有可能下降。

但 physical：

```yaml
polarized_elements: 64
```

仍然沒變。

---

# 13. 所以我最後會把你的 simulator 架構切成「Static Spec + Runtime Mode」

這可能是你真正需要的設計。

```text
              AntennaSystemSpec
             STATIC / HARDWARE
┌─────────────────────────────────────┐
│ Physical Array                      │
│ Mg Ng M N P                         │
│ spacing                             │
│ orientation                         │
│ element pattern                     │
│                                     │
│ TRX capability                      │
│ max TX / RX units                   │
│                                     │
│ logical capability                  │
│ supported CSI-RS ports              │
└──────────────────┬──────────────────┘
                   │
                   │
                   ▼
              AntennaMode
           DYNAMIC / CONTROL
┌─────────────────────────────────────┐
│ active TX/RX                        │
│ active CSI-RS ports                 │
│                                     │
│ beamforming architecture            │
│ W_RF                                │
│ W_BB                                │
│                                     │
│ active rank                         │
│ active layers                       │
│ codebook                            │
└──────────────────┬──────────────────┘
                   │
                   ▼
               Radiation
                   │
                   ▼
             Channel H
                   │
                   ▼
             UE CSI feedback
            RI / PMI / CQI
```

**這比把所有東西塞進一個 `rows × cols × ports` 正確很多。**

最核心的資料關係可以濃縮成：

$$
\boxed{
\text{Physical Elements}
\xleftarrow{W_{RF}}
\text{RF/TRX}
\xleftarrow{W_{BB}}
\text{Logical Ports/Layers}
}
$$

或者從資料流方向寫：

$$
\boxed{
\mathbf s
\rightarrow
\mathbf W_{BB}
\rightarrow
\text{RF chains}
\rightarrow
\mathbf W_{RF}
\rightarrow
\text{physical elements}
\rightarrow
\text{beam}
}
$$

其中 3GPP **有標準化 Layer 1 的 reference array model、有定義 Layer 2 的 RF boundaries、有正式定義 Layer 3 的 protocol/port schema；但沒有標準化中間完整的 `192 elements → 64 TRX → 32 ports` mapping。** 那一部分正是你們 simulator 應該自己抽象成 mapping matrix 的地方。

如果以你現在的目的來看，我會直接以這個 **`AntennaSystemSpec + AntennaMode`** 當你們後續程式的 data model，而不是再用單純 `rows / cols / tx / rx`。

[1]: https://www.etsi.org/deliver/etsi_TS/138200_138299/138211/19.04.00_60/ts_138211v190400p.pdf
[2]: https://www.etsi.org/deliver/etsi_ts/138300_138399/138331/19.03.00_60/ts_138331v190300p.pdf
[3]: https://www.etsi.org/deliver/etsi_ts/138200_138299/138214/19.04.00_60/ts_138214v190400p.pdf
[4]: https://www.etsi.org/deliver/etsi_tr/138900_138999/138901/19.04.00_60/tr_138901v190400p.pdf
[5]: https://www.etsi.org/deliver/etsi_ts/138100_138199/138104/19.05.00_60/ts_138104v190500p.pdf
