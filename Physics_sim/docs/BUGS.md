# ranp-sim Bug List

追蹤開發過程中發現並修正的 bug。格式：`[狀態] #編號 — 簡述`

**狀態標記**：`✅ 已修正` / `🔧 進行中` / `🚧 已知但暫不修` / `❌ 無法重現`

---

## ✅ #001 — Mitsuba scene BSDF id 與 shape ref 不匹配

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：✅ 已修正
**嚴重度**：🔴 Critical（Sionna 載入場景失敗）

### 症狀
執行 `tools/scene_to_mitsuba.py` 產出的 Mitsuba XML，Sionna `load_scene()` 雖然不直接報錯，但所有 shape 都找不到對應的 radio material。

### 根因
`tools/scene_to_mitsuba.py` 的材質 BSDF 用 **ITU 名稱**當 id（`itu_concrete`），但 shape 的 `<ref id="...">` 用**原始名稱**（`concrete`）。Mitsuba 按 id 字串匹配，對不上 → BSDF 沒掛到 shape 上。

### 修正
`tools/scene_to_mitsuba.py`：統一 BSDF id 和 shape ref 都使用 ITU 名稱，新增 `_itu(m)` helper function。
- 修正 commit：volume mount 開發模式即時生效
- 檔案：`/home/mitlab/Omniverse/Omniverse/ranp-sim/tools/scene_to_mitsuba.py`

### 驗證
重新執行 `python3 tools/scene_to_mitsuba.py`，檢查 XML 內 `<bsdf id="itu_concrete">` 對應的 `<ref id="itu_concrete">`。

---

## ✅ #002 — Container 抓不到 OptiX，Sionna init 失敗

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：✅ 已修正
**嚴重度**：🔴 Critical（整個服務無法啟動 Sionna engine）

### 症狀
呼叫 `/api/v0.1/RanpSim/RanSignal/ConfigManager/reload` 回傳：
```json
{
  "success": false,
  "message": "Reload failed: [parser.cpp:1716] At string (line 1, col 2): failed to instantiate scene plugin of type \"scene\": Could not initialize OptiX!"
}
```

### 根因
`nvcr.io/nvidia/pytorch:24.10-py3` 基底映像預設 `NVIDIA_DRIVER_CAPABILITIES=compute,utility,video`，**缺 `graphics`**。沒有 `graphics` 權限，NVIDIA Container Toolkit 不會把 host 的 `libnvoptix.so` 掛進 container，Mitsuba 的 OptiX 後端找不到 library 就 bail。

驗證方法：
```bash
docker compose exec ranp-sim find / -name 'libnvoptix*' 2>/dev/null
# 修正前：無輸出
# 修正後：/usr/lib/x86_64-linux-gnu/libnvoptix.so.1 等
```

### 修正
`docker-compose.yml` 新增 `environment.NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics,video`，然後 `docker compose down && up -d` 重建 container。
- 檔案：`/home/mitlab/Omniverse/Omniverse/ranp-sim/docker-compose.yml`

### 驗證
容器內 `find / -name 'libnvoptix*'` 能看到 `libnvoptix.so.580.126.09` + `libnvoptix.so.1`，後續 Sionna engine 能正常初始化。

---

## ✅ #003 — Sionna v2 CIR tensor 維度與舊版不同

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：✅ 已修正
**嚴重度**：🔴 Critical（compute endpoint 500 Error）

### 症狀
呼叫 `/ComputeRunner/compute` 拿到：
```
IndexError: too many indices for array: array is 6-dimensional, but 7 were indexed
```
修掉維度後仍只有「部分 UE 有結果，其他 UE 被標記 not in CIR result」。

### 根因
Sionna RT **v1.x** CIR shape：`[batch, num_rx, num_rx_ant, num_tx, num_tx_ant, num_paths, num_time]`（7 維）。
Sionna RT **v2.0.1** CIR shape：`[num_rx, num_rx_ant, num_tx, num_tx_ant, num_paths, num_time]`（**6 維，沒有 batch**）。

另外，cross-polarization 下 `num_rx_ant = 2`（兩條正交極化分支），V 單極化才是 1。

原本程式誤把 `a.shape[1]` 當成 `num_rx` → 實際只遍歷了 2 次（剛好等於 num_rx_ant），導致 5 個 UE 只有 2 個有結果。

