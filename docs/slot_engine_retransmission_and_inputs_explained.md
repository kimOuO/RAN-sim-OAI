# RANsim Slot 引擎：重傳機制與「讓輸入更準」的修正 — 介紹

這份文件是 [`slot_engine_delay_commits_explained.md`](./slot_engine_delay_commits_explained.md) 的延伸。前一份在講 delay 本身怎麼從「粗 tick + 除 30」改成「0.5ms slot 逐格 drain」；這一份則回答一個更根本的問題：**delay / PRB / throughput 這些數字準不準，其實取決於餵進引擎的「輸入」準不準。** 內容會完整說明 slot 引擎裡的**重傳（HARQ）機制**怎麼運作、失敗機率（BLER）從哪裡參考來、以及除了 delay 之外還改了哪些東西讓輸入更貼近真機 OAI。

---

## 一、為什麼「輸入」決定一切

slot 引擎算 delay 的方式很單純：每個 0.5ms slot 算出「這格能送多少 byte」，把 FIFO 佇列 drain 出去，某個封包最後一個 byte 送出去的那一刻就是它的離開時間，delay = 離開 − 進來。

但「這格能送多少 byte」不是憑空來的，它是一連串輸入算出來的：SINR 決定 MCS、MCS 決定每格的 TBS（容量）、TDD 決定哪些格能送、重傳會佔掉格子、buffer 上限決定過載時怎麼丟。**只要其中任何一個輸入是「猜的」或「假設樂觀的」，算出來的 delay/PRB/throughput 就會歪。** 所以這次改造的重點，有一大半不是 delay 公式本身，而是把這些輸入一個一個從「猜測」換成「真實物理」。其中影響最大、也最容易被誤解的，就是重傳。

---

## 二、重傳（HARQ）機制：完整一條龍

### 重傳是什麼、為什麼會拖延遲

NR 用 HARQ（Hybrid ARQ）：一個 transport block（TB）送出去後，接收端若解不開就回 NACK，基站隔一段時間重傳同一塊。重傳的代價是**佔掉未來某一個 slot 的容量** —— 那個 slot 本來可以送新資料，被重傳吃掉了，於是排在後面的封包全部被往後推。所以重傳不是憑空多出一段延遲，而是**「偷走 slot」間接拖慢所有人**。這個「間接」是理解整件事的關鍵。

### 引擎用到的幾個時間參數

引擎模擬了真機的排程節奏：封包到達後要等 `k0_slots`（預設 2）才能被排（對應 PDCCH→PDSCH 的 offset 加處理時間）；首傳失敗後要隔 `harq_rtt_slots`（預設 4）才重傳（HARQ 的 NACK→retx 往返）；link adaptation 的目標是把首傳 BLER 壓在 `target_bler`（10%）；另外每個 slot 還疊一層 fast fading；RLC AM 層則限制一塊最多重傳 `MAX_RETX`（4）次。

### 逐 slot 在做什麼

引擎對每個 0.5ms slot 依序跑這幾步：先把到達滿 K0 的封包放進 FIFO 佇列；接著把等太久（超過 discardTimer）的從佇列頭丟掉；如果這格不是 TDD 的 DL slot 就跳過；**如果這格之前被某次 NACK 排了重傳，整格容量就讓給重傳、不送新資料**（這就是「偷 slot」）；否則就算這格的通道狀況推出 MCS、得到 TBS（這格能裝幾 byte），從佇列頭 drain 出去，某封包最後一 byte 送出時記下它的延遲；最後對這格送出的 TB 擲一次骰子決定成敗，失敗就在「這格 + 4」排一個重傳。

### 失敗機率從哪來：兩個 SINR 是精髓

這裡有個容易忽略但很關鍵的設計：**挑 MCS 跟判失敗，用的是不同的 SINR。**

- 挑 MCS 用的是**平均 SINR**（也就是 UE 回報的 CQI）—— link adaptation 看的是平均通道，把 MCS 停在約 10% 失敗率的操作點。
- 判這一格的 TB 成不成功，用的是**瞬時 SINR**（平均再加上這一格的 fast fading），餵進 BLER 曲線。

於是當某一格的瞬時 fading 比平均掉下去，那一格的 BLER 就升高、比較容易失敗。**失敗率不是寫死的 10%，而是「平均落在 ~10% 附近、隨每個 slot 的 fading 上下自然湧現」。** 這跟真機一模一樣：基站照平均通道選 MCS，但瞬時衰落讓某些塊偶爾失敗。

