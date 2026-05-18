# 實體 OAI → XAPP_DT 對接 — 欄位需求清單(精簡版)

> 產出日期:2026-05-15
> 對象:準備從實體 OAI gNB / CU / DU 拿設定,灌進 XAPP_DT 雙生平台
> 範圍:**只列 XAPP_DT 真正會用上的欄位**;OAI 上的 PRACH / PUCCH 序列 / TDD slot 細部 / 安全演算法 / F1 port 等,平台不模也不打算模,**不在此清單**。
> 排除:A2 事件、方向性/per-PCI 鄰區(平台目前未實作)。

---

## A. 場景設定需求(每換場景 / 每跑新實驗都要要)

> 這些欄位**直接灌進 `scene_config.json` 或透過 HTTP API 推送**,平台支援 runtime 熱調。

### A.1 gNB 物理擺放(每站一份)

| 欄位 | OAI 對應 | XAPP_DT 落點 | 必要 |
|---|---|---|---|
| 站台識別字串 | `gNB_name` | `scene_config.gnbs[].name` | ✅ |
| 場景內座標 [x,y,z] (m) | (站台規劃資料) | `scene_config.gnbs[].position` | ✅ |
| 天線高度 (m) | (規劃資料) | 併入 position.z | ✅ |
| 天線朝向 azimuth (deg) | (規劃資料) | `scene_config.gnbs[].cells[].azimuth_deg` | ✅ |
| Downtilt (deg) | (規劃資料) | 併入 antenna pattern | ⭐選 |

### A.2 載波 / Cell 參數(每個 sector 一份)

| 欄位 | OAI 對應 | XAPP_DT 落點 | 必要 |
|---|---|---|---|
| PCI (0–1007) | `physCellId` | `scene_config.gnbs[].cells[].pci` | ✅ |
| 全域 cell ID | `nr_cellid` | `scene_config.gnbs[].cells[].cell_id` | ✅ |
| 載波頻率 (GHz) | `absoluteFrequencySSB` (要 ARFCN→Hz 換算) | `scene_config.gnbs[].frequency_ghz` | ✅ |
| 頻段標記 (n77/n78/...) | `dl_frequencyBand` | 記錄用 | ✅ |
| 頻寬 (MHz) | `dl_carrierBandwidth × SCS × 12 / 1000` | `scene_config.gnbs[].bandwidth_mhz` | ✅ |
| Tx EIRP 上限 (dBm) | `ssPBCH_BlockPower + antenna gain` 總和 | `scene_config.gnbs[].power_dbm` | ✅ |
| 天線陣列 rows × cols | `nb_tx × nb_rx`(配合 pol) | `RU/update_antenna.rows / cols` | ✅ |
| 極化 polarization | (從 nb_tx 配置推) | `RU/update_antenna.polarization` | ✅ |
| Antenna pattern | (OAI 不指定,TR 38.901 默認) | `RU/update_antenna.pattern`(預設 `tr38901`) | ⭐選 |

### A.3 鄰區關係(粗顆粒版)

| 欄位 | 說明 | XAPP_DT 落點 |
|---|---|---|
| 哪幾個 gNB 互為鄰區 | 列舉清單即可,雙向自動成立 | `scene_config.gnbs[].active=true`;active 的 cell 自動互為鄰區 |

> ⚠ **暫不支援(平台未實作)**:
> - 不對稱鄰區(A→B 但不 B→A)
> - per-PCI A3 offset(對不同鄰居設不同門檻)
>
> 若 OAI 端 `neighbour_list` 用了 per-PCI A3 list,目前只能取「整體 A3 平均值」灌進去。

### A.4 量測事件(實驗變因,跑 sweep 時動)

| 欄位 | OAI 對應 | XAPP_DT 落點 | 必要 |
|---|---|---|---|
| A3 offset (dB) | `nr_measurement_configuration.A3.offset` | `CU/Mobility/A3Controller/set.offset_db` | ✅ |
| A3 hysteresis (dB) | `nr_measurement_configuration.A3.hysteresis` | `.hys_db` | ✅ |
| A3 TimeToTrigger (ms) | `nr_measurement_configuration.A3.timeToTrigger` | `.ttt_ms` | ✅ |
| ~~A2 threshold / TTT~~ | `nr_measurement_configuration.A2.*` | **平台未實作,先 skip** | ❌ |

### A.5 UE 屬性(要驗證真實 UE 時)

| 欄位 | OAI 對應 | XAPP_DT 落點 | 必要 |
|---|---|---|---|
| IMSI | `uicc0.imsi` | `scene_config.ues[].imsi`(若需可加 schema) | ✅ |
| 起始位置 [x,y,z] | (規劃資料) | `scene_config.ues[].position` | ✅ |
| 移動軌跡 + 速度 | (測試案規劃) | `scene_config.ues[].waypoints` + `speed_mps` | ✅ |
| Traffic profile (Mbps + 5QI) | (用例規劃) | `CU/Session/update_traffic_profile` | ✅ |
| Key / OPc / DNN / NSSAI | `uicc0.*` | (僅接真 CN5G 時用,雙生 RT 不必要) | ⭐選 |