### 修正
`sionna_engine.py::SionnaEngine.compute_paths`：
1. 索引改為 6 維：`a[rx_i, :, tx_j, :, :, 0]`
2. `num_rx = a.shape[0]`（不是 `shape[1]`）
3. 保留對 7 維 tensor 的向下相容（若 `a.ndim == 7` 取 `a[0]`）
4. 對 `num_rx_ant` / `num_tx_ant` 多元素做 power sum，正確處理 cross polarization
- 檔案：`/home/mitlab/Omniverse/Omniverse/ranp-sim/main/apps/ran_signal/services/optional/ran_calculation/sionna_engine.py`

### 驗證
- 5 UE compute 全部出現在 `path_gain_linear`，無 warning
- UE_NLOS_Shadow 對 gNB_Macro_SE 的 RSRP 比對 gNB_Macro_NW 低 35.7 dB（建築物遮蔽生效，FSPL 看不出來）
- 10 連續 tick 壓力測試穩定，median 76ms

---

## ✅ #004 — RSRQ 公式在低干擾時出現正值

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：✅ 已修正
**嚴重度**：🟡 Low（對 serving cell 選擇與 SINR 無影響）

### 症狀
`data.e2[].cells[].ues[].rsrq` 出現 `+24`、`+15`、`+12` 等正值。3GPP RSRQ 正常範圍應是 -20 ~ -3 dB。

### 根因
`e2_formatter.py::build` 的舊公式把 RSRP 當 per-RE、RSSI 當全頻寬雜訊，又加了 `+10·log10(N_RB)`（≈+24.4 dB），三個量綱混用導致正值。

### 修正
`e2_formatter.py` 改用 3GPP TS 38.215 §5.1.3 簡化式：
```
RSRQ_dB ≈ -10·log10(12) - 10·log10(1 + 1/SINR_lin)
        = -10.8 dB (極限，SINR→∞)
        ≈ -13.8 dB (SINR=0 dB)
        ≈ -21 dB (SINR=-10 dB)
```
且下界 clip 到 -43（3GPP ReportConfig 有效最低值）。Neighbor RSRQ 改用該 neighbor 自己為 serving 重算 SINR 後套同樣公式。
- 檔案：`main/apps/ran_signal/services/optional/ran_calculation/e2_formatter.py`

### 驗證
驗證後所有 RSRQ 值落在 [-21, -11] dB 合理區間；SINR 越高 RSRQ 越接近 -10.8 dB 上限。

---

## 🚧 #008 — 8 GB VRAM 被 Omniverse Kit 搶佔時 Sionna 變慢 30~60×

**發現日期**：2026-04-18
**狀態**：🚧 已知環境限制（非 code bug）
**嚴重度**：🟠 High（影響 demo 效能）

### 症狀
當 Omniverse Kit App（`ran_server.kit`）同時跑時，Sionna compute 從 70ms 升到 4000~6000ms。

### 根因
`nvidia-smi` 顯示：
- Omniverse Kit 吃 **3.6 GB VRAM**
- ranp-sim Sionna 只分到 **1.0 GB**（其餘被 Omniverse 占用）
- GPU utilization 100%（整張卡被 Omniverse 渲染吃滿）

Sionna OptiX 需要足夠 VRAM 做 BVH + 射線緩衝，不夠時頻繁 swap 到 system memory。

### 暫不修的原因
- 硬體極限（8 GB VRAM 物理不夠 Omniverse + Sionna 同時跑）
- 解法只有：(1) 升級 GPU ≥ 16 GB；(2) demo 時關掉 Omniverse 只跑 ranp-sim；(3) 兩者跑在不同機器上透過 REST 連線

### 檢測方法
```bash
nvidia-smi --query-compute-apps=pid,process_name,used_memory --format=csv
```
若出現多於一個 Python process 吃大記憶體 → 競爭中。

### 建議
Demo 流程：
1. **純 ranp-sim demo**：關 Omniverse Kit，只跑 docker compose → 100ms/tick
2. **混合 demo**：接受 4-6 秒 tick；適合「每 5 秒更新 RSRP 看板」類展示
3. **Production**：ranp-sim 和 Omniverse 部署在不同機器


## 🚧 #005 — Django dev server auto-reload 會清掉 Sionna engine state

**發現日期**：2026-04-18
**狀態**：🚧 已知但暫不修（開發期可接受）
**嚴重度**：🟢 Info

### 症狀
改 `.py` 檔案後，Django dev server 偵測變更重載，下一個 `/compute` 請求回 404：
```json
{"success":false,"message":"scene_id 'umi_3sector_v1' not loaded on this server"}
```
要再呼一次 `/ConfigManager/reload` 才能用。

