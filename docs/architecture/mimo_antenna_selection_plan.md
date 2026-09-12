# 多天線鏈路:現況盤點與改造方案

> 建立 2026-09-11。目的:在動手做「天線選擇」研究前,先確認 DT 的多天線鏈路實際
> 通到哪裡、斷在哪裡,以及要打通需要付出什麼代價。
>
> **結論先講:目前整條多天線鏈路是惰性的(inert)。H 恆為 1×1,rank 恆為 1。**

---

## §1 現況:鏈路斷在哪

| # | 環節 | 位置 | 狀態 |
|---|---|---|---|
| 1 | RU 陣列設定表(rows/cols/spacing/polarization) | `RANsim-RU/main/apps/antenna/models/antenna_config.py` | ✅ 存在,有 API 可改 |
| 2 | RU 打包進請求 | `physics_client/services/optional/payload_builder.py::build_tx_config()` | ✅ 有讀、有送 |
| 3 | **RU 的 UE 端陣列** | 同上 `build_rx_config()` | ❌ **寫死 `rows=1, cols=1`**(註解自承「先給單天線版本」) |
| 4 | **Physics 接收請求** | `ran_signal/actors/path_solver_actor.py:88` | ❌ **明確忽略 tx_config / rx_config** |
| 5 | Physics 實際陣列來源 | `sionna_operations.py:135-138` 讀 `scene_config["scene_antenna_config"]` | ⚠️ 管線完整,但… |
| 6 | **`deploy/scene_config.json`** | — | ❌ **根本沒有 `scene_antenna_config` 這個 key** → 全部 fallback `1` |
| 7 | 全 repo 唯一會設 `scene_antenna_config` 的地方 | `RANsim-UE/.../physics_client.py:69` | ⚠️ **只設 `gnb_antenna_pattern`**,rows/cols 從未被設過 |
| 8 | Sionna 建陣列 | `sionna_engine.py:91-107` `rt.PlanarArray` | ✅ 實作完整,支援到 gNB 16 列 / UE 4 列 |
| 9 | **cached 模式的 npz** | `path_gain_db (T, U, C) float32` | ❌ **只有純量,沒有 H** |
| 10 | RU 算 rank | `beamforming/services/optional/sinr_estimator.py::estimate_rank()` | ✅ 實作正確,但輸入恆為 1×1 → 恆回 1 |
| 11 | DU 的 MIMO 模組 | `phy_high/services/optional/precoding/{mimo_processor,precoder}.py` | ⚠️ **死碼**:只有自己的單元測試呼叫 |
| 12 | DU TBS 乘層數 | `nr_resources.bits_per_prb_slot()` | ✅ 2026-09-11 已加(`NR_MIMO_LAYERS_ENABLED`) |

**第 4 點的註解是自承的 TODO:**
```python
# tx_config 跟 rx_config 目前 Physics_sim 內 sionna scene 已經 baked-in(在 init_scene 階段配好)
# 未來要支援動態切換 antenna config 再從 body 讀
```

---

## §2 阻擋因素:path_gain 會被天線元素數污染

在放大陣列之前必須先修這個,否則所有既有校正與 npz cache 會被靜默破壞。

`sionna_engine.py::compute_paths()`:
```python
combined = np.sum(faded, axis=-1)          # (rx_ant, tx_ant)
pg = float(np.sum(np.abs(combined) ** 2))  # ← 對所有 (rx,tx) 元素對加總
```

`path_gain` 是**對整個天線矩陣的元素對加總**。1×1 時剛好等於單一元素,看不出問題;
一旦陣列變大,`pg` 隨元素對數目線性膨脹:

| 陣列 | 元素對數 | path_gain 偏移 |
|---|---|---|
| gNB 1×1 / UE 1×1 | 1 | 0 dB(基準) |
| gNB 2×2 / UE 1×2 | 8 | **≈ +9 dB** |
| gNB 4×4 / UE 2×2 | 64 | **≈ +18 dB** |

這不是波束成形增益,是把「元素數量」當成了「接收功率」—— 即架構文件 §6 早已記載的
**antenna gain 雙重計算**。

### 規範依據與修法

**3GPP TS 38.215 §5.1.1** 定義 SS-RSRP 為承載參考訊號之 RE 的功率**線性平均**,
且明訂在接收分集下,回報值以個別接收分支為準,並非各分支功率之和
→ **RSRP 是 per-port 量,不隨陣列元素數放大。**

正確的增益分工:

| 增益來源 | 由誰產生 | 只計一次的位置 |
|---|---|---|
| path_gain / RSRP | 路徑損耗 | per-port 平均(本次修正) |
| 波束成形陣列增益 | codebook precoder `W` 作用在 `H` | `RANsim-RU/main/apps/beamforming/` |
| 空間多工增益 | `H` 的 SVD rank | DU `TBS × ν` |

