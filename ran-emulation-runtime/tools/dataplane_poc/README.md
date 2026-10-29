# P0 資料面 PoC：真實封包吞吐跟隨 DT 計算

目的：驗證 DT 算出的通道容量能不能由真實封包（iperf3）跑出來。不改任何 DT 程式碼，對 DT 只做讀取。

```
[netns dtpoc-ue1] veth-ue 10.250.0.1 ══ veth-dn 10.250.0.2 [netns dtpoc-dn]
 iperf3 client                                               iperf3 server
            ↑ shaper.py 每 100 ms 讀 DT 量測 → tc 改寫 htb 速率
```

| 檔案 | 作用 | 權限 |
|---|---|---|
| `setup_netns.sh` | 建兩個 netns、一對 veth，兩端出口掛 htb + netem | sudo |
| `teardown_netns.sh` | 全部移除（刪 netns 即連帶刪 veth 與 tc） | sudo |
| `shaper.py` | 讀 CU `Logs/TelemetryExportReader/read`（唯讀游標），把指定 UE 的 `throughput_dl/ul_mbps` 套到 tc。`--dry-run` 只印指令 | tc 需 sudo |
| `run_poc.sh` | 一個場景跑 UDP、TCP 下行各一組 iperf3（`-R`），期間 shaper 同步運作 | sudo |
| `compare.py` | 對齊時間序列，算 MAPE、MAE、相關係數、總量比、追隨延遲，輸出 `summary.md` | 一般 |

## 使用步驟

```bash
sudo apt install iperf3                     # 本機目前沒有
sudo ./setup_netns.sh                       # 最後會 ping 一次確認連通
# 啟動 DT 測試 run(1x),測試 UE 設為 full-buffer
sudo UE_ID=<UE> SCENARIO=s1_center ./run_poc.sh
python3 compare.py out/s1_center_<時間>
sudo ./teardown_netns.sh
```

可調整的環境變數：`DURATION`（預設 60）、`UDP_BW`（預設 1G，必須高於容量）、`AIR_DELAY_MS`（預設 0）、`CU_URL`（預設 `http://localhost:8101`）。

## 模型假設

- **速率**：直接採用 DT 回報的每 UE 吞吐。測試 UE 必須是 full-buffer，回報值才等於容量。
- **延遲**：只加上 `AIR_DELAY_MS`。排隊延遲由 tc 佇列自然產生；DT 的 `rlc_sdu_delay_dl_ms` 只記錄在 CSV 裡做對照。
- **丟包**：預設 0。HARQ 加上 RLC AM 之後的殘餘丟包趨近 0，BLER 的影響已經反映在 DT 的吞吐裡。
- **上行**：預設不整形（`SHAPE_UL=1` 才開）。full-buffer 劇本的上行需求是 0；如果照 DT 回報值整形，下行 TCP 的 ACK 會送不回去。
- **吞吐為 0**（未連線、換手中斷）：套用 8 kbit 加 100% 丟包。
- **時間解析度**：取決於 DT 寫入 MeasurementLog 的頻率。shaper 每 100 ms 輪詢一次，但只有出現新的量測列時才改寫 tc。

## 驗收門檻（暫定）

- UDP 的 MAPE ≤ 5%。
- TCP 的 MAPE ≤ 15%。
- 追隨延遲（lag）≤ 2 個 tick。