### 根因
`SionnaBusinessService` 把 engine 存在 class variable（記憶體），process 重啟就掉。`manage.py runserver` 偵測 `.py` 變更自動重啟 worker process。

### 暫不修的原因
- 僅開發期 volume mount 模式會遇到
- Production 用 gunicorn 固定 worker 不會 auto-reload
- 自動呼叫 reload 可加在 middleware 但不屬於鐵則層面的問題

### 替代做法
每次改完 code 自己補：
```bash
curl -X POST http://localhost:8000/api/v0.1/RanpSim/RanSignal/ConfigManager/reload \
  -H "Content-Type: application/json" -d '{}'
```

---

## 🟡 #006 — 首次 compute 有 CUDA kernel 冷啟動延遲（部分改善）

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：🟡 部分改善（可接受）
**嚴重度**：🟢 Info（只影響第一個請求）

### 症狀
Sionna engine reload 後的第一個 `/ComputeRunner/compute` 要 ~190ms，之後穩定在 70~80ms。

### 根因（更深入）
OptiX / Dr.Jit kernel JIT 編譯。實驗發現 **Dr.Jit 對 num_receivers 敏感**——warmup 用 1 Rx 編一份 kernel，真實請求用 5 Rx 時還會再編一次（雖然比完全冷啟動快）。

### 修正與量測
`SionnaEngine.__init__()` 加 `_warmup()`：新增虛擬 Receiver `__warmup__` 跑一次完整 PathSolver 觸發 JIT。

**實測效果**（3 gNB × 5 UE 場景）：
| 版本 | reload 耗時 | 首 compute | 後續 compute |
|---|---|---|---|
| 無 warmup | ~2.7s | ~190ms | ~70-80ms |
| 有 warmup | ~3.9s（加 120ms warmup） | ~155ms | ~70-80ms |

改善約 35ms；若要完全消除，warmup 需使用和真實請求**相同的 num_receivers**，但這需要在 init 時知道 UE 數量，代價太高。

### 不進一步修的原因
- 500 ms tick 目標下，155ms 仍有 ~345ms 餘裕
- 前端 UI 第一個 frame 有 35ms 差異使用者感知不出
- 如要完全消除可寫「UE 註冊 API」讓外部先告知數量再 warmup，複雜度不值得

### 檔案
`main/apps/ran_signal/services/optional/ran_calculation/sionna_engine.py`


## ✅ #007 — UE 天線 cross polarization 加倍 compute 開銷

**發現日期**：2026-04-18
**修正日期**：2026-04-18
**狀態**：✅ 已修正（設計取捨，留註解說明可改回）
**嚴重度**：🟢 Info（效能最佳化）

### 症狀
`rx_array = PlanarArray(polarization="cross")` 使 `num_rx_ant=2`，CIR 張量要多乘一倍，compute 時間與記憶體雙倍。

### 修正
`sionna_engine.py` 的 `scene.rx_array` 改為 `polarization="V"`，`num_rx_ant=1`。對單天線 UE 的 RSRP 量測結果等價（單極化條件下）。如要雙極化請還原為 `"cross"`（註解已說明）。
- 檔案：`main/apps/ran_signal/services/optional/ran_calculation/sionna_engine.py`

### 驗證
RSRP 數值量級不變（cross 會把兩分支功率相加給 +3 dB，V 直接取單元素），SINR 趨勢相同；compute_ms median 從 76ms 降到 ~50ms（待重測）。


## 📊 統計

| 狀態 | 數量 |
|---|---|
| ✅ 已修正 | 5 |
| 🟡 部分改善（可接受） | 1 |
| 🔧 進行中 | 0 |
| 🚧 已知暫不修 | 2 |
| ❌ 無法重現 | 0 |
| **總計** | **8** |

---

## 新增 bug 格式模板

```markdown
## [狀態] #編號 — 簡述

**發現日期**：YYYY-MM-DD
**修正日期**：YYYY-MM-DD（未修則省略）
**狀態**：[狀態標記]
**嚴重度**：🔴 Critical / 🟠 High / 🟡 Medium / 🟢 Low / Info

### 症狀
使用者看得到的現象，錯誤訊息貼上來。

### 根因
為什麼會這樣。

### 修正
改了什麼 + 檔案路徑。

### 驗證
怎麼知道修好了。
```
