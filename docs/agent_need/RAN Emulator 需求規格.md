# RAN Emulator 需求規格（RAN Emulator Interface Requirements）

- 版本：v3.1（2026-09-22）｜狀態：規劃層草案，待委託者確認後交付 RAN Emulator 方。v3.1 變更（委託者 2026-09-22 裁決）。
- 對象：RAN Emulator 方（提供模擬場域、接受情境觸發並回傳觀測資料之一方）。本文件說明我方（情境與問題定義系統）如何使用 RAN Emulator、將發出之請求、每一請求期望取得之內容與建議格式。**路徑命名與內部實作由貴方決定**；本文件之路徑僅為建議，欄位名稱與結構為我方之期望，貴方得以等價結構回應，惟須能對映至本文件之欄位語意。
- 範例來源：欄位與範例值依我方現行之過渡資料格式撰寫；其中「觀測資料」之結構依先前提供之 E2 傾印範例建立，欄位名稱與貴方系統應大致相同。

---

## 壹、我方如何使用 RAN Emulator

我方系統以多個 Agent 協作產出「情境問題庫」供藍隊驗證。RAN Emulator 為情境資料之唯一來源，使用方式分兩型：

1. **類型一（固定存在之問題）**：使用者指定場域與負載型態（時段），我方觸發一段不含事件之模擬，取回該段觀測資料後由分析 Agent 判定場域固有之問題（例如同頻干擾、覆蓋不足）。此型不注入事件，問題來自貴方場域之既有配置。
2. **類型二（事件觸發之問題）**：使用者指定目標情境（例如新增 cell 後鄰區關係缺漏），我方設計最小事件集，觸發一段含事件之模擬，取回觀測資料後判定事件所致之問題；我方送出之事件清單即該情境之正確答案。

兩型之共同步驟如下（我方各步驟皆由工具模組呼叫貴方介面，Agent 不直接呼叫）：

| 步驟 | 我方動作 | 呼叫之介面 |
|---|---|---|
| 1 | 使用者詢問可用場域時，取得場域清單與配置並轉述 | I-1、I-2 |
| 2 | 使用者確認場域、負載型態、模擬長度、（類型二）事件清單後，觸發模擬 | I-3 |
| 3 | 若觸發為非同步，輪詢至完成 | I-4 |
| 4 | 取回該次模擬之觀測資料與事件紀錄，序列化為我方之雙格式觀測 | I-5、I-6 |
| 5 | 我方進行一致性檢核、問題分析、測項生成與入庫（不再呼叫貴方） | 無 |

對貴方之核心要求有四：（一）同一觸發參數（含種子）重跑可得相同資料；（二）觀測資料分彙整觀測與原始觀測兩種格式（見 I-5），原始觀測須含每終端量測（含鄰區量測）與 cell 級量測；（三）事件紀錄須含量測報告、重建、無線鏈路失敗、換手失敗原因；（四）缺項以 null 表示並明列，不得以 0 代替。

---

## 貳、總則

1. **傳輸與格式**：全部介面為 POST，請求參數置於 JSON 請求本文（不使用路徑參數與查詢字串），回應為 JSON（UTF-8）；大量資料得以 JSON Lines 交付或分頁。
2. **時間**：時戳附時區；建議同時提供 epoch 秒（`timestamp`）與 ISO 8601 字串（`timestamp_iso`，例 `2026-09-21T14:00:00+08:00`）。模擬內之時間以「自模擬起點之偏移秒數」（`offset_s`）與絕對時戳並列。
3. **識別**：場域以 `field_id`；cell 以全域識別 `ncgi`（或貴方之 `cell_id`）；gNB 以 `gnb_id`；終端以 `ue_id`（同一次模擬內穩定）；每次模擬以 `run_id`。同一 cell 在配置、觀測、事件各介面中之識別必須一致。
4. **單位**：功率 dBm；RSRP dBm；RSRQ 與 SINR dB；吞吐 Mbps；資料量 bytes；延遲 ms；距離公尺；量測名稱依 3GPP TS 28.552 與 O-RAN E2SM-KPM 原名。
5. **缺項**：貴方無法提供之欄位以 `null` 表示並於回應之 `unavailable_fields` 陣列列出欄位名，勿以 0 或空字串代替（0 為有效觀測值）。
6. **資料等級**：欄位標注「必要」或「建議」。必要欄位缺失時該項功能無法運作；建議欄位缺失時我方以「觀測不足」標注後續處理。
7. **決定性**：同一 `field_id`、負載型態、模擬長度、事件清單與 `seed`，重跑須得到相同之觀測資料與事件紀錄。

---

## 參、介面清單

