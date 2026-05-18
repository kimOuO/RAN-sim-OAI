# OAI ↔ XAPP_DT 對齊行動計畫

> 產出日期: 2026-05-16
> 來源依據: `oai_conf_alignment_report.md` + `scene_frontend_capability_report.md`
> 範圍: **不含場景**(前端自行調整),含 env 校準 + `nr_cellid` map 修正 + 核網 env 接口空殼

---

## 範圍劃分

| 區塊 | 處理方式 |
|---|---|
| **A. 場景情境建設** | ❌ 不在此計畫(使用者在 `/editor` 前端自行調整) |
| **B. env 值校準** | ✅ 本計畫 Phase 1 |
| **C. `nr_cellid` map 修正** | ✅ 本計畫 Phase 2 |
| **D. 核網 env 接口(served_plmn / TAC / SST)** | ✅ 本計畫 Phase 3 — **做接口但邏輯空殼** |

**已確認決策**:
- RIC IP 以 **XAPP_DT 為準(10.3.0.71)** → OAI conf 三份要改
- 核網三件 → **加 env 接口,但不實作 TAU / slice 分流邏輯**(等接真實 5GC 再補)

---

## Phase 1 — env 值校準(預估 0.5 天)

目標: 純改設定 / DTO 預設值,改完重啟 container 就生效。

### Task 1.1 — `GNB_ID` 對齊 OAI
**位置**: `docker-compose.yml`(cu 與 du 兩個 block)
**改動**:
```yaml
# 原
GNB_ID_HEX: "0x000038"
GNB_ID_LENGTH: "22"
# 改成
GNB_ID_HEX: "0x000e00"
GNB_ID_LENGTH: "12"
```
**理由**: 對齊 OAI `gNB_ID = 0xe00`(12-bit)。E2 Setup `globalE2node-ID` 對齊 RIC。
**驗收**: e2adapter log 看到 `globalE2node-ID gNB_ID=0x000e00 len=12`,RIC 端 E2 Setup 接受。

### Task 1.2 — 同步 RIC IP(以 XAPP_DT 為準)
**位置**: OAI 三份 conf
```libconfig
# 三份都改
e2_agent = {
  near_ric_ip_addr = "10.3.0.71";   # 原 10.3.0.204
  sm_dir = "/usr/local/lib/flexric/"
};
```
**理由**: 平台這邊 SCTP listen 在 10.3.0.71(對應記憶 `host_setup_sctp.sh` 規則)。OAI 三份 conf 跟過來,雙方握手才會成功。
**驗收**: OAI nr-softmodem 啟動後 SCTP 連 10.3.0.71:36422,e2adapter `/Status/read` 看到 OAI 那邊也建立了 sub。

### Task 1.3 — `UE_MEASUREMENT_PERIOD_MS` 降到合理值
**位置**: `docker-compose.yml`(ue block)
**改動**:
```yaml
UE_MEASUREMENT_PERIOD_MS: "40"   # 原 80
```
**理由**: 原本 80 ms ≥ TTT 60 ms,A3 邊緣根本量不到第二次來形成 "持續滿足" 條件。降到 40 ms 留至少 1 個 measurement period < TTT。
**驗收**: UE measurement period < `HO_TTT_MS`,且 A3 觸發次數明顯回升(用 KPM indication 數量比較)。

### Task 1.4 — 補 RU link budget env(目前用 hard-coded fallback)
**位置**: `docker-compose.yml`(ru block)
**改動**: 在 ru service environment 區塊加入:
```yaml
RU_TX_POWER_DBM: "43.0"
RU_SCENE_CALIBRATION_LOSS_DB: "36.0"
```
**理由**:
- 程式 (`dl_tti_pipeline.py`) 用 `get_float("RU_TX_POWER_DBM", default=43.0)` 讀,但目前 compose 沒列 → 用 fallback
- 寫進 compose 讓「真實值來源」單一,方便日後跟 OAI 校準時改一個地方就好
- `RU_ANTENNA_GAIN_DBI` 已併入 `RU_SCENE_CALIBRATION_LOSS_DB`,不再獨立(過去 +14 dBi 已含在 36 dB 內)

**驗收**: RU 啟動 log 印出 `tx_power=43.0 scene_loss=36.0 (from env)`。

---

## Phase 2 — `nr_cellid` map 修正(預估 1 天)

### 現況回顧

平台**內部**已經有 deterministic mapping:
- `RANsim-CU/main/apps/cu_cp/actors/e2_control_actor.py:43 compute_nr_cell_id(cell_id) → int`
- `RANsim-E2Adapter/main/apps/e2_adapter/services/optional/codec/e2ap_codec.py _hash_nr_cell_id(cell_id) → int`
- 兩者都用 `SHA1(cell_id)[:5] & ((1<<36)-1)`,所以 CU ↔ e2adapter ↔ RIC 內部 round-trip 沒問題

