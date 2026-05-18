# OAI conf ↔ XAPP_DT 對齊報告(A/B 分區版)

> 產出日期: 2026-05-16
> 來源:
> - OAI: `gnb-cu.sa.f1.conf`、`gnb-du.sa.band78.106prb.rfsim.pci0.conf`、`gnb-du.sa.band78.106prb.rfsim.pci1.conf`
> - XAPP_DT: `ran_init_required_settings.md`、`docker-compose.yml`、`scene_config.json`、`ran-sim-protocol` DTO

---

## TL;DR

把對齊狀況依「**場景**(A)/ **OAI 內部**(B)」拆兩半看,結論很清楚:

| 區塊 | 結構上有沒有對應入口? | 值對不對? | 結論 |
|---|---|---|---|
| **B. OAI 內部調整參數** | ✅ 幾乎都有 env / DTO 接口 | ⚠ 有 3 個欄位「值對不上」(可直接改設定即修) | **基本上設定好了**,只剩值校準 |
| **A. 場景情境建設** | ⚠ 有 5 類結構性缺口(無接口、OAI conf 本來就不帶) | — | **還沒到位**,要場勘 + 補檔 + 加 API |

→ 接下來的火力應該全部放在 **A. 場景情境建設**,B 區只是收尾。

---

## A. 場景情境設定(per-scenario)— 還沒到位

### A.1 對齊明細

| 場景欄位(XAPP_DT) | OAI 對應 | OAI 值 | 場景現值 | 狀態 |
|---|---|---|---|---|
| `gnbs[].position` (XYZ) | — | ❌ conf 不帶 | NW/SE/Central 三站 | 結構性缺:OAI 不給,要勘測 |
| `gnbs[].cells[].azimuth_deg` | — | ❌ conf 不帶 | 0 / 120 / 240 | 同上 |
| `gnbs[].frequency_ghz` | `absoluteFrequencySSB` | DU0=3450.72 / DU1=3649.44 MHz | 3.5 / 3.5 / 2.6 GHz | ⚠ OAI 都 n78,場景有 2.6 GHz Micro |
| `gnbs[].bandwidth_mhz` | `dl_carrierBandwidth=106 PRB @ 30 kHz` | 40 MHz × 2 | 100 / 100 / 20 MHz | ⚠ 不齊 |
| `gnbs[].power_dbm` | `ssPBCH_BlockPower` + gain | -25 dBm (per-RE) | 43 / 40 / 20 dBm | ⚠ 口徑不同 |
| `gnbs[].cells[].pci` | `physCellId` | {0, 1} 共 2 個 | {100..302} 共 9 個 | ⚠ 數量 + 範圍全不同 |
| `gnbs[].cells[].cell_id` | `nr_cellid` (int) | 12345678 / 11111111 | `gnb1_cell0`(字串) | ⚠ 格式需 map |
| 鄰區關係 | `neighbour_list` | ❌ 三份 conf 沒給 | 隱式(全 active 互鄰) | 結構性缺:無方向性 / per-PCI 接口 |
| A3 offset/hyst/TTT | `nr_measurement_configuration.A3` | ❌ 三份 conf 沒給 | 0.5 / 0.3 / 60 ms | 需要 OAI `neighbour-config.conf` 對齊 |
| A2 RSRP threshold | `nr_measurement_configuration.A2` | ❌ 三份 conf 沒給 | **平台未實作** | 結構性缺:沒入口 |
| `ues[].waypoints/speed` | (在 `nrue.uicc.conf`) | ❌ 不在 gNB conf | 5 個 UE | 由 UE 端 conf 出 |

### A.2 結構性缺口(5 類,要動程式碼/補檔/勘測才補得齊)

1. **gNB / cell 物理屬性(XYZ + azimuth + tilt)**
   - 實體 OAI conf 本來就不帶,要現場勘測表 / RAN deployment plan
   - 對應記憶 [[brownstone_asset_resolution]]:asset 與設定不一致會悄悄失敗