| 編號 | 介面 | 目的 | 建議路徑 | 請求本文 | 頻率 |
|---|---|---|---|---|---|
| I-1 | 查詢場域清單 | 得知可用場域、其支援之負載型態與事件型別 | `POST /fields/list` | `{}` | 使用者詢問時 |
| I-2 | 取得場域配置 | 空間結構化描述、cell 清單、鄰區關係、Xn、收集參數 | `POST /fields/config` | `{field_id}` | 使用者詢問時、觸發前 |
| I-3 | 觸發情境 | 以指定場域、負載型態、模擬長度、種子與事件清單啟動一次模擬 | `POST /scenarios/run` | `{field_id, load_profile, duration_s, seed, events, magnitude}` | 每次任務 |
| I-4 | 查詢執行狀態 | 非同步觸發時輪詢完成 | `POST /scenarios/status` | `{run_id}` | 觸發後 |
| I-5 | 取得觀測資料 | 該次模擬之彙整觀測與原始觀測（cell 級量測、每終端量測） | `POST /runs/observations` | `{run_id, format, from, to, cells, page_size, next_token}` | 每次任務 |
| I-6 | 取得事件紀錄 | 該次模擬之量測報告、換手失敗、重建、無線鏈路失敗、CGI 解析 | `POST /runs/events` | `{run_id, from, to, types}` | 每次任務 |
| I-7（選配） | 取得組態變更紀錄 | 模擬中由貴方系統自行變更之組態（如節能自動關斷） | `POST /runs/config-changes` | `{run_id}` | 需要時 |

---

## 肆、逐介面規格

### I-1 查詢場域清單

**目的**：使用者詢問「現在有哪些場域」時，我方須取得貴方可用之場域、各場域支援之負載型態名與事件型別，據以向使用者列選單。

**請求**：`POST /fields/list`，本文 `{}`。

**期望回應欄位**

| 欄位 | 型別 | 等級 | 說明 |
|---|---|---|---|
| fields[].field_id | 字串 | 必要 | 場域唯一識別 |
| fields[].name、site、floor | 字串 | 必要／建議 | 名稱；建物與樓層（建議） |
| fields[].config_version | 字串 | 必要 | 配置版本，與 I-2 一致 |
| fields[].updated_at | 字串 | 必要 | 配置最後更新時間 |
| fields[].cell_count | 整數 | 必要 | cell 數 |
| fields[].load_profiles[] | 陣列 | 必要 | 貴方內建負載型態：`name`、`description`、`default_ue_count`、`mobility`（例：一般走動、通勤人流、尖峰時段） |
| fields[].event_types[] | 陣列 | 必要 | 可觸發之事件型別名與其參數綱要（見 I-3） |
| fields[].intrinsic_features[] | 陣列 | 建議 | 場域固有屬性之名稱與位置（例：同頻重疊區、覆蓋交會口）；僅名稱與範圍，不含問題判定 |
| fields[].coordinate_convention | 字串 | 必要 | 空間座標約定（軸向、單位、原點），與 I-2 之 `space` 一致 |
| fields[].limits | 物件 | 必要 | `granularity_period_s`、`max_duration_s`、`max_windows`、`concurrent_runs` |

**回應範例**
```json
{
 "fields": [
  {"field_id": "ee7_corridor_4cell", "name": "EE 大樓 7 樓走廊", "site": "EE 大樓", "floor": "7F",
   "config_version": "3", "updated_at": "2026-09-21T10:00:00+08:00", "cell_count": 4,
   "load_profiles": [
     {"name": "walk_normal", "description": "一般走動", "default_ue_count": 30, "mobility": "隨機停留與走廊移動"},
     {"name": "commute_flow", "description": "通勤人流", "default_ue_count": 70, "mobility": "走廊縱向往返"},
     {"name": "peak_hours", "description": "尖峰時段", "default_ue_count": 90, "mobility": "高密度往返"}],
   "event_types": ["cell_addition", "cell_outage", "tx_power_change", "antenna_change", "relation_change", "energy_saving_state"],
   "intrinsic_features": [{"name": "co_channel_overlap", "cells": ["NCGI-C02", "NCGI-C03"], "range": {"x": [2.4, 4.9], "z": [-7.5, 7.4]}}],
   "coordinate_convention": "x 向右、z 向前、y 向上，單位公尺，原點為場域基準點",
   "limits": {"granularity_period_s": 60, "max_duration_s": 3600, "max_windows": 60, "concurrent_runs": 1}}
 ]
}
```

### I-2 取得場域配置

**目的**：場域配置為我方一切分析之基準：向使用者據實轉述；分析結果與配置核對；鄰區關係為鄰區類問題之判準核心；cell 座標與幾何為覆蓋類問題之判定基礎；收集參數決定基準值計算方式。我方於每次任務開始時取得一份並附 `config_version` 保存，任務內各步驟以該份為準。

**請求**：`POST /fields/config`，本文：
```json
{"field_id": "ee7_corridor_4cell"}
```

**期望回應欄位**

（一）空間 `space`（結構化描述；我方各步驟之判斷皆以此為據，不需三維模型）：`coordinate_convention`（必要）、`segments[]`（必要：可行走區段，`segment_id`、`name`、`x_range`、`z_range`、`width_m`、`length_m`）、`junctions[]`（必要：交會口與轉角，`junction_id`、`position{x,z}`、`connects[]` 所連接之 segment_id）、`ceiling_height_m`（建議）、`environment`（必要）、`obstacles[]`（選配：門洞、凹室等，`type`、`x_range`、`z_range`）。

