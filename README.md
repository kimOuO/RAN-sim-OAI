# XAPP_DT —— 5G NR RAN 數位孿生

用真實 3D 場景(OSM 地圖或實地掃描)算出電波傳播,驅動一套 O-RAN 網路模擬(CU / DU / RU / UE),
把量測結果以 **真實 E2 介面**送給外部 RIC,讓 xApp 可以對這個「數位孿生網路」下控制命令並看到效果。

**用途:xApp 的決策(換手、節能、波束、鄰區管理)先在數位孿生驗證,再上實體 RAN。**

新接手請從 **[`docs/architecture/reading_guide.md`](docs/architecture/reading_guide.md)** 開始,
它有模組閱讀順序、一個 tick 的資料流、名詞對照與已知的坑。

---

## 1. 系統長什麼樣

```
使用者在編輯器建場景 ──▶ 管理平台 registry(場景設定的唯一真相)
                                  │
                         編排器 orchestrator 啟動一個 run
                                  │
        ┌─────────────────────────┼──────────────────────────┐
        │                         │                          │
   UE driver                CU / DU / RU               E2 Adapter ──▶ RIC / xApp
 (推模擬時間、人流、流量)   (協定與無線模擬)            (SCTP + ASN.1)
        │                         │
        └──── Physics(Sionna RT 光線追蹤,GPU)────┘
                                  │
                        編排器歸檔 ──▶ 監控前端(即時 / 回放 / 3D)
```

### 服務一覽

| 服務 | 連接埠 | 角色 |
|---|---|---|
| `scene-management-backend` | 8301 | 管理平台:場景、網元、UE、天線 preset、run 設定 |
| `scene-editor-frontend` | 3011 | 場景建置(地圖框選 / 掃描檔上傳 → 3D 編輯 → 啟動) |
| `run-orchestrator` | 8302 | 編排器:起停 run、健康監控、遙測歸檔 |
| `run-monitor-frontend` | 3012 | 監控(唯讀):儀表板、事件流、3D 即時與回放 |
| `physics` | 8104 | Sionna RT 光線追蹤(GPU) |
| `kpm-calib` | 8200 | KPM 對 OAI 實機數據的校準 |
| `postgres` / `pgbouncer` | 5433 | 資料庫 |

**一個 run = 5 個專屬容器 + 3 個專屬資料庫**:
`cu-<rid>`、`du-<rid>`、`ru-<rid>`、`ue-<rid>`、`e2adapter-<rid>`(rid = run uuid 後 8 碼),
以及 `cu_<rid>`、`du_<rid>`、`ru_<rid>`。停止時容器移除、資料庫 drop,不留殘骸。

Physics 是共用的:多場景並行只能用 cached 模式;live 模式同時最多 1 個(GPU 要排隊)。

---

## 2. 資料庫分工

| 資料庫 | 表數 | 存什麼 |
|---|---|---|
| `scene_registry_db` | 20 | **設計值**:場景、建築、材質、gNB→DU→cell→RU、UE 路徑與流量、preset、run 設定 |
| `cu_<rid>` | 14 | **執行中狀態**:UE 連線、鄰區關係、換手 / 斷線事件、量測 |
| `du_<rid>` | 6 | 時鐘、MAC / RLC / HARQ 狀態 |
| `ru_<rid>` | 5 | cell 與天線設定、UE 位置、最後一次量測 |
| `run_orchestrator_db` | 4 | **執行後紀錄**:啟動請求、KPM 樣本、換手 / 控制事件(回放讀這份) |
| `physics_db` | 4 | 場景與設定快取 |

三條跨庫關聯(沒有外鍵,靠 ID 字串):`scene_run_uuid`、`cell_id`、`ue_id`。

**設定在 run 啟動時凍結** —— 容器啟動時拉進記憶體,run 期間改 registry 不生效,要重啟 run。

---

## 3. 一個 tick 的資料流

```
UE driver 推進模擬時間、更新 UE 位置(路徑點線性內插)
  → DU tick:RLC 緩衝 → 排程(誰拿多少 PRB)
  → DlTtiRequest 給 RU(服務 cell、劇本時鐘 scene_sim_ms、各 cell 負載)
  → RU 查通道:cached 查 npz / live 打 Physics
  → RU:重建元件層 H → 壓到埠層 → 選波束 → 選 rank/PMI → 算 SINR / RSRP / 上行 SINR
  → CqiIndication 回 DU
  → DU 查 BLER 曲線決定成敗 → 算吞吐、延遲 → 餵斷線偵測(T310)
  → DU 每秒送量測報告給 CU
  → CU:A3 換手判斷 / 斷線重建 / 產生 KPM
  → E2 Adapter 經 SCTP 送 RIC;xApp 可回送控制命令
  → 編排器歸檔 → 監控前端
```

