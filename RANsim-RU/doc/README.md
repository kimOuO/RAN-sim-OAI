# RANsim-RU — O-RU

## 系統用途
5G NR **無線單元(O-RU)**,埠 `:8103`。負責天線/波束成形、SINR/CQI 估計、以及 DL/UL TTI pipeline;向 Physics(Sionna)取 path_gain(或讀 cached npz)算真實多 cell 干擾下的 SINR,回 CQI/CRC 給 DU。
↔ OAI:`nr_ru_procedures.c::ru_thread()`、`nr_modulation.c`(codebook)、`nr_ru_timing.c`。

## 模組(Django apps,`main/apps/`)
| 模組 | 路徑 | 功能 | 對應 OAI |
|---|---|---|---|
| `fapi_south` | `main/apps/fapi_south` | DL/UL TTI pipeline、真實多cell干擾、SINR→CQI/CRC、live/cached、inter_freq | ru_thread() |
| `beamforming` | `main/apps/beamforming` | 38.211 Type I codebook、PMI、precoder、SINR/rank/CQI 估計(內部用) | nr_modulation.c |
| `antenna` | `main/apps/antenna` | 天線陣列/cell/UE 位置 DB + RuController 配置 API | PHY/MODULATION/antenna.c |
| `physics_client` | `main/apps/physics_client` | 組 PathSolverRequest 打 Physics + L2 cache | RU→物理引擎 |
| `phy_low` | `main/apps/phy_low` | RU state(SFN/slot/numerology/FFT/CP)、OFDM 描述 | nr_ru_timing.c |

## API(全部 POST)

### Config/RuController(`/api/v0.1/RU/Config/`)
| 端點 | 說明 |
|---|---|
| `RuController/update_antenna` | 更新天線設定 |
| `RuController/update_cells` | 更新 cell 清單 |
| `RuController/update_ues` | 更新 UE 位置(批次) |
| `RuController/set_channel_mode` | 設 channel 模式(live / cached) |
| `RuController/set_inter_freq` | 設 inter-frequency(關互擾) |

### FAPI / State / Physics
| 端點 | 說明 |
|---|---|
| `RU/FAPI/FapiRouter/dl_tti_request` | 處理下行 slot(算 SINR→CQI) |
| `RU/FAPI/FapiRouter/ul_tti_request` | 處理上行 slot(CRC) |
| `RU/State/RuStateReader/read` | 讀 RU state 快照 |
| `RU/Physics/PhysicsHealth/read` | 讀 Physics 健康狀態 |

> `beamforming` 無對外端點(內部計算用)。平台架構見 [`docs/architecture/`](../../docs/architecture/dt_ran_architecture.md)。