（二）cell 清單 `cells[]`：`ncgi`、`cell_id`、`gnb_id`（必要）、`ran_name`（建議）、`pci`、`arfcn`、`tx_power_dbm`（必要）、`bandwidth_mhz`（建議）、`position{x,z,h}`（必要）、`antenna{azimuth_deg,tilt_deg,type}`（建議）、`administrative_state`、`operational_state`、`energy_saving_state`（必要）、`ric_managed`（必要）。

（三）鄰區關係 `neighbour_relations[]`（單向）：`source_ncgi`、`target_ncgi`、`target_pci`、`target_arfcn`、`xn_x2_established`、`is_ho_allowed`、`is_remove_allowed`（必要）、`ho_validated`、`created_at`、`updated_at`（建議）。

（四）Xn 連線 `xn_links[]`：`gnb_a`、`gnb_b`、`established`（必要）、`since`（建議）。

（五）收集參數 `collection`：`granularity_period_s`、`timezone`（必要）、`baseline_windows_required`（必要：我方計算各時段常態基準所需之最少無事件窗數，由貴方確認可提供）、`clock_source`（建議）。

**回應範例**
```json
{
 "field_id": "ee7_corridor_4cell", "config_version": "3", "updated_at": "2026-09-21T10:00:00+08:00",
 "space": {"coordinate_convention": "x 向右、z 向前、y 向上，單位公尺，原點為場域基準點",
           "segments": [{"segment_id": "S1", "name": "主走廊", "x_range": [2.4, 4.9], "z_range": [-27.5, 7.4], "width_m": 2.5, "length_m": 33.5},
                        {"segment_id": "S2", "name": "橫向走廊", "x_range": [-6.5, 4.9], "z_range": [7.4, 10.9], "width_m": 3.5, "length_m": 11.4},
                        {"segment_id": "S3", "name": "偏移段走廊", "x_range": [0.6, 2.9], "z_range": [10.9, 32.5], "width_m": 2.25, "length_m": 21.6}],
           "junctions": [{"junction_id": "J1", "position": {"x": 3.6, "z": 9.2}, "connects": ["S1", "S2"]},
                         {"junction_id": "J2", "position": {"x": 1.75, "z": 10.9}, "connects": ["S2", "S3"]}],
           "ceiling_height_m": 3.51, "environment": "indoor_corridor", "obstacles": []},
 "cells": [
  {"ncgi": "NCGI-C01", "cell_id": "99f966000214001", "gnb_id": "133", "ran_name": "gnb_999_066_000214_d_00000001", "pci": 101, "arfcn": 630000, "bandwidth_mhz": 100, "tx_power_dbm": 24,
   "position": {"x": 3.6, "z": -21.0, "h": 2.8}, "antenna": {"azimuth_deg": 0, "tilt_deg": 0, "type": "omni"},
   "administrative_state": "unlocked", "operational_state": "enabled", "energy_saving_state": "notEnergySaving", "ric_managed": true},
  {"ncgi": "NCGI-C02", "cell_id": "99f9660402e8001", "gnb_id": "134", "ran_name": "gnb_999_066_0402e8_d_00000001", "pci": 103, "arfcn": 630000, "bandwidth_mhz": 100, "tx_power_dbm": 24,
   "position": {"x": 3.6, "z": -7.5, "h": 2.8}, "antenna": null,
   "administrative_state": "unlocked", "operational_state": "enabled", "energy_saving_state": "notEnergySaving", "ric_managed": true}
 ],
 "neighbour_relations": [
  {"source_ncgi": "NCGI-C01", "target_ncgi": "NCGI-C02", "target_pci": 103, "target_arfcn": 630000, "xn_x2_established": true, "ho_validated": true, "is_ho_allowed": true, "is_remove_allowed": true},
  {"source_ncgi": "NCGI-C02", "target_ncgi": "NCGI-C01", "target_pci": 101, "target_arfcn": 630000, "xn_x2_established": true, "ho_validated": true, "is_ho_allowed": true, "is_remove_allowed": true}
 ],
 "xn_links": [{"gnb_a": "133", "gnb_b": "134", "established": true, "since": "2026-08-01T00:00:00+08:00"}],
 "collection": {"granularity_period_s": 60, "timezone": "Asia/Taipei", "baseline_windows_required": 6, "clock_source": "simulated"},
 "unavailable_fields": ["cells[].antenna"]
}
```

### I-3 觸發情境

**目的**：以使用者確認之參數啟動一次模擬。類型一不含事件；類型二含事件清單。我方將此請求原樣保存作為該次任務之情境配置與（類型二之）正確答案。

**請求**：`POST /scenarios/run`，本文：

