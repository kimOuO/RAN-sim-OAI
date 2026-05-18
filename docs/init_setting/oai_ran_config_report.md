# OpenAirInterface5G RAN 初始設定整理與數位雙生影響評估

> 來源:`/home/mitlab/openairinterface5g/ci-scripts/conf_files/` 與 `targets/PROJECTS/GENERIC-NR-5GC/CONF/`
> 對象:XAPP_DT 專案(NVIDIA AODT + Sionna RT)的 xApp Handover 驗證流程
> 日期:2026-05-15

---

## 0. 取樣的設定檔

本份報告涵蓋以下代表性 OAI 設定檔(monolithic、F1 split、N2 HO、neighbour、UE 五大類):

| 檔案 | 角色 |
|---|---|
| `gnb.sa.band78.106prb.rfsim.conf` | 單體 gNB(rfsimulator,n78、106 PRB) |
| `gnb.sa.band78.106prb.rfsim.neighbour.conf` | 含 neighbour 的單體 gNB |
| `gnb-cu.sa.f1.ho.conf` | F1 切分下的 CU(支援 HO) |
| `gnb-du.sa.band78.51prb.usrpb210.ho-pci0.conf` | DU0(PCI=0) |
| `gnb-du.sa.band78.51prb.usrpb210.ho-pci1.conf` | DU1(PCI=1) |
| `gnb-cucp.sa.e1-ho-n2.conf` | CU-CP(N2 inter-gNB HO) |
| `neighbour-config.conf` / `neighbour-config-ho.conf` | 鄰區與量測事件 |
| `nrue.uicc.conf` | OAI UE(rfsim) |

---

## 1. 整合後的 RAN 設定總覽

### A. 識別與拓撲(Identity / Topology)
```libconfig
gNB_ID            = 0xe00 / 0xb00 / 0xe88        # CU=0xe88, DU0=0xe00, DU1=0xe01
gNB_DU_ID         = 0xe00 / 0xe01                 # F1 split 時 DU 各自一個
gNB_name          = "gnb-rfsim" / "DU0-OAI" / "CU-OAI"
tracking_area_code= 1
plmn_list         = ({ mcc=208/001; mnc=99/03; mnc_length=2;
                       snssaiList=({sst=1, sd=0xffffff}) })
nr_cellid         = 12345678L / 11111111L         # 全域 cell ID
physCellId        = 0 / 1                         # PCI(UE 直接量測對象)
```

### B. 載波 / 頻段(RF Carrier)
```libconfig
dl_frequencyBand              = 78 (或 77)
absoluteFrequencySSB          = 621312 (≈3319.68 MHz) / 641280 / 679104
dl_absoluteFrequencyPointA    = 620040
dl_subcarrierSpacing          = 1                 # 30 kHz (μ=1)
dl_carrierBandwidth           = 106 PRB (≈40 MHz) / 51 PRB / 273 PRB
ul_frequencyBand              = 78
ul_carrierBandwidth           = 106
initialDL/ULBWPlocationAndBandwidth = 28875
ssb_PositionsInBurst_Bitmap   = 1
ssb_periodicityServingCell    = 2                 # ms20
referenceSubcarrierSpacing    = 1
dmrs_TypeA_Position           = 0                 # pos2
```

### C. TDD pattern
```libconfig
dl_UL_TransmissionPeriodicity = 6                 # 5 ms
nrofDownlinkSlots             = 7
nrofDownlinkSymbols           = 6
nrofUplinkSlots               = 2
nrofUplinkSymbols             = 4
```

### D. 隨機接取(PRACH / RACH)
```libconfig
prach_ConfigurationIndex                  = 98
prach_msg1_FDM                            = 0    # one occasion
prach_msg1_FrequencyStart                 = 0
zeroCorrelationZoneConfig                 = 12/13
preambleReceivedTargetPower               = -104 / -96   # dBm
preambleTransMax                          = 6
powerRampingStep                          = 1    # 2 dB
ssb_perRACH_OccasionAndCB_PreamblesPerSSB_PR = 4
ssb_perRACH_OccasionAndCB_PreamblesPerSSB    = 14 / 15
ra_ContentionResolutionTimer              = 7    # 64 ms
rsrp_ThresholdSSB                         = 19
prach_RootSequenceIndex(_PR)              = 1 / 2
msg1_SubcarrierSpacing                    = 1
restrictedSetConfig                       = 0
msg3_DeltaPreamble                        = 1
```

### E. 功率與天線(Power / Antenna)
```libconfig
pMax                              = 20            # dBm,UE 最大上行
preambleReceivedTargetPower       = -104 / -96
p0_NominalWithGrant / p0_nominal  = -90
ssPBCH_BlockPower                 = -25           # SSB EPRE 參考點
max_pdschReferenceSignalPower     = -27           # PDSCH RS 功率
max_rxgain                        = 75 / 114      # USRP 接收增益
nb_tx, nb_rx                      = 1, 1          # 多為 SISO;n310 範例 2x2/4x4
att_tx, att_rx                    = 0
```