2. **拓樸不對等(2 vs 9 cell)**
   - OAI: 1 CU + 2 DU = 2 cell(PCI 0, 1, n78 ~3.45/3.65 GHz, 40 MHz)
   - XAPP_DT: 3 gNB × 3 sector = 9 cell(異頻 3.5/2.6 GHz, 100/20 MHz)
   - 三條路徑:
     - **A 路:縮 scene**(改成 2 cell,PCI 改 0/1)— 適合先做煙霧測試
     - **B 路:擴 OAI**(再起 7 份 du.conf,異頻多 carrier)— 真正做 9-cell HO 驗證
     - **C 路:純 DT,不接 rfsim**(維持 scene 9 cell,xApp 走 XAPP_DT e2adapter)

3. **`neighbour-config.conf` 沒拿到**
   - 三份 conf 都沒帶鄰區表,XAPP_DT 目前用「全 active cell 互為鄰」的隱式策略
   - 真實 OAI 用 `neighbour_list` 顯式定義方向性鄰區
   - **要回頭跟 OAI 端要 `ci-scripts/conf_files/neighbour-config.conf`**

4. **A2 事件完全沒模**
   - 平台只有 A3,沒有 A2(離開門檻 / 弱訊號上報)
   - 若 OAI 真實 case 有用 A2 → XAPP_DT 必須補 A2 偵測邏輯到 CU,**目前無入口**

5. **EIRP 口徑反算**
   - OAI 的 `ssPBCH_BlockPower=-25 dBm` 是 per-RE,真 EIRP 要加 antenna gain 與 PA 增益
   - 需要 RU 機種 / antenna datasheet → 才能推出 `RU_TX_POWER_DBM` + `RU_ANTENNA_GAIN_DBI` 真值
   - 推出來後,scene_config.gnbs[].power_dbm 也要一起改

### A.3 場景區待辦清單

```
[ ] 跟 OAI 端要 gNB / cell 的 XYZ + azimuth(現場勘測表)
[ ] 跟 OAI 端要 neighbour-config.conf(鄰區 + A3 + A2)
[ ] 跟 OAI 端要 antenna datasheet + 實際 EIRP(dBm)
[ ] 決定走哪條路徑(縮 scene / 擴 OAI / 純 DT)
[ ] 建立 nr_cellid(int)↔ platform cell_id(str)的 map 表
[ ] (可選)若 OAI 有用 A2 → 在 CU 端補 A2 觸發邏輯與 env
```

---

## B. OAI 內部調整參數(one-time)— 基本上設定好了

### B.1 對齊明細

✅ = 結構 & 值都對 / ⚠ = 結構在但值要改 / ➖ = DT 內部選不必對齊

| OAI 內部欄位(XAPP_DT) | XAPP_DT 現值 | OAI conf 值 | 狀態 |
|---|---|---|---|
| `PLMN_MCC` / `PLMN_MNC` | "208" / "95" | mcc=208, mnc=95 | ✅ |
| `GNB_ID_HEX` | "0x000038" (= 56) | `gNB_ID` = **0xe00** (= 3584) | ⚠ 改值即可 |
| `GNB_ID_LENGTH` | 22 | 0xe00 需 12-bit 才裝得下 | ⚠ 改值即可 |
| `RIC_E2TERM_HOST` / `PORT` | **10.3.0.71** / 36422 | `e2_agent.near_ric_ip_addr` = **10.3.0.204** | ⚠ 改值即可 |
| `RAN_FUNC_ID_KPM` / `RC` | 2 / 3 | flexric 內建(conf 沒寫) | ✅(對齊 flexric 預設) |
| TAC | (XAPP_DT 沒列) | `tracking_area_code` = 0xa000 | ⚠ 補欄位即可 |
| SST(slice) | (XAPP_DT 沒列) | `snssaiList.sst` = 1 | ⚠ 補欄位即可 |
| `served_plmn`(DTO 預設) | `"00101"` | mcc=208, mnc=95 | ⚠ DTO 預設改 `"20895"` |
| `RU_TX_POWER_DBM` | 43.0 | (推自 `ssPBCH_BlockPower` + gain) | ⚠ 值要按 A.2-5 反算 |
| `RU_ANTENNA_GAIN_DBI` | 14.0 | ❌ datasheet 才有 | 值要按 A.2-5 反算 |
| `RU_SCENE_CALIBRATION_LOSS_DB` | 50.0 | ❌ DT 內部校準 | ➖ |
| `RU_NOISE_FLOOR_DBM` | -95 | ❌ DT 內部 | ➖ |
| `RU_DEFAULT_ANTENNA_ROWS/COLS` | 1 / 1 | `nb_tx` / `nb_rx` = 1 / 1 | ✅ |
| `RU_DEFAULT_POLARIZATION/PATTERN` | "V" / "tr38901" | ❌ 不在 conf | ➖ |
| `RU_NUMEROLOGY` | 1 | `dl_subcarrierSpacing` = 1 (30 kHz) | ✅ |
| `SIM_TICK_MS` / `PM_WINDOW_SEC` | 50 / 1.0 | ❌ sim-internal | ➖ |
| `UE_MEASUREMENT_PERIOD_MS` | 80 | ❌ 三份 conf 沒帶 | ⚠ 建議降 30–50 ms(< TTT) |