| 欄位 | 型別 | 等級 | 說明 |
|---|---|---|---|
| field_id | 字串 | 必要 | 場域 |
| config_version | 字串 | 建議 | 我方保存之配置版本；不符時貴方回錯誤 |
| load_profile | 字串 | 必要 | 貴方內建負載型態名（I-1 所列） |
| ue_count | 整數 | 建議 | 覆寫型態預設終端數；省略即用預設 |
| duration_s | 整數 | 必要 | 模擬長度（秒）；不得低於 `baseline_windows_required` 加事件後窗數乘 `granularity_period_s` |
| seed | 整數 | 必要 | 種子；同參數重跑須得相同資料 |
| events[] | 陣列 | 必要（可為空） | 逐事件：`event_id`、`type`（I-1 所列）、`target`（cell 之 ncgi 或關係識別）、`at_offset_s`（自模擬起點之秒數）、`duration_s`（持續；null 為至結束）、`params`（依型別） |
| magnitude | 數值 | 建議 | 事件強度係數，預設 1.0 |
| requester_task_id | 字串 | 建議 | 我方任務識別，供追溯 |

各事件型別之 `params`（建議綱要，請貴方確認）：

| type | params |
|---|---|
| cell_addition | `ncgi`、`pci`、`arfcn`、`tx_power_dbm`、`position{x,z,h}`、`neighbour_relations`（新 cell 之關係清單，可為空以呈現缺漏） |
| cell_outage | `reason`（例 `hardware`、`planned`） |
| tx_power_change | `tx_power_dbm_after` |
| antenna_change | `tilt_deg_after`、`azimuth_deg_after` |
| relation_change | `source_ncgi`、`target_ncgi`、`action`（`add`、`remove`、`set`）、`attributes{is_ho_allowed,is_remove_allowed}` |
| energy_saving_state | `state_after`（`energySaving`、`notEnergySaving`） |

**期望回應**：`run_id`（必要）、`instance_id`（建議：貴方對此組參數之決定性識別）、`status`（`accepted`、`running`、`done`）、`started_at`、`estimated_finish_at`、`echo`（貴方實際採用之參數，含預設值填充後之結果）。

**請求範例**
```json
{
 "field_id": "ee7_corridor_4cell", "config_version": "3", "load_profile": "commute_flow", "ue_count": null,
 "duration_s": 900, "seed": 202609211400,
 "events": [
  {"event_id": "E1", "type": "cell_addition", "target": "NCGI-C05", "at_offset_s": 360, "duration_s": null,
   "params": {"ncgi": "NCGI-C05", "pci": 109, "arfcn": 630000, "tx_power_dbm": 24, "position": {"x": -5.0, "z": 9.2, "h": 2.8}, "neighbour_relations": []}}
 ],
 "magnitude": 1.0, "requester_task_id": "ANR03"
}
```

**回應範例**
```json
{"run_id": "run_20260921_000123", "instance_id": "SC-7f3a9c1d2e", "status": "running",
 "started_at": "2026-09-21T14:00:05+08:00", "estimated_finish_at": "2026-09-21T14:03:05+08:00",
 "echo": {"load_profile": "commute_flow", "ue_count": 70, "duration_s": 900, "seed": 202609211400, "events": 1}}
```

### I-4 查詢執行狀態

**目的**：觸發為非同步時，我方輪詢至完成後始取觀測。若貴方之 I-3 為同步回應（跑完才回），本介面可省略，請於伍章確認。

**請求**：`POST /scenarios/status`，本文 `{"run_id": "run_20260921_000123"}`。

**期望回應**：`run_id`、`status`（`running`、`done`、`failed`）、`progress_s`（已模擬秒數）、`finished_at`、`error`（失敗時之訊息）、`windows_available`（可取回之窗數）。

### I-5 取得觀測資料

**目的**：觀測資料是問題偵測與分析之唯一輸入，分兩種格式並列，兩者須同源同一次模擬：
- **彙整觀測（aggregated observation）**：逐 cell 之量測值物件（現值、同時段基準值、六窗趨勢）、鄰區關係與服務 cell 清單、逐鄰區關係之換手統計、量測報告彙整與重建反推。我方理解貴方資料庫已具此格式，請於伍章確認。
- **原始觀測（raw observation）**：逐窗之 E2 傾印結構，含每終端量測（含鄰區量測）與 cell 級量測鍵（322 鍵）。結構依先前E2範例，請沿用。

請求以 `format` 指定 `aggregated`、`raw` 或 `both`。

**請求**：`POST /runs/observations`，本文：
```json
{"run_id": "run_20260921_000123", "format": "both", "from": 0, "to": 900, "cells": null, "page_size": 30, "next_token": null}
```
（`from`、`to` 為自模擬起點之偏移秒數；`cells` 為 cell_id 陣列，null 即全部。）

**期望回應結構（原始觀測部分，`raw`）**
```
{
 "run_id", "field_id", "config_version", "granularity_period_s",
 "windows": [
   {"offset_s", "timestamp", "timestamp_iso",
    "e2": [ { "gnb_id", "cells": [ { "cell_id", "ncgi", "ran_name", "pci", "ues": [ ... ] } ] } ],
    "pm": { "<gnb_id>": [ { "cell_id", ...量測鍵... } ] } }
 ],
 "next_token", "unavailable_fields"
}
```