### F. PUCCH / Scheduler
```libconfig
pucchGroupHopping        = 0
hoppingId                = 40
pusch_TargetSNRx10       = 200                    # 即 20 dB
pucch_TargetSNRx10       = 200 / 230
prach_dtx_threshold      = 100 / 200
pucch0_dtx_threshold     = 10
max_ldpc_iterations      = 20
min_rxtxtime             = 6
ofdm_offset_divisor      = 8
sl_ahead                 = 3
```

### G. 量測事件與鄰區(Mobility / Measurement)— xApp HO 核心
```libconfig
# neighbour-config.conf
neighbour_list = (
  { nr_cellid = 0;
    neighbour_cell_configuration = ({
      gNB_ID=0xb00, nr_cellid=1, physical_cellId=1,
      absoluteFrequencySSB=621312, band=78, subcarrierSpacing=1,
      plmn={mcc=208;mnc=99;mnc_length=2}, tracking_area_code=1 }) },
  { nr_cellid = 1;
    neighbour_cell_configuration = ({
      gNB_ID=0xe00, nr_cellid=0, physical_cellId=0,
      absoluteFrequencySSB=641280, band=78, ... }) }
);

nr_measurement_configuration = {
  Periodical = { enable=1; includeBeamMeasurements=1; maxNrofRS_IndexesToReport=4 };
  A2         = { enable=1; threshold=60 (或110); timeToTrigger=1 };  # serving 低於門檻
  A3         = ({ physCellId=-1; offset=10; hysteresis=0; timeToTrigger=1 },
                { physCellId=2;  offset=5;  hysteresis=1; timeToTrigger=2 });
};
```

### H. 介面 / 網路(F1 / E1 / N2 / N3 / SCTP)
```libconfig
SCTP            = { SCTP_INSTREAMS=2; SCTP_OUTSTREAMS=2 };
amf_ip_address  = ({ ipv4 = "192.168.71.132" });
NETWORK_INTERFACES = {
  GNB_IPV4_ADDRESS_FOR_NG_AMF = "192.168.71.140";
  GNB_IPV4_ADDRESS_FOR_NGU    = "192.168.71.140";
  GNB_PORT_FOR_S1U            = 2152;
};
# F1 (CU↔DU)
local_s_address / remote_s_address  + local_s_portd = 2153    # F1-C
local_n_portd   = 2154; remote_n_portd = 2153                 # F1-U (MAC-DU)
# E1 (CU-CP↔CU-UP)
E1_INTERFACE = ({ type="cp"; ipv4_cucp="..."; port_cucp=38462;
                  ipv4_cuup="0.0.0.0"; port_cuup=38462 });
```

### I. 安全(NAS/AS Security)
```libconfig
ciphering_algorithms = ("nea2","nea0")            # 或 ("nea0")
integrity_algorithms = ("nia2","nia0")
drb_ciphering = "yes"
drb_integrity = "no" (gNB 預設) / "yes" (HO CU)
```

### J. UE 側
```libconfig
uicc0 = { imsi="208990100001100"; key=...; opc=...; dnn="oai"; nssai_sst=1 };
position0 = { x=0; y=0; z=6377900 };              # 地心座標 ≈ 地表 (0,0,0)
thread-pool = "-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1";
channelmod = {                                     # 僅 rfsimulator 通道模式使用
  modellist = "modellist_rfsimu_1";
  rfsimu_channel_enB0 = { type=AWGN; ploss_dB=20; noise_power_dB=-4; ds_tdl=0 };
  rfsimu_channel_ue0  = { type=AWGN; ploss_dB=20; noise_power_dB=-2; ds_tdl=0 };
};
```

### K. Log(僅運維、不影響行為)
```libconfig
log_config = { global=info; phy/mac/rlc/pdcp/rrc=info; f1ap/ngap=debug };
```

---

## 2. 對 AODT 數位雙生的影響評估

依「該設定是否會改變 Sionna RT 場景裡的射頻幾何 / 通道 / HO 決策」分四級。

### ★★★ 高影響(必須與雙生場景一致,否則覆蓋圖 / HO 全錯)

| 設定 | 為何重要 |
|---|---|
| `absoluteFrequencySSB`, `dl/ul_frequencyBand` | RT 的 path loss、穿透、繞射全部頻率相關;n77 vs n78 結果就會差。 |
| `dl_carrierBandwidth` (PRB) + `subcarrierSpacing` | 決定 Sionna 算 channel 時的子載波解析度、coherence BW、總可用功率譜密度。 |
| `ssPBCH_BlockPower`, `max_pdschReferenceSignalPower` | UE RSRP 的「絕對位準」就是用這個算出來的;雙生跑 A3/A2 量測唯一的功率參考點。 |
| `nb_tx`, `nb_rx`(MIMO 階) | 直接決定 RT 要不要把多天線 ray traced channel 攤開,影響 SINR / 吞吐預測。 |
| `physCellId`, `nr_cellid` | UE 報的 measurement 是用 PCI 標的;PCI conflict 時雙生 HO 完全混亂。 |
| `neighbour_list` 整段 | 沒列進來的 cell,UE 根本不會量;雙生內就算射線可達也不會觸發 HO。 |
| `A3 offset / hysteresis / timeToTrigger`、`A2 threshold` | 就是 xApp 想驗證的 HO 觸發條件本身,等於實驗變因。 |
| gNB 位置 / 朝向(在 OAI conf 裡沒有,要在 AODT scene 對齊) | RT 幾何來源 |