---

## 4. 模擬到什麼程度(重要)

這是**系統層級模擬**,不是連結層級。只有「無線通道」是真的在算物理。

| 層 | 做法 |
|---|---|
| 電波傳播 | **真算**:Sionna RT 射線追蹤,直射 / 反射 / 漫反射 / 穿透 / 繞射,最多 5 次反射,ITU-R P.2040 材質 |
| 天線 | **真算**:TR 38.901 三層模型(元件 → TXRU → CSI 埠)、電子下傾、GoB 波束、TS 38.214 Type I codebook、MMSE 每層 SINR |
| 資料 | 只有「位元組數」,沒有實際酬載。RLC 的分段 / 重組 / 丟棄 / 緩衝上限都在搬數字 |
| LDPC / 調變 / OFDM / 射頻 | **不做**。改用 OAI 官方 AWGN 模擬產出的 BLER 曲線(2087 點)查表決定成敗 |
| RRC | 有狀態機與訊息型別,內容是 JSON 假裝(非 ASN.1);A3 判斷搬到 CU(真實系統在 UE) |
| F1AP / FAPI / NGAP | 借用規格的欄位語意,傳輸是 HTTP + JSON |
| **E2(對 RIC)** | **真協定**:SCTP + ASN.1 APER,規格定義檔在 `RANsim-E2Adapter/asn1/` |

### 怎麼確保接近真實
- 公式與參數取自規格:TR 38.901(天線場型、虛擬化)、TS 38.214(codebook、MCS)、TS 38.331(A3、T310)、ITU-R P.2040(材質)
- BLER 曲線、MCS 表來自 OAI 實測;KPM 有校準服務對 OAI 實機數據(例:1 Mbps 下延遲 1.17 ms、吞吐 1.04 Mbps、PRB 2.5%)
- 對照實驗:自由空間檢查、下傾角掃描、路徑參數重建 vs Sionna 完整陣列
- 端到端行為檢查:UE 是否連到最近的 cell、換手與斷線頻率、SINR 分布

---

## 5. cached 與 live

| | cached | live |
|---|---|---|
| 通道來源 | 事先算好存 npz + 路徑參數 | 每 tick 即時光追 |
| GPU | 只有預算階段 | 全程 |
| 劇本長度 | 8–24 小時可行 | 短時測試 |
| 並行 | 多個 | 最多 1 個 |

**快取存兩份東西**:`<scenario>.npz`(路徑增益)與 `<scenario>.paths/`(前 K 條路徑的振幅、極化、收發方向)。
後者讓 RU 能依當下天線重建元件層通道 —— **改陣列大小 / 波束不用重算快取,改天線場型或機械角度才要**。

---

## 6. 場景怎麼建

編輯器(:3011)四步驟：

1. **環境** —— 兩層:先選來源(從地圖建立 / 上傳掃描檔),再進 3D
   - 地圖:台灣全圖 → 搜尋地標 → 自動框範圍 → 拖拉多邊形調整 → 讀 OSM 建築 → **逐棟設材質 / 高度 / 排除** → 產生 Mitsuba 場景
   - 掃描:上傳 .glb → 自動分類材質、置中貼地 → 直接進 3D
2. **網路元件** —— 拖放 gNB / cell,貼齊地面、屋頂或掃描模型表面;設 PCI、頻率、功率、方位角、下傾、天線 preset、A3、DU 參數
3. **UE** —— 產生器(可設種子、數量、速度、停留、流量)或逐一放置;路徑、流量、在場時段
4. **啟動** —— 選 cached / live、倍速;cached 要先 precompute

---

## 7. 快速啟動

```bash
cd /home/mitlab/XAPP_DT
docker compose up -d                      # 起共用服務(registry / 編排器 / physics / 前端 / DB)

# 開編輯器建場景,或用既有場景啟動一個 run:
curl -XPOST localhost:8302/api/v0.1/Run_orchestrator/Run_lifecycle/LaunchController/start \
  -H 'Content-Type: application/json' -d '{"scene_run_uuid":"<uuid>","speed_x":2}'

# 停止(劇本跑完會自動停)
curl -XPOST localhost:8302/api/v0.1/Run_orchestrator/Run_lifecycle/LaunchController/stop \
  -H 'Content-Type: application/json' -d '{"scene_run_uuid":"<uuid>"}'
```

編輯器 http://localhost:3011 · 監控 http://localhost:3012

---

## 8. 慣例