（一）每終端量測 `ues[]`

| 欄位 | 型別 | 等級 | 說明 |
|---|---|---|---|
| ue_id | 字串 | 必要 | 同一次模擬內穩定 |
| role | 整數 | 建議 | 貴方定義之角色碼 |
| interfered | 整數 | 必要 | 受擾旗標 0 或 1 |
| rsrp、rsrq、sinr | 數值 | 必要 | 服務 cell 之下行量測 |
| ul_sinr、cqi | 數值 | 建議 | 上行 SINR、寬頻 CQI |
| neighbors[] | 陣列 | 必要 | 逐鄰區 `{"<鄰區 cell_id>": {"pci", "arfcn", "rsrp", "rsrq"}}`；**須實際填值** |
| dl_throughput、ul_throughput | 數值 | 必要 | Mbps |
| rb_start、rb_width | 整數 | 建議 | 資源區塊配置 |
| position | 物件 | 建議 | `x`、`z` 或 `segment` |

（二）cell 級量測 `pm[<gnb_id>][]`：貴方範例之 322 鍵全部保留；我方判準直接依賴之必要鍵族如下。

| 鍵族 | 必要鍵（示例） | 用途 |
|---|---|---|
| du_RRU | RRU.PrbTotDl、PrbTotUl、PrbAvailDl、PrbAvailUl | 負載 |
| du_DRB、du_gnb | DRB.MeanActiveUeDl、UEThpDl、UEThpUl、AirIfDelayDlAvg | 活動終端數、吞吐、延遲 |
| cu_DRB | DRB.PdcpSduVolumeDL、PdcpSduVolumeUl | 資料量 |
| cu_RRC、cu_UECNTX | RRC.ConnMean、ConnEstabAtt、ConnEstabSucc、RRC.ConnReEstabAtt.*（含原因分項） | 連線數、重建 |
| cu_MM | MM.HoPrepIntraReq、HoPrepIntraSucc、HoExeIntraReq、HoExeIntraSucc 與失敗分項 | 換手 |
| du_TB | TB.TotNbrDl、TotNbrUl、ErrTotalNbrDl、ErrTotalNbrUl（總數不得為 0 而錯誤數非 0） | 傳輸區塊錯誤率 |
| du_CARR、du_wbCqiDist | PDSCHMCSDist.*、wbCqiDist.Avg | 通道品質 |
| du_PEE | PEE.AvgPower 與 PEE.Energy（建議） | 能耗 |
| 可用率 | cellAvailablePer | cell 中斷 |
| SINR 分布 | SSSINR 分位數（至少中位數） | 同頻干擾 |
| 時間 | cu_timestamp_start、cu_timestamp_end、du_timestamp_start、du_timestamp_end | 窗對齊 |

**回應範例**（節錄一窗、一 cell、一終端；量測鍵僅示部分）
```json
{
 "run_id": "run_20260921_000123", "field_id": "ee7_corridor_4cell", "config_version": "3", "granularity_period_s": 60,
 "windows": [
  {"offset_s": 0, "timestamp": 1789992005, "timestamp_iso": "2026-09-21T14:00:05+08:00",
   "e2": [{"gnb_id": "133", "cells": [{"cell_id": "99f966000214001", "ncgi": "NCGI-C01", "ran_name": "gnb_999_066_000214_d_00000001", "pci": 101,
            "ues": [{"ue_id": "36", "role": 1, "interfered": 0, "rsrp": -68, "rsrq": -10, "sinr": 19, "ul_sinr": 22, "cqi": 13,
                     "neighbors": [{"99f9660402e8001": {"pci": 103, "arfcn": 630000, "rsrp": -83, "rsrq": -12}}],
                     "dl_throughput": 96, "ul_throughput": 4, "rb_start": 0, "rb_width": 273, "position": null}]}]}],
   "pm": {"133": [{"cell_id": "99f966000214001", "cu_timestamp_start": "1789992005", "cu_timestamp_end": "1789992065",
                   "du_RRU.PrbTotDl": "46", "du_RRU.PrbTotUl": "36", "du_RRU.PrbAvailDl": "273",
                   "du_DRB.MeanActiveUeDl": "17.5", "du_DRB.UEThpDl": "78", "cu_RRC.ConnMean": "17", "cu_RRC.ConnReEstabAtt.sum": "2",
                   "cu_MM.HoExeIntraReq": "64", "cu_MM.HoExeIntraSucc": "64",
                   "du_TB.TotNbrUl.Tot": "98000", "du_TB.ErrTotalNbrUl.Tot": "900", "du_PEE.AvgPower": "62.5",
                   "du_gnb.PEE.cellAvailablePer": "100", "du_SSSINR.Percentile50Db": "18"}]}}
 ],
 "next_token": null, "unavailable_fields": ["e2[].cells[].ues[].position"]
}
```