### 重傳怎麼算進 delay（重要細節）

引擎量的 delay 是 **HOL sojourn**，也就是封包從「到達」到「第一次被 drain 出去」的時間，**不包含這個封包自己的 HARQ 往返**。這是刻意對齊 OAI 的 `DRB_RlcSduDelayDl`（它定義上就是 waited_time，不含 HARQ ACK 來回）。

那重傳怎麼進到 delay？**間接地**：失敗的那塊 TB 會在 4 個 slot 後排一個重傳，那個 slot 被整個佔掉、不能送新資料，於是排在後面的封包多等了一格，它們的 sojourn 就變大。一句話：**失敗的封包不直接加自己的延遲，但它佔走的重傳 slot 拖慢了後面所有人。** 這正是為什麼 BLER 一高，整體 delay 就跟著高。

### 跨 tick 不歸零

因為重傳可能排到下一個粗 tick（「這格 + 4」超出本 tick 邊界），所以待重傳的 slot、沒排完的佇列、伺服器游標等狀態都會跨 tick 帶過去。這樣高負載時，backlog 和重傳佔用會持續累積、delay 隨之長高，而不是每個 tick 假性清零。

### 這個模型的簡化（誠實說明）

引擎抓住了重傳對 delay/PRB 的主要影響，但做了幾個簡化：一次失敗只排「一個」重傳 slot，不再對重傳本身判成敗、也不鏈式多次；沒有模 soft-combining（真機重傳會軟合併、降低再失敗率）；MAX_RETX=4 的丟棄是在 RLC AM 層（buffer/window 帳）做，slot 引擎這層不重判；重傳被簡化成「整個 slot 被佔掉」而非只重送失敗的片段。這些簡化保留了「重傳偷 slot、拖後面」這個主導效果，但不做位元級 HARQ。

---

## 三、BLER 從哪裡參考來：3GPP AWGN 錨點

上面那個「擲骰決定成敗」的機率，就是 BLER（Block Error Rate，首傳失敗機率）。它的來源分兩層。

**第一層（優先，但目前沒啟用）是真實量測 CSV。** 如果設了 `SIM_BLER_CURVE_PATH` 指向一個 `bler_curve.csv`（欄位是 `mcs, sinr_db, bler`），引擎就會查表加線性插值。這層是留給「你有真實 link-level 量到的曲線」（例如從 OAI nr_dlsim 或 Sionna 跑出來的）時直接掛上用。目前容器沒設這個路徑，所以走第二層。

**第二層（目前實際在用）是解析公式。** 沒有 CSV 時，BLER 用一條 erfc「水落曲線」算：`BLER = 0.5 · erfc((SINR − 該MCS門檻) / (1.5·√2))`。這條公式由兩個東西組成：一是每個 MCS 的「SINR 門檻」表，註解寫明它取自 **3GPP AWGN 各 MCS 在 10% BLER 的 SINR 門檻**；二是 σ=1.5 dB 的曲線陡度，這是標準的 waterfall 解析形狀。換句話說，它不是逐點抄某一張現成的 3GPP BLER 表，而是**取 3GPP/OAI 公認的「每個 MCS 在 10% BLER 的操作點」當骨架，再用 erfc 把曲線形狀補出來**。周邊的查表也都對齊標準：SINR→CQI 對齊 OAI 的 cqi_table2，SINR→MCS 對齊 3GPP TS 38.214 Table 5.1.3.1-2，TDD DL slot 比例對齊 OAI band78 的設定。

**為什麼錨在「10%」？** 因為 10% 首傳 BLER 正是 OAI / 3GPP link adaptation 的操作點（`target_dl_bler`）—— NR 的外環 link adaptation 就是把 MCS 停在約 10% 失敗率以最大化吞吐。所以用 10% BLER 的 SINR 當錨點，跟真機選 MCS 的邏輯是同一個點。

要特別澄清一個常見誤會：**10% 不是「固定重傳率」。** 它是挑 MCS 時瞄準的目標，不是結果被鎖死。實際每次傳輸的 BLER 是用 erfc 照當下 SINR 連續算的——SINR 比門檻高個幾 dB，BLER 可能只有 2% 甚至趨近 0%；SINR 掉到連最低的 MCS 都撐不住，BLER 會衝破 10% 一路往 100% 去、重傳暴增。link adaptation 只是在「好鏈路」時把 BLER 壓在 10% 以下（這是設計），鏈路一壞就遠超 10%。對比舊版：舊版用亂猜的 sigmoid，操作點落在約 50% BLER，等於不管鏈路好壞都狂重傳；新版錨在真實的 10% 操作點加連續 erfc，鏈路好就少重傳、鏈路壞才多重傳，才是物理該有的行為。