### B.2 結論

**結構上 100% 對應** — 該有的 env / DTO 接口全部都有,
**值對不上的只有 3+2 個欄位**,改設定即修(不需動程式):

| # | 欄位 | 修法 | 不修的影響 |
|---|---|---|---|
| ① | `GNB_ID_HEX` / `GNB_ID_LENGTH` | compose 改 `0x000e00` / `12` | E2 Setup `globalE2node-ID` 對不上 → 訂閱不會建立 |
| ② | `RIC_E2TERM_HOST` | 確認 RIC 實際 IP,兩邊同步 | E2 SCTP 連不上(對應記憶 [[sctp_host_reboot_wipe]]) |
| ③ | `served_plmn` DTO 預設值 | 改 `"20895"` | CellConfig 預設與真實 PLMN 對不上 |
| ④ | TAC、SST 補欄位 | compose 新增 `TAC=0xa000`、`SST=1` | NGAP 註冊用,目前用內建 mock 不會掛但接真 5GC 會掛 |
| ⑤ | RU 功率三件套 | 等 A.2-5 antenna datasheet 才能算 | Sionna RSRP 與 OAI 實量值會差 50–70 dB |

### B.3 OAI 內部區待辦清單

```
[ ] compose: GNB_ID_HEX 改 0x000e00、GNB_ID_LENGTH 改 12
[ ] compose: RIC_E2TERM_HOST 與 OAI conf 同步
[ ] ran-sim-protocol DTO: served_plmn 預設改 "20895"
[ ] compose: 新增 TAC、SST 欄位
[ ] (依賴 A.2-5)compose: RU_TX_POWER_DBM / RU_ANTENNA_GAIN_DBI 真值
[ ] compose(ue): UE_MEASUREMENT_PERIOD_MS 從 80 降到 30–50 ms
```

---

## C. 總結

```
                      結構入口      值對齊       要動什麼
────────────────────  ───────       ───────      ─────────────────────
A. 場景情境建設       ⚠ 5 類缺口    —            場勘 + 補檔 + 改程式
B. OAI 內部調整參數   ✅ 全到位     ⚠ 3+2 處     改 env / DTO 預設值
```

**判斷**: B 區只剩值校準(全部是改設定就好的工作),A 區才是真正的工作 — 拓樸選型、場勘資料、neighbour-config 補檔、(可選)A2 邏輯實作。

下一步建議:
1. 先把 B.2 的 ①②③④ 在 1 天內全部改完(純改設定)
2. 同步發信跟 OAI 端要 A.3 列的三類資料(座標表 / neighbour-config / antenna datasheet)
3. 等資料回來再做 A 區拓樸決策(縮 scene / 擴 OAI / 純 DT)

---

*本份替代原 `oai_conf_alignment_report.md` 平鋪表,採 A/B 分區呈現,直接對應 `oai_required_fields_request.md` 的「場景設定需求 / OAI 內部固定設定」雙區結構。*