**期望回應結構（彙整觀測部分，`aggregated`）**：每一負載型態時段一份（或每窗一份，由貴方確認）。每 cell 十五個量測值物件，鍵名為「量測名.cell 識別」，欄位名尾綴即單位（PerMin、Pct、Mbps、Mbit、Ms、Count、Db）；`baseline` 為同時段常態值；`trendLast30Min` 為最近六窗之序列（僅趨勢有意義之量測附之）。

```json
{
 "run_id": "run_20260921_000123", "timestamp": "2026-09-21T14:15:05+08:00", "granularityPeriod": "60s",
 "field_id": "ee7_corridor_4cell", "load_profile": "commute_flow",
 "e2NodeInformation": {
  "servingCells": [{"ncgi": "NCGI-C01", "physicalCellId": 101, "arfcn": 630000, "radioAccessTechnology": "NR"}],
  "neighbourCellRelations": [{"sourceCellNcgi": "NCGI-C01", "targetCellGlobalId": "NCGI-C02", "targetPhysicalCellId": 103,
    "targetArfcn": 630000, "targetRadioAccessTechnology": "NR", "xnX2Established": true, "hoValidated": true}]
 },
 "kpmIndication": {
  "cellLevel": {
   "RLF.DetectedRate.NCGI-C01": {"currentPerMin": 0.161, "baselinePerMin": 0.15, "trendLast30Min": [0.158, 0.141, 0.159, 0.153, 0.156, 0.161]},
   "RLF.DropWithoutReestablishmentRate.NCGI-C01": {"currentPerMin": 0.051, "baselinePerMin": 0.05},
   "RRC.ConnReEstabInboundRatePerMin.NCGI-C01": {"currentPerMin": 0.161, "baselinePerMin": 0.15},
   "HO.IntraSys.TooEarlyRate.NCGI-C01": {"currentPerMin": 0.0, "baselinePerMin": 0.0},
   "HO.IntraSys.TooLateRate.NCGI-C01": {"currentPerMin": 0.02, "baselinePerMin": 0.02},
   "HO.IntraSys.ToWrongCellRate.NCGI-C01": {"currentPerMin": 0.0, "baselinePerMin": 0.0},
   "RRU.PrbTotDl.NCGI-C01": {"currentPct": 46.765, "baselinePct": 46},
   "RRU.PrbTotUl.NCGI-C01": {"currentPct": 36.968, "baselinePct": 36},
   "DRB.UEThpDl.NCGI-C01": {"currentMbps": 75.447, "baselineMbps": 78},
   "DRB.UEThpUl.NCGI-C01": {"currentMbps": 19.444, "baselineMbps": 19},
   "DRB.PdcpSduVolumeDL.NCGI-C01": {"currentMbit": 2981.877, "baselineMbit": 2900},
   "DRB.PdcpSduVolumeUL.NCGI-C01": {"currentMbit": 780.24, "baselineMbit": 760},
   "DRB.RlcSduDelayDl.NCGI-C01": {"currentMs": 12.371, "baselineMs": 12},
   "DRB.MeanActiveUeDl.NCGI-C01": {"currentCount": 18.155, "baselineCount": 17.5},
   "SSSINR.Percentile50Db.NCGI-C01": {"currentDb": 17.994, "baselineDb": 18.0}
  },
  "perNeighbourRelation": [{"sourceCellNcgi": "NCGI-C01", "targetCellGlobalId": "NCGI-C02", "MM.HoExeAttRatePerMin": 4.6, "MM.HoExeSuccRatio_last50": 0.979}]
 },
 "e2MessageCopyAggregate": {
  "measurementReportAggregate": [{"cellNcgi": "NCGI-C01", "reportedRadioAccessTechnology": "NR", "reportedArfcn": 630000, "reportedPhysicalCellId": 103,
    "sampleRatePerMin": 45.8, "rsrpPercentile50Dbm": -83.4, "rsrpPercentile90Dbm": -77.9, "rsrpStandardDeviationDb": 3.3, "servingRsrpPercentile50Dbm": -66.0}],
  "reestablishmentInboundByPreviousPci": [{"cellNcgi": "NCGI-C05", "previousPhysicalCellId": 101, "previousArfcn": 630000, "ratePerMin": 2.9}]
 },
 "unavailable_fields": []
}
```

| 區段 | 欄位 | 等級 | 說明 |
|---|---|---|---|
| e2NodeInformation | servingCells[]（ncgi、physicalCellId、arfcn、radioAccessTechnology） | 必要 | 該窗在服務中之 cell |
| e2NodeInformation | neighbourCellRelations[]（sourceCellNcgi、targetCellGlobalId、targetPhysicalCellId、targetArfcn、xnX2Established、hoValidated） | 必要 | 鄰區關係表 |
| kpmIndication.cellLevel | 十五個量測值物件（上例所列）；每物件含 current、baseline，選配 trendLast30Min | 必要 | 現值、基準、趨勢 |
| kpmIndication.perNeighbourRelation[] | sourceCellNcgi、targetCellGlobalId、MM.HoExeAttRatePerMin、MM.HoExeSuccRatio_last50 | 必要 | 逐關係換手統計；事件數不足時以 note 說明 |
| e2MessageCopyAggregate.measurementReportAggregate[] | cellNcgi、reportedPhysicalCellId、reportedArfcn、sampleRatePerMin、rsrpPercentile50Dbm、rsrpPercentile90Dbm、rsrpStandardDeviationDb、servingRsrpPercentile50Dbm | 必要 | 量測報告彙整（含不在鄰區表之 PCI） |
| e2MessageCopyAggregate.reestablishmentInboundByPreviousPci[] | cellNcgi、previousPhysicalCellId、previousArfcn、ratePerMin | 必要 | 重建反推 |