---

## 四、其他讓輸入更準的修正

除了 BLER/重傳，還有幾刀也是同一個精神——把輸入從「猜測 / 樂觀 / 過時 / 無上限」換成「真實 / 一致 / 即時 / 對齊 OAI」。

**scheduler 與 slot 引擎的 MCS 一致。** 以前 scheduler 配 PRB 時挑的 MCS，跟 slot 引擎實際送時用的 MCS 是各算各的，於是「以為能送這麼多、實際送不了」，配的 PRB 跟真正傳輸對不上、backlog 估算錯。修正後讓兩邊用同一個操作點 MCS（首傳 BLER ≤ 10% 裡最高的可行 MCS），而且呼叫同一條曲線，scheduler 配的 PRB 就跟實際送得出去的量一致了。

**retx-aware 的 PRB 需求。** scheduler 算「要幾個 PRB 才能清掉 backlog」時，舊版假設 100% 一次成功，於是少開 PRB、backlog 清不完、delay 虛高。修正後把 BLER 算進需求——有效容量 = 容量 ×（1 − BLER），為重傳預留資源，對齊 OAI 的 outer-loop link adaptation；另外設一個 PRB 下限，避免有 buffer 的 UE 被 PF 餓到 0 個 PRB。

**in-process SINR。** 以前 DU 要等 RU 用 HTTP callback 回 CQI，中間差一個 tick，等於用上一拍的舊 SINR 排程。修正後在 cached 模式下，DU 直接讀 channel cache 自己算 SINR、同一 tick 完成，且已驗證結果跟 RU 算的一致，省掉那一拍滯後。代價是它的正確性綁在 channel cache（precompute）上，邊界幾何下 SINR 可能翻負，跑前要驗 npz。

**achieved-speed 注入修正。** sim 設 2x 但跨容器開銷讓它實際只跑到約 1.9x，舊版仍按設定的 2x 注入流量，等於每秒多注約 5%，把 throughput 和 delay 都灌虛高。修正後改用 DU 實際量到的達成倍速來注入，量就跟實際跑速一致。

**RLC buffer 上限與丟棄計數。** 舊版 RLC AM 的傳送 buffer 上限沿用 OAI 預設的 50 MB，這對真機高 MCS 只是一秒級緩衝，但模擬常被 SINR 限在低 MCS（約 25 kbps drain），50 MB 會撐出小時級的假延遲（bufferbloat），加上 entity 跨 session 殘留沒清更嚴重。修正後對齊 OAI 的 tx_maxsize 檢查，把 buffer 設成有限上限，達上限就拒收新進的 SDU（不是 head-drop，對應 OAI 行為），並把被拒的計入 drop KPM，過載 delay 不再爆表、drop rate 也變真。

---

## 五、總結

slot 引擎能算出對的 delay/PRB/throughput，前提是餵進去的輸入是對的。這次改造把這些輸入逐一從假變真：重傳的失敗機率錨在 3GPP AWGN 的 10% 操作點、用連續 erfc 隨瞬時 SINR 湧現，而不是亂猜一個 50% 的固定點；重傳對 delay 的影響走「佔 slot、間接拖後面」的真實路徑，且狀態跨 tick 累積；scheduler 與引擎用一致的 MCS、並為重傳預留 PRB；SINR 即時、注入量按實際跑速、buffer 有界且丟棄可計。這一切的共同主軸只有一句話：**靠把物理參數校到跟 OAI 一樣讓數字自己對，而不是事後除一個係數。**

---

*對應 commit：`403ee40`、`51bdbaf`（RANsim-DU）。BLER 曲線來源：`main/apps/mac/services/optional/link_adaptation/mcs_controller.py`、`phy_high/.../coding/ldpc_abstract.py`；重傳邏輯：`mac/services/optional/slot_engine/slot_loop.py`；RLC buffer：`rlc/services/optional/entities/am_entity.py`。旗標狀態依 2026-06-10 `ransim-du` 容器實際 env。*