- **所有 API 都是 POST**,路徑 `/api/v0.1/{System}/{Module}/{Controller}/{action}`,動作為 create / read / update / delete 四式加少數自訂
- **一個資料表一個檔案**,`models/` 底下的檔名就是資料表清單
- 跨系統只傳 **UUID**,外鍵欄位命名 `f_xxx_uuid`
- 協定新欄位一定要能相容舊版:預設值代表「舊版」,例如 `cell_dl_load` 空 dict = 退回滿載假設
- 平台座標 **Y 軸朝上**;Sionna 是 Z 軸朝上,轉換只在 `Physics_sim/.../ran_calculation/frame.py` 這個邊界做

---

## 9. 已知的坑(都踩過)

1. **兩個時鐘**:DU tick 早於 UE 劇本啟動,曾讓通道比 UE 位置超前 2 分鐘。查快取一律用 `scene_sim_ms`
2. **光追有雜訊**:同位置相鄰 tick 可差十幾 dB。cached 載入時平滑、live 在 RU 平滑
3. **快取缺值 ≠ 沒訊號**:短缺口內插,長缺口才當沒訊號
4. **A3 預設是關的**:劇本 JSON 沒寫 A3 欄位 → 匯入後不換手,只能等斷線重連
5. **設定凍結**:改 registry 要重啟 run
6. **路徑要兩邊一致**:registry 與 physics 都把場景檔掛在 `/app/scenes`
7. **干擾模型**:下行干擾依鄰 cell 實際 PRB 負載加權(下限 0.1);一律滿載會讓密集同頻場景長期 SINR < −6 dB

---

## 10. 目前的限制與待辦

**尚未啟用 / 驗證**
- 前端互動(地圖框選、3D 拖曳、A3 開關、DU 欄位、排程器下拉)尚未在瀏覽器實測 —— 只確認過編譯與 API
- 多埠天線 / 波束成形已在 `osm_ntust_test`(32T32R + GoB 16×4)驗證通過(陣列增益、rank 2、beam_id、
  RIC RC 2-8 控制),但走廊場景仍是單埠;MU-MIMO 尚未在完整場景觸發過
- corridor_16_24 從未跑過

**資料品質**
- 走廊場景 2026-09-19 17:00 UTC 前的 SINR / MCS / 吞吐不可用於品質評估(DU cached SINR 取到最強 cell,
  詳見 [`docs/test_records/data_quality_notice_20260919.md`](docs/test_records/data_quality_notice_20260919.md))

**已知不足**
- 下行雜訊底 −98 dBm 查不到依據(上行 −113.4 dBm/PRB 是嚴格推導);應改成依頻寬動態計算
- 光追取樣雜訊靠平滑壓住,根治要提高射線數重算
- `max_gain_dbi`、`polarization_model`、`bf_method`、`noise_figure_db` 有欄位但程式未使用
- `neighbor_seed` 表有 API 但執行期無人使用
- CU 開場偶發 `dl_rrc_message` 404(斷線 UE 的 SRB1 已清,競態)
- 走廊資料集位置每 30 s 一點且大幅來回,換手偏多

**規劃中不做**
UE 對 UE 直接干擾、上行 MIMO(rank > 1)、Type II codebook、FR2 類比波束、跨 cell 精確排程對齊、多發射點協同傳輸

完整進度與決策紀錄:[`new_plan/progress_log.md`](new_plan/progress_log.md)、[`new_plan/platform_restructure_plan.md`](new_plan/platform_restructure_plan.md)

---

## 11. 目錄

```
ran-scene-management/          管理平台(registry + 場景建置前端)
ran-emulation-runtime/
  ├─ ran-emulation-runtime-run-orchestrator/   編排器
  ├─ ran-emulation-runtime-run-monitor-frontend/ 監控前端
  ├─ ran-emulation-runtime-interface-protocol/ 共用訊息定義(FAPI / F1AP / E1AP / NGAP)
  ├─ Physics_sim/              Sionna 光追、precompute、通道快取
  ├─ RANsim-CU/                RRC、A3 換手、重建、ANR、KPM
  ├─ RANsim-DU/                tick、排程、RLC、HARQ、鏈路調適、RLF
  ├─ RANsim-RU/                通道、天線三層、波束、SINR
  ├─ RANsim-UE/                劇本載入、模擬時鐘、UE 生命週期、流量
  └─ RANsim-E2Adapter/         E2:SCTP + ASN.1(對 RIC 的唯一真協定)
docs/                          架構、ANR、KPM、MIMO、劇本、測試紀錄
new_plan/                      重構計畫與進度紀錄
Omnivers_platform/             舊的 3D 顯示平台(不在模擬主線)
```