### I-6 取得事件紀錄

**目的**：事件紀錄為終端與基站層級之**逐筆訊息副本**（例如 3GPP 量測事件 A3 觸發之 RRC 量測報告、RRC 重建請求、無線鏈路失敗指示、換手準備失敗訊息），非統計值。cell 級量測僅有計數（如 A3 事件次數），沒有「回報了哪個 PCI、訊號多少」或「重建時前一服務 cell 為何」等明細；這些明細是彙整觀測中量測報告彙整與重建反推之來源，亦是判定缺漏鄰區、PCI 混淆、覆蓋洞、換手問題所需。若貴方提供彙整觀測（I-5 之 `aggregated`），本介面降為建議等級，供佐證與交叉核對。

**請求**：`POST /runs/events`，本文：
```json
{"run_id": "run_20260921_000123", "from": 0, "to": 900, "types": ["meas_report", "rrc_reestab_req", "ho_prep_fail", "rlf", "cgi_resolution"]}
```

**期望回應**：`events[]`，共通欄位 `offset_s`、`ts`、`ts_iso`、`type`、`gnb_id`、`cell_id`、`ue_id`（cgi_resolution 除外）、`payload`；`type` 枚舉與 payload 如下。

| type | payload 欄位 |
|---|---|
| meas_report | `reported[]`：`{pci, arfcn, rsrp, rsrq}`；`serving_rsrp`；`event_trigger`（例 A3） |
| ho_prep_fail、ho_exe_fail | `target_pci`、`target_ncgi`（可為 null）、`cause`、`cause_category`（`timeout`、`rejected`、`rlf`、`other`） |
| ho_exe_succ | `target_ncgi` |
| rrc_reestab_req | `reestablishment_cause`、`previous_pci`、`previous_ncgi`（可為 null）、`target_cell_id` |
| rlf | `serving_pci`、`last_rsrp`、`last_sinr`、`reestablished` |
| conn_release | `cause` |
| cgi_resolution | `pci`、`arfcn`、`resolved_ncgi[]` |

**回應範例**
```json
{"run_id": "run_20260921_000123",
 "events": [
  {"offset_s": 372, "ts": 1789992377, "ts_iso": "2026-09-21T14:06:17+08:00", "type": "meas_report", "gnb_id": "133", "cell_id": "99f966000214001", "ue_id": "36",
   "payload": {"reported": [{"pci": 109, "arfcn": 630000, "rsrp": -71, "rsrq": -9}], "serving_rsrp": -68, "event_trigger": "A3"}},
  {"offset_s": 390, "ts": 1789992395, "ts_iso": "2026-09-21T14:06:35+08:00", "type": "rrc_reestab_req", "gnb_id": "134", "cell_id": "99f9660402e8001", "ue_id": "41",
   "payload": {"reestablishment_cause": "handoverFailure", "previous_pci": 101, "previous_ncgi": "NCGI-C01", "target_cell_id": "99f9660402e8001"}},
  {"offset_s": 405, "ts": 1789992410, "ts_iso": "2026-09-21T14:06:50+08:00", "type": "cgi_resolution", "gnb_id": "133", "cell_id": "99f966000214001", "ue_id": null,
   "payload": {"pci": 109, "arfcn": 630000, "resolved_ncgi": ["NCGI-C05"]}}
 ], "unavailable_fields": []}
```

### I-7（選配）取得組態變更紀錄

**目的**：模擬中若貴方系統自行變更組態（例如節能功能自動關斷 cell、鄰區關係自動新增或移除），我方需知其時間與前後值，以區分「我方觸發之事件」與「貴方系統之自主行為」。

**請求**：`POST /runs/config-changes`，本文 `{"run_id": "..."}`。

**期望回應**：`changes[]`：`offset_s`、`ts_iso`、`object_type`（`cell`、`neighbour_relation`、`xn_link`）、`object_id`、`attribute`、`before`、`after`、`origin`（`triggered_event`、`son_function`、`system`）。

---

## 伍、我方對貴方能力之理解（請確認是否有誤）

下表為我方目前對 RAN Emulator 能力之理解，來源為委託者轉述。請逐項確認；有誤者請更正。