**已實作**:`PHY_PATH_GAIN_PER_PORT`(預設 `off`)。開啟後 `pg /= n_rx·n_tx`。
1×1 時兩者等價,故預設 off 可保證現有數值與 npz cache 完全不變。

---

## §3 要決定的事:陣列設定的權威來源

目前有兩份且互不相通:

| 來源 | 可否 runtime 改 | 誰在用 |
|---|---|---|
| RU `AntennaConfig` 表 | ✅ 有 API | 只用來組請求 —— 而請求被 Physics 忽略 |
| Physics `scene_config.json` | ❌ 靜態 | 真正生效的那一份(但目前沒設 rows/cols) |

**做天線「選擇」的前提是設定能在 runtime 改**,所以應該打通 §1 的第 4 點,
讓 Physics 讀請求裡的 `tx_config`,而不是繼續用 baked-in。

⚠️ **但代價不低**:Physics 的 engine 是 singleton,改陣列要重建 scene
(`rt.load_scene` + warmup ≈ 4 秒)。所以**不可能做成 per-request 動態切換**。

建議折衷:做成 **scene-level 的重新配置 API**(改一次、跑一段劇本),語意上等同
現有的 `apply_override`,而不是每個 tick 都能換。天線選擇的研究通常是
「比較 N 種配置各自跑一輪」,這個粒度足夠。

---

## §4 cached 模式:最大的一塊

目前 npz 只存純量 `path_gain_db`。做多天線必須存 `H`(複數矩陣),維度從
`[tick, ue, cell]` 變成 `[tick, ue, cell, n_rx, n_tx]`。

以現有 `corridor` 場景(57600 tick × 18 UE × 2 cell)推估:

| 內容 | 大小 | 倍率 |
|---|---|---|
| 現況 `path_gain_db` float32 | 7.9 MB | 1× |
| `H` complex64,gNB 1×1 / UE 1×1 | 15.8 MB | 2× |
| `H` complex64,gNB 2×2 / UE 1×2 | **126.6 MB** | 16× |
| `H` complex64,gNB 4×4 / UE 2×2 | **1012.5 MB** | 128× |
| `H` complex64,gNB 8×8 / UE 2×2 | **4050.0 MB** | 512× |

⚠️ 現有 npz 在磁碟上是壓縮的(`corridor_00_08` 原始 7.9 MB → 磁碟 1.0 MB),
但**複數 H 的相位近似隨機,幾乎壓不動**,上表應視為實際佔用。

### 兩條路

**路線 A — 天線選擇只跑 live 模式的短劇本。**
不動 cache 格式。代價:速度上限約 2×,劇本長度受限。
適合:「比較 N 種天線配置」這種本來就不需要 24 小時的實驗。**建議先走這條。**

**路線 B — 擴充 cache 存 H。**
你近期在 precompute 上做的三件事(DrJit 快取歸還、分段換行程、24h 切時窗)在這裡
會從「優化」變成「前提條件」。開工前務必先用一個短場景實測 H 的實際壓縮率與寫入
時間,再決定是否值得。

---

## §5 建議順序

| | 動作 | 成本 | 前置 |
|---|---|---|---|
| 1 | 開 `PHY_PATH_GAIN_PER_PORT`,重跑一次基準確認 1×1 下數值不變 | 低 | — |
| 2 | 拿掉 RU `build_rx_config()` 的 1×1 硬編 | 低 | — |
| 3 | 讓 Physics 讀請求的 `tx_config`(scene-level 重配,非 per-request) | **中** | §3 決策 |
| 4 | 在 `scene_config.json` 加 `scene_antenna_config` 的 rows/cols | 低 | 1 |
| 5 | 復活 DU 的 `mimo_processor`(目前是死碼,但實作正確) | 低 | 3, 4 |
| 6 | 開 `NR_MIMO_LAYERS_ENABLED`,驗證 rank 真的動起來、吞吐隨層數變化 | 低 | 5 |
| 7 | RU 回 per-layer SINR 陣列(改 `CqiIndication` 介面)→ DU 做完整 EESM | **中** | 6 |
| 8 | (可選)cache 存 H | **高** | §4 決策 |

**第 1~2 項可以立刻做且完全可逆。第 3 項是真正的分水嶺 —— 它決定天線設定能不能
在 runtime 改,而那是「選擇」這個研究題目的前提。**

---

## §6 對既有結果的影響

* 開 `PHY_PATH_GAIN_PER_PORT` 在 1×1 下**不改變任何數值**(除以 1)。
* 一旦陣列 > 1×1,**所有既有 npz cache 必須重算** —— 因為 path_gain 的定義變了,
  且 cache 裡本來就沒有 H。
* `NR_MIMO_LAYERS_ENABLED` 在 rank 恆為 1 的現況下**不會有任何效果**;
  要等第 3~5 項打通才看得到。