**問題**: 平台算出來的 hash 跟 OAI 真實的 `nr_cellid`(12345678、11111111)是兩組完全不同的整數。
若 RIC 上同時接到「真 OAI 上報的 nr_cellid」與「平台 hash 的 nr_cellid」,就無法歸到同一個邏輯 cell。

### Task 2.1 — scene_config schema 新增 `nr_cellid` 可選欄位
**位置**: `scene_config.json`(範本)+ 前端 `Physics_sim/Dashboard/components/ObjectForm.tsx` cells 子表單
**改動**: cell 物件新增可選欄位
```json
{
  "cell_id": "gnb1_cell0",
  "pci": 100,
  "azimuth_deg": 0,
  "nr_cellid": 12345678,    // 新增,可選;沒填就走 SHA-1 hash
  ...
}
```
**理由**: 讓「來自 OAI 的 cell」可以填 explicit `nr_cellid`;「新建的虛擬 cell」沒填則 fall back 到原 hash。
**驗收**: 前端 ObjectForm 多一欄輸入,留空合法。

### Task 2.2 — `compute_nr_cell_id()` 改成 explicit-first
**位置**: `RANsim-CU/main/apps/cu_cp/actors/e2_control_actor.py:43`
**改動**:
```python
def compute_nr_cell_id(cell_id: str, explicit: int | None = None) -> int:
    """有 explicit nr_cellid 就用,否則 SHA-1 hash(原行為)。"""
    if explicit is not None:
        return int(explicit) & ((1 << 36) - 1)
    h = hashlib.sha1(cell_id.encode()).digest()
    return int.from_bytes(h[:5], "big") & ((1 << 36) - 1)
```
**呼叫端**: 三處(`e2_control_actor.py:103`、`:273`、`kpm_indication.py:132`)需從 `Cell.objects.get(cell_id=...)` 把 `nr_cellid` 欄位帶進去。
**驗收**: 單元測試 `test_compute_nr_cell_id_explicit_wins_over_hash`。

### Task 2.3 — `_hash_nr_cell_id()` 對應改造
**位置**: `RANsim-E2Adapter/main/apps/e2_adapter/services/optional/codec/e2ap_codec.py`
**改動**: 同 Task 2.2,加 `explicit: int | None = None` 參數,優先用 explicit。
**呼叫端**: 編 RANfunction list / E2SM-KPM indication 時從 sim_http_client `cell list` payload 帶 `nr_cellid` 進來。
**驗收**: e2adapter ↔ CU 用 OAI 端真值 12345678,RIC 收到後 indication 能 round-trip。

### Task 2.4 — `Cell` DB model 新增 `nr_cellid` 欄位
**位置**: `RANsim-CU/main/apps/cu_cp/models/cell.py`(或同等)
**改動**: 新增 `nr_cellid = BigIntegerField(null=True)`(可空,沒填就 fallback)。Migration 走 Django `makemigrations`。
**對應記憶**: `feedback_clean_scene_reset` — 每次 Start Sim wipe DB,所以 migration 不會撞舊資料。
**驗收**: scene reload 後 DB 看得到 `nr_cellid` 欄。

### Task 2.5 — 加雙向反查 helper
**位置**: 新檔 `RANsim-CU/main/apps/cu_cp/services/common/cell_id_map.py`
```python
def to_nr_cellid(platform_cell_id: str) -> int: ...
def to_platform_cell_id(nr_cellid: int) -> str | None: ...
```
**理由**: 集中化兩種 ID 的轉換,避免各處散落。
**驗收**: 單元測試雙向:`to_platform_cell_id(to_nr_cellid("gnb1_cell0")) == "gnb1_cell0"`。

### Task 2.6 — sim_http_client 補 `nr_cellid` 欄位
**位置**: `RANsim-E2Adapter/main/apps/e2_adapter/services/optional/sim_bridge/sim_http_client.py`
**改動**: pull globalE2node-ID 時順便 pull cell list 的 `nr_cellid`,塞進 e2adapter local cache,後續編 PDU 時用。
**驗收**: e2adapter `/Status/read` 看到每個 cell 的 explicit `nr_cellid`。

---

## Phase 3 — 核網 env 接口空殼(預估 0.5 天)

決策: **加 env 接口讓 NGAP 編碼能塞值,但平台內部不做 TAU / slice 分流邏輯**。