| 項 | 我方理解 | 狀態 | 對介面之影響 |
|---|---|---|---|
| 1 | Emulator 內部具種子配置，同一參數重跑可復現相同資料 | 已確認 | I-3 之 `seed` 必要；貳章第 7 條 |
| 2 | Emulator 內建負載型態名，預設隨機產生終端數量與路徑；型態包含一般走動、通勤人流、尖峰時段 | 已確認 | I-1 之 `load_profiles[]`；I-3 之 `load_profile` 以貴方名稱為準，我方不另定義 |
| 3 | 基本事件型別皆支援：新增 cell、cell 中斷、發射功率調整、天線參數、鄰區關係增刪、節能狀態 | 已確認 | I-1 之 `event_types[]`；I-3 之 `params` 綱要請貴方確認 |
| 4 | 場域固有屬性（如同頻重疊、覆蓋交會口）可配置，但以貴方既有場域物件配置為基礎；我方不移動物件配置 | 已確認 | I-1 之 `intrinsic_features[]` 僅登記名稱與範圍；我方不送物件位置 |
| 5 | 觀測收集間隔、一次模擬可取之窗數、每終端鄰區量測與事件紀錄之提供範圍 | 待確認 | I-1 之 `limits`、I-2 之 `collection`、I-5 與 I-6 之內容 |
| 6 | 觸發為同步（跑完才回）或非同步（回 run_id 再輪詢） | 待確認 | I-4 是否需要 |
| 7 | 場域空間由 Emulator 提供 | 已確認 | I-2 之 `space` 以結構化描述（區段、交會口、淨高、座標約定）提供；不傳三維模型檔 |

---

## 陸、待確認事項（請貴方逐項答覆）

1. **收集間隔與窗數**：每一收集窗之秒數為何？一次模擬最多可取回幾窗？我方計算各負載型態之常態基準值需至少六個無事件窗，貴方可否於同一次模擬內提供（例如事件之 `at_offset_s` 前之各窗）？
2. **觸發方式**：I-3 為同步或非同步？非同步時，狀態查詢之建議輪詢間隔與逾時為何？失敗時如何回報原因？
3. **每終端量測**：`neighbors[]` 是否實際填值？是否提供 `ul_sinr`、`cqi`、終端位置或所在區段？
4. **事件紀錄**：I-6 所列七種事件型別中，貴方可提供哪些？量測報告是否含被回報之 PCI 與 RSRP？重建請求是否含前一 PCI？換手失敗是否含原因？是否提供 CGI 解析結果？
5. **負載型態**：內建型態之完整名稱清單、各型態之預設終端數與路徑語意；是否允許以 `ue_count` 覆寫終端數。
6. **事件參數**：肆章 I-3 所列各型別之 `params` 綱要是否正確？新增 cell 是否需座標與天線參數？鄰區關係增刪以何識別？功率調整之允許範圍？
7. **空間描述**：貴方可否以區段與交會口之結構化描述提供空間（I-2 之 `space`）？座標約定與單位為何？cell 座標是否隨 I-2 回傳且與空間描述同一座標系？
8. **並行與保存**：同一場域可否並行多次模擬？模擬結果保存多久？`run_id` 逾期後 I-5、I-6 之回應為何？
9. **傳輸區塊量測**：E2範例傳輸區塊總數欄位為 0 而錯誤數非 0，請確認總數欄位於正式資料中是否填值。
10. **彙整觀測**：貴方資料庫是否具備 I-5 所列彙整觀測格式？其基準值（baseline）以何時段、幾窗計算？趨勢（trendLast30Min）之窗數與間隔？量測報告彙整與重建反推是否由貴方計算？若不提供，我方將自原始觀測與事件紀錄導出。
11. **自主組態變更**：貴方系統是否會於模擬中自行變更組態（節能、自動鄰區）？若會，I-7 是否可提供。

---

## 柒、接線前之核對程序

1. 貴方先提供一個場域之 I-1 與 I-2 回應，及一次不含事件之短模擬（例如十窗）之 I-5 與 I-6 資料。
2. 我方以既有之格式檢核與一致性檢核試跑（含終端數對連線數、cell 中斷之可用率與資源占用、重建與換手失敗之對應、傳輸區塊錯誤數不得大於總數），不一致處回饋貴方。
3. 必要欄位缺失者暫不接線；建議欄位缺失者於我方分析結果中標注「觀測不足」。
4. 雙方確認 cell 識別（ncgi、cell_id、gnb_id）之對映與負載型態名之對映後，以一次含事件之模擬（新增 cell）做端到端驗證，正式接線。

---

## 捌、與先前之 E2 傾印範例之對照

| 介面 | 範例已有 | 需補充 |
|---|---|---|
| I-1、I-2 | gnb_id、cell_id、ran_name、pci | 場域清單、負載型態名、事件型別、座標、功率、頻點、狀態、鄰區關係表、Xn、收集參數 |
| I-3、I-4 | 無 | 全部 |
| I-5 每終端 | 11 個欄位 | neighbors 實填、服務 cell 之 ncgi、ul_sinr 與 cqi（建議）、offset_s |
| I-5 cell 級 | 322 個量測鍵（單一時窗） | 連續多窗、換手失敗分項、cellAvailablePer、SSSINR 分位數、PEE.Energy（建議）；傳輸區塊總數不得為 0 |
| I-6、I-7 | 無 | 全部 |