### ★★ 中等影響(雙生需匹配,但容差較大)

| 設定 | 影響 |
|---|---|
| `pMax`, `p0_NominalWithGrant`, `p0_nominal` | 上行功率控制 → UL SINR 與 RACH 成功率;對 HO 觸發影響較間接。 |
| `ssb_periodicityServingCell`(預設 20 ms) | 量測週期下限;HO 反應時間軸的最小粒度。 |
| `dl_UL_TransmissionPeriodicity` + DL/UL slot 配置 | TDD pattern 決定每秒可量測 / 可回報的 slot 數,影響 HO 延遲分布,不影響 RSRP 數值。 |
| `rsrp_ThresholdSSB`、PRACH 門檻 | 接取邊界 → 覆蓋邊緣 UE 能否 attach,間接影響 HO 場景能否成立。 |
| UE `position0` | rfsim 模式才會用;若改走 AODT/Sionna 通道注入,會被覆蓋。 |

### ★ 低影響(對雙生本身幾乎無影響,但跑得起來才有意義)

| 設定 | 說明 |
|---|---|
| `SCTP_INSTREAMS / OUTSTREAMS`, F1/E1/NGAP IP & port | 只決定 OAI 進程間連線能否建立,跟 RF 無關。 |
| `ciphering_algorithms` / `integrity_algorithms` | NAS/AS 加密選擇,不影響量測值。 |
| `log_config`, `Asn1_verbosity` | 純除錯。 |
| `pucchGroupHopping`, `hoppingId`, `prach_RootSequenceIndex` | 物理層序列;只要兩端一致就好,RT 不用感知。 |
| `IMSI / key / opc / dnn` | 鑑權設定,雙生看不到。 |

### ⚠ 與雙生需「同步對齊」的清單(實作上最容易踩坑)

1. **頻率三件套**:`absoluteFrequencySSB` ↔ Sionna `frequency` ↔ AODT scene carrier frequency。
   OAI 的 ARFCN→Hz 換算錯一次,RSRP 全錯。
2. **天線增益基準**:OAI 用 `ssPBCH_BlockPower=-25 dBm` 當 SSB EPRE;Sionna 預設用 dBm/Hz 的 Tx power。
   要先做 EPRE→總功率換算,否則 RSRP 會差好幾 dB。
3. **PCI ↔ AODT cell 物件**:`neighbour_list.physical_cellId` 必須與 AODT 場景內 BS 物件的 PCI 屬性一一對齊,
   否則 xApp 的 measurement report 解析不到鄰區。
4. **A3 參數單位**:offset 用 0.5 dB 為單位(OAI 內部),hysteresis 同單位,雙生跑統計時要換算。
5. **`channelmod` 區塊**:走 AODT/Sionna 注入通道時,**必須關掉**或讓 rfsim AWGN model 失效,
   否則會疊兩層 path loss。

---

## 3. 結論

OAI 配置裡真正會「灌進」AODT/Sionna 雙生回路的只有以下 7 類:

1. 頻率(`absoluteFrequencySSB` / `frequencyBand`)
2. 頻寬(`carrierBandwidth` PRB)
3. SSB / PDSCH 功率(`ssPBCH_BlockPower`、`max_pdschReferenceSignalPower`)
4. 天線數(`nb_tx`、`nb_rx`)
5. PCI(`physCellId`)
6. 鄰區表(`neighbour_list`)
7. 量測事件(`A2 threshold`、`A3 offset/hysteresis/TTT`)

其餘 PRACH / PUCCH 序列、SCTP、F1/E1/NGAP、security、log、UICC 多屬 RAN 內部運作參數,
只要兩端一致即可,對雙生的射頻幾何沒有意義 — 但若忽略上述 7 類任一項,xApp HO 驗證會直接失準。

---

## 4. 給 XAPP_DT 的後續行動建議

- 在 `scene_config.json` 或 AODT 場景元件中,把每個 BS 物件加上 `pci`、`nr_cellid`、`absoluteFrequencySSB`、`tx_power_dBm`、`nb_tx/nb_rx` 欄位,直接對應 OAI conf。
- 在 Sionna 餵 RAN 之前,實作 `oai_to_sionna.py` 做以下轉換:
  - ARFCN → Hz
  - `ssPBCH_BlockPower` (EPRE/15kHz subcarrier) → SSB 總功率 (over 240 subcarriers × 4 OFDM symbols)
  - `dl_carrierBandwidth` PRB → channel BW Hz(× SCS × 12)
- 在 RANsim-CU 啟動腳本中強制檢查 `neighbour_list` 的 PCI 集合 ⊆ 場景內 BS PCI 集合,缺一個就告警(避免 HO 報告找不到對應 cell)。
- 將 `nr_measurement_configuration` 視為實驗變因,放進 xApp 驗證 matrix(offset / hysteresis / TTT 三維 sweep),其他 RAN 設定保持固定。