---

## B. OAI 內部固定設定(部署期填一次,跑實驗時不動)

> 這些寫進 `docker-compose.yml`,**改完要重啟對應 container**。整個營運商週期填一次即可。

### B.1 網路識別

| 欄位 | OAI 對應 | XAPP_DT 落點 |
|---|---|---|
| MCC | `plmn_list.mcc` | `compose: PLMN_MCC`(CU + DU 兩處要一致) |
| MNC | `plmn_list.mnc` | `compose: PLMN_MNC` |
| MNC length | `plmn_list.mnc_length` | (平台 hardcode=2;若不同需改程式) |
| TAC | `tracking_area_code` | (平台 hardcode=1;若不同需加 env) |
| gNB_ID (hex) | `gNB_ID` | `compose: GNB_ID_HEX` |
| gNB_ID length (bit) | `gNB_ID_LENGTH` | `compose: GNB_ID_LENGTH=22` |

### B.2 RIC / E2 對接

| 欄位 | OAI 對應 | XAPP_DT 落點 |
|---|---|---|
| KPM RAN Function ID | (OAI flexric 預設 2) | `compose: RAN_FUNC_ID_KPM=2` |
| RC RAN Function ID | (OAI flexric 預設 3) | `compose: RAN_FUNC_ID_RC=3` |
| RIC E2TERM host:port | OAI 端 flexric / RIC 位址 | `compose(e2adapter): RIC_E2TERM_HOST / PORT`(目前 `10.3.0.71:36422`) |
| SCTP bind IP | 主機網卡 IP | `.env: SERVER_IP`(目前 `10.3.0.217`) |

### B.3 RU Link Budget(對齊真實 RF 的關鍵)

> ⚠ 目前 **env-only 冷調**,改完要重啟 RU container。後續建議升 HTTP API 熱調。

| 欄位 | OAI / 規格來源 | XAPP_DT 落點 |
|---|---|---|
| gNB Tx 功率上限 (dBm) | `ssPBCH_BlockPower`(per RE,要乘 RE 數換算總功率) | `compose(ru): RU_TX_POWER_DBM`(預設 43) |
| 天線增益 (dBi) | 站台規格書(TR 38.901 預設 14 dBi) | `compose(ru): RU_ANTENNA_GAIN_DBI=14` |
| 場景校準 loss (dB) | (Sionna RT 場景與真實之間的偏差校準) | `compose(ru): RU_SCENE_CALIBRATION_LOSS_DB=50` |
| Noise floor (dBm) | 規格推算 `-174 + 10·log10(BW) + NF` | `compose(ru): RU_NOISE_FLOOR_DBM=-95` |

### B.4 Sim Tick / KPM 報告節奏

> 影響「實驗速度 vs 量測解析度」的權衡。

| 欄位 | 用途 | XAPP_DT 落點 |
|---|---|---|
| Sim tick 週期 (ms) | DU 主迴圈節拍 | `compose(du): SIM_TICK_MS=50` |
| PM window (s) | KPM 累加視窗(= 1 / KPM rate) | `compose(du): PM_WINDOW_SEC=1.0` |
| UE 量測週期 (ms) | UE measurement report 出現頻率 | `compose(ue): UE_MEASUREMENT_PERIOD_MS=80` |
| UE 軌跡更新 (ms) | UE 位置插值週期 | `compose(ue): UE_TRAJECTORY_PERIOD_MS=100` |
| Channel cache TTL (s) | RU 對同 UE 位置 cache 多久 | `compose(ru): RU_CHANNEL_CACHE_TTL_SEC=0.5` |
| Numerology μ | (對應 OAI `subcarrierSpacing`,平台只用來標記,不模 OFDM slot) | `compose(ru): RU_NUMEROLOGY=1` |

> 🔧 設值時的兩個硬性檢查:
> 1. `UE_MEASUREMENT_PERIOD_MS ≤ HO_TTT_MS` — 否則 TTT 內取不到樣
> 2. `PM_WINDOW_SEC × 1000 / SIM_TICK_MS` 必須是整數(平台自動算)

---

## C. 不在此清單的 OAI 欄位(歸檔即可,**不必填**)

下列 OAI 設定 XAPP_DT **不模也不打算模**,跟 OAI 端要回來只是歸檔對齊用,不會進任何 env / config / API:

- **PRACH / 隨機接取全段**(`prach_ConfigurationIndex`、`preambleReceivedTargetPower`、`preambleTransMax`、`powerRampingStep`、`ra_ContentionResolutionTimer`、`prach_RootSequenceIndex`、`zeroCorrelationZoneConfig`、`rsrp_ThresholdSSB`)
  → 平台假設 UE 一直已連線,不模 RACH;non-contention HO 也不走 PRACH。

- **PUCCH 物理層序列**(`pucchGroupHopping`、`hoppingId`)
  → 純 sequence ID,Sionna RT 不感知。

- **上行功控與 SNR target**(`p0_nominal`、`p0_NominalWithGrant`、`pMax`、`pusch_TargetSNRx10`、`pucch_TargetSNRx10`、`prach_dtx_threshold`)
  → 平台只模 DL HO 用的 RSRP;UL 功控不參與決策。