### Task 3.1 — `served_plmn` DTO 預設改讀 env
**位置**: `Physics_sim/ran-sim-protocol/ran_sim_protocol/common.py:13`
**改動**:
```python
import os
from dataclasses import dataclass, field

_DEFAULT_PLMN = os.environ.get("PLMN_MCC", "001") + os.environ.get("PLMN_MNC", "01")

@dataclass
class CellConfig:
    cell_id: str
    pci: int
    ...
    served_plmn: str = field(default_factory=lambda: _DEFAULT_PLMN)
```
**理由**: 一改 `PLMN_MCC` env 就連動到 DTO 預設,不用每個 caller 都自己拼。
**驗收**: 在 CU container 設 `PLMN_MCC=208 PLMN_MNC=95`,新建 CellConfig 看到 `served_plmn="20895"`。

### Task 3.2 — `TAC` env 加進 CU compose 與 NGAP 編碼
**位置**:
- `docker-compose.yml` cu block:`TAC: "0xa000"`
- CU NGAP `NG Setup Request` 編碼處(找一下 `SupportedTAList` 編碼位置)
**改動**: 從 env 讀 TAC,塞進 `SupportedTAList` IE。**不要實作 TAU 流程**,只是讓 NGAP PDU 帶上正確值。
**驗收**: NGAP NG Setup Request log 看到 `tac=0xa000`,mock AMF 接受。

### Task 3.3 — `SST` env 加進 CU compose 與 NGAP 編碼
**位置**:
- `docker-compose.yml` cu block:`SST: "1"`、(可選 `SD: ""`)
- CU NGAP `PDU Session Resource Setup` + `NG Setup Request` 編碼處
**改動**: 從 env 讀 SST,塞進 `S-NSSAI` IE。**不要實作 slice-aware 分流**,所有 traffic 仍走預設處理。
**驗收**: NGAP PDU 看到 `s_nssai.sst=1`。

### Task 3.4 — 三個 env 在 README / 文件補記
**位置**: 更新 `docs/init_setting/ran_init_required_settings.md` 第 1.2 / 1.3 節,加上 TAC / SST 行,並標示 *目前為空殼接口,功能未實作*。
**驗收**: 新開發者讀文件看得到「這三個值會被編進 NGAP 但 CU 不做相關邏輯」。

---

## 工時與順序

| Phase | 內容 | 工時 | 阻塞依賴 |
|---|---|---|---|
| 1 | env 校準 5 項 | 0.5 天 | 無 — 可立刻動 |
| 2 | nr_cellid map 6 task | 1 天 | 無 — 但建議跟 OAI 端確認 explicit nr_cellid 取得管道 |
| 3 | 核網 3 個 env 接口空殼 | 0.5 天 | 無 |

**建議執行序**: Phase 1 → Phase 3 → Phase 2(Phase 2 工時最長但對使用者最有感,建議最後做才有足夠時間測)。
或並行 Phase 1+3(都是純改設定),Phase 2 獨立做。

---

## 驗收總清單

完成全部 task 後,以下檢查應全部通過:

```
[ ] OAI nr-softmodem ↔ XAPP_DT e2adapter SCTP 連線成功(雙向 10.3.0.71)
[ ] e2adapter /Status/read 顯示 globalE2node-ID gNB_ID=0x000e00 (12-bit)
[ ] CU 新建 cell 時,有 explicit nr_cellid 就用、沒填 fallback 到 SHA-1 hash
[ ] e2adapter 編 indication 時 nr_cellid 與 sim CU 100% 一致
[ ] OAI 真實 nr_cellid=12345678 能反查回 platform cell_id 字串
[ ] NGAP NG Setup Request 帶上正確 TAC、SST(即使 mock AMF 不檢查)
[ ] CellConfig DTO 預設 served_plmn 跟 env PLMN_MCC/MNC 連動
[ ] RU log 顯示 tx_power / scene_loss 來自 env 而非 hard-coded
[ ] UE_MEASUREMENT_PERIOD_MS = 40 < HO_TTT_MS = 60
```

---

## 不在此計畫的項目(明確列出)

- ❌ 鄰區 (`neighbour_list`) 編輯 UI + 後端 API → 留作 future work
- ❌ A2 量測事件實作 → 留作 future work
- ❌ Cell tilt(下傾角)欄位 → 留作 future work
- ❌ RU LinkBudget runtime API(完整 hot reload)→ 留作 future work(目前先用 env 冷重啟)
- ❌ 場景幾何(buildings / gNB position / azimuth)→ 由使用者在前端 `/editor` 自行操作
- ❌ TAU 流程實作、slice-aware traffic 分流 → Phase 3 只做 env 接口,不做邏輯