- **TDD slot 細部**(`dl_UL_TransmissionPeriodicity`、`nrofDownlinkSlots / Symbols`、`nrofUplinkSlots / Symbols`、`referenceSubcarrierSpacing`)
  → 平台 tick 模型已抽象掉 OFDM slot;只要 DL:UL 比例大致一致即可。

- **SSB / DMRS 時序**(`ssb_periodicityServingCell`、`ssb_PositionsInBurst_Bitmap`、`ssb_perRACH_*`、`dmrs_TypeA_Position`)
  → 不模 SSB burst,RSRP 從 path gain 直算。

- **Security**(`ciphering_algorithms`、`integrity_algorithms`、`drb_ciphering`、`drb_integrity`)
  → 不影響任何 KPM。

- **F1 / E1 / NGAP / GTP-U port 與 IP**(`local_s_portd=2153`、`local_n_portd=2154`、`E1_INTERFACE.port_cucp=38462`、`GNB_PORT_FOR_S1U=2152`、`amf_ip_address`、`SCTP_INSTREAMS / OUTSTREAMS`)
  → 平台內部走 HTTP;只有 E2Adapter 那層才走真 SCTP(已在 B.2)。

- **S-NSSAI**(`snssaiList.sst / sd`)
  → CN5G 用,平台不檢查。

- **CU split mode**(`HTTP_CUUP_HOST`,OAI `gnb-cucp` + `gnb-cuup` 拆分)
  → 平台預設 integrated,接 OAI 時也不影響 RT。

→ **建議做法**:把 OAI conf 整份存一份檔案在 `docs/init_setting/oai_reference_<site>.conf`,以便日後出現「灌入後 KPM 異常」時可回查,但**不要為它們開 env 或寫程式**。

---

## D. minimal payload(可直接給 OAI 端的精簡 YAML 樣板)

### 場景(A 區塊)
```yaml
# 每個 gNB 一份
- name: gnb1
  position: [x, y, z]              # m
  cells:                            # 每個 sector 一份
    - pci: 100
      cell_id: gnb1_c0
      azimuth_deg: 0
      frequency_ghz: 3.5
      bandwidth_mhz: 100
      power_dbm: 43                 # 含天線增益後的 EIRP
  antenna:
    rows: 1, cols: 1
    polarization: V
    pattern: tr38901

# A3 sweep 變因
a3:
  offset_db: 1.0
  hys_db: 0.5
  ttt_ms: 80

# UE
- imsi: "001010000000001"
  start_pos: [x, y, z]
  waypoints: [[x,y,z], ...]
  speed_mps: 5
  traffic_mbps: 10
  qos_5qi: 9
```

### OAI 全域(B 區塊,一次性)
```yaml
# B.1 網路識別
plmn:
  mcc: "208"
  mnc: "95"
  mnc_length: 2
gnb_id_hex: "0x000038"
gnb_id_length: 22
tracking_area_code: 1

# B.2 RIC / E2
ran_func_id_kpm: 2
ran_func_id_rc: 3
ric_e2term: "10.3.0.71:36422"
sctp_bind_ip: "10.3.0.217"

# B.3 RU link budget
ru_tx_power_dbm: 43
ru_antenna_gain_dbi: 14
ru_scene_calibration_loss_db: 50
ru_noise_floor_dbm: -95

# B.4 Sim tick / KPM
sim_tick_ms: 50
pm_window_sec: 1.0
ue_measurement_period_ms: 80
ue_trajectory_period_ms: 100
ru_channel_cache_ttl_sec: 0.5
numerology: 1                       # 30 kHz SCS,標記用
```

---

## E. 對齊 checklist(填完後驗收)

```
場景(A 區塊)
[ ] 每個 gNB 都填了 position + power + freq + bw
[ ] 每個 cell 都有不重複的 PCI(全平台 PCI 集合無衝突)
[ ] A3 三件套(offset / hys / TTT)有明確值
[ ] UE 軌跡 + traffic 有明確值

OAI 全域(B 區塊)
[ ] B.1 PLMN + gNB_ID 跟 OAI 一致
[ ] B.2 RIC e2term 位址可達(可 SCTP test)
[ ] B.3 RU link budget 4 個常數有「來源依據」(OAI ssPBCH_BlockPower 推算或實測)
[ ] B.4 `UE_MEASUREMENT_PERIOD_MS ≤ HO_TTT_MS`(否則 HO 永遠不會觸發)

OAI 端宣告
[ ] OAI 端是否使用 A2 → 若有,告知 XAPP_DT 待補實作
[ ] OAI 端是否使用方向性鄰區或 per-PCI A3 list → 若有,告知 XAPP_DT 待補實作
[ ] OAI 完整 conf 副本已歸檔到 `docs/init_setting/oai_reference_<site>.conf`
```

---

*用法:把這份直接 e-mail 給 OAI 站台規劃 / 維運方,A 區塊每個實驗回合都重新要一份,B 區塊整個部署期填一次即可。C 區塊的欄位只要他們把整份 conf 給我們存檔即可,不需要逐項填表。*
