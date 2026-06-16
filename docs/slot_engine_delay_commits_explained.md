# RANsim Slot 引擎與 Delay 模擬 — 介紹

這份文件介紹 RANsim-DU 如何把 **delay / throughput / PRB / SINR** 的模擬，從「粗 tick + 硬除係數」升級成「0.5ms slot 級的物理引擎」，目標是讓模擬數字能誠實對齊真機 OAI rfsim。文中會一路說明：delay 本質上是怎麼算的、原本的做法錯在哪、新的 slot 引擎怎麼運作、模擬裡「送出封包」到底是什麼意思、目前實際開了哪些功能、以及離「真正對齊 OAI」還差什麼。

---

## 一、問題從哪來：為什麼模擬的 delay 不可信

RANsim 為了效能，是用**粗 tick**在跑的 —— 一個 tick 大約 250ms，程式每跑一輪就推進 250ms 的模擬時間。但真實 5G NR 的排程單位是 **0.5ms 一個 slot**，比 tick 細了 500 倍。

用粗 tick 直接算 delay，物理上是假的：一個封包中途到達，模型卻只能在 tick 邊界（每 250ms）才「服務」它，於是算出來的 delay 被量化成 250ms 的倍數，數字大到不合理。舊版的解法是套一個 **`÷30` 的 fudge 係數**，把這個過大的數字硬除小，讓它看起來接近 OAI 的次毫秒延遲。

這招的問題是：**數字對了，但物理是假的。** `÷30` 是針對某一個操作點湊出來的魔術常數，一換場景或負載就崩，沒有可信度，也無法推廣到不同情境（IM / CCO / ES）。會被鎖死在粗 tick，根因是跨容器 HTTP per-tick 把「時間粒度 × 模擬速度」綁死了。

整個改造的核心理念，就是**把「湊輸出」換成「修輸入」**：與其事後除一個係數，不如把 slot 級的物理（0.5ms 排程、MCS、PRB、SINR）建對，讓正確的 delay 數字**自然浮現**出來。

---

## 二、delay 到底是什麼、怎麼算出來

最重要、也最容易誤解的一點：**delay 的定義從頭到尾沒變過 —— 永遠是「離開時間 − 進來時間」。**

- **進來時間（arrival）**：流量產生器（`traffic_gen`）把這個 SDU 注入佇列的那一刻，直接給定。
- **離開時間（departure）**：這個 SDU 被送出去的那一刻 —— 這個值不是天上掉下來的，要靠引擎算。

**改造前後，差別只在「離開時間怎麼算」：**

| | 原本（÷30 calib） | 後來（0.5ms slot 引擎） |
|---|---|---|
| 服務粒度 | 只在粗 tick（250ms）邊界服務 SDU | 逐 0.5ms slot 服務 |
| 「離開時間」怎麼來 | 量化到 tick，數字約 30 倍太大，再硬除 30 湊小 | 一格一格 drain，SDU 最後一個 byte 送出去的那個 slot，就是離開時間 |
| delay 公式 | `(粗 tick 算的 delay) ÷ 30`（fudge） | `離開 − 進來`（離開由 slot 引擎算） |
| 對齊 OAI 的方式 | 調一個魔術係數（湊輸出） | 校物理參數 PRB / MCS / SINR / TDD（修輸入） |
| 換場景 | 崩（係數不通用） | 自洽（物理通用） |

這裡要特別澄清一個常見誤會：**「0.5ms slot」不代表 SDU 要等很久。** 250ms 是 tick（程式跑一輪的單位），0.5ms 是 slot（模型裡無線電排程的單位），兩者是不同層級。舊的粗 tick 才是「只能在 250ms 邊界服務」，所以 delay 被量化得很大、需要 ÷30。新的 slot 引擎，是在**同一個 tick 的計算裡，把約 500 個 0.5ms slot 在程式碼裡瞬間跑完**；一個中途到達的 SDU，在**下一個能塞得進去的 0.5ms slot** 就被服務，不必等整個 250ms tick。所以新做法不是「加速」delay，而是把 250ms 的量化假象拿掉，把真實的延遲**正確還原**出來。模擬器的牆鐘（wall-clock）時間沒變，變的是模型內的時間用 0.5ms 在走，delay 才有 slot 級的物理意義。

那為什麼前面又會列出「`PRB × MCS → TBS × TDD × retx × discard` 逐 slot 算」？這串東西**不是另一個 delay 公式，而是「算出離開時間的那台機器」**。`delay = 離開 − 進來` 是定義；離開時間什麼時候發生，得靠這台機器一格一格把佇列 drain 出去才知道。

---

## 三、slot 引擎逐 slot 在做什麼：模擬裡的「送出封包」其實是記帳

要理解離開時間怎麼算出來，先要打破一個直覺：**模擬器裡「送出封包」不是真的發射無線電訊號，而是記帳。** RANsim 沒有真實 payload，`traffic_gen` 注入的是合成的 byte 量；所謂「送出」，就是把 byte 數從緩衝區扣掉、並蓋上時間戳。

slot 引擎每個 0.5ms slot 做四件事：

1. **scheduler 配 PRB** —— 決定這個 UE 這個 slot 拿到幾個 resource block（頻寬單位）。
2. **算 TBS** —— 由 SINR/CQI 推出 MCS，再查表得到 TBS（transport block size），也就是「這些 PRB 在這個 slot 能裝幾個 byte」。
3. **drain 佇列** —— 從 FIFO 佇列頭部扣掉最多 TBS 個 byte（只在 TDD 的 DL slot 才送）。
4. **蓋離開時間戳** —— 當某個 SDU 的最後一個 byte 被 drain 掉，這個 slot 的 sim-time 就是它的「離開時間」，delay 隨即 = 離開 − 進來。

所以同一個「離開 − 進來」公式，delay 大小完全取決於這台機器把「離開」推到多遠：

- **輕載**（PRB 多、MCS 高）：每 slot 能送很多 byte，幾個 slot（幾毫秒）就 drain 完 → delay 小。
- **重載**（例如 ES 場景只有 8 個 PRB）：每 slot 的 TBS 很小，要很多 slot 才 drain 完，前面還排隊 → delay 大。
- **過載**：等太久的 SDU 會被 discardTimer 直接丟掉（不算送出）→ delay 被封頂。

引擎還把兩個真機行為算進去，讓「離開時間」更真實：

- **retx-aware PRB**：HARQ 重傳也會佔掉 slot 與 PRB。舊版 PRB 只算首傳，會低估真實用量；算進重傳後，PRB% 與真機更接近，也讓有效的新資料吞吐更真。
- **RLC discardTimer**：SDU 在佇列裡等超過設定時間（本機設 300ms）就丟棄。這對齊真機 RLC 的行為，避免過載時報出「無窮排隊 42 秒」這種爆表假延遲。

---

## 四、讓輸入更真的兩個配套

delay 算得準不準，取決於餵進引擎的輸入準不準。兩個配套修正讓輸入更貼近真機：

- **in-process SINR**：以前 DU 要等 RU 用 HTTP callback 回 CQI，會多出 1 個 tick 的滯後。改造後，DU 在 cached 模式下**直接讀 channel cache 自己算 SINR**（同一 tick 內完成，省掉那個延遲），而且已驗證結果與 RU 算的一致。這正是這次跑 cco cached 場景所走的路徑。代價是它的正確性綁在 channel cache（precompute）上 —— 邊界幾何下 SINR 可能翻負，跑前要驗 npz。

- **achieved-speed 漂移修復**：sim 設 2x，但跨容器 HTTP 開銷會拖累，實際往往只跑到 ~1.9x。舊版按「設定的 2x」算流量注入量，等於注太多（過量注入），把 delay 灌虛高。修正後改用 DU 實際量到的 `achieved_speed_x` 來注入，量就對了。（注：DL 注入量已對齊，但 delay 的時基還有未動到的部分。）

---

## 五、怎麼安全地把新引擎接上線：shadow 與 takeover

新引擎一開始不能直接驅動真實 KPM —— 因為它誠實算出來的 delay 反而**比 OAI 高**，還沒校準，貿然上線會把報表搞壞。所以設計了兩段式開關：

- **shadow（影子模式）**：slot 引擎照算，但**不餵 KPM**，真實 KPM 還是走舊路徑。它的用途是**安全驗證** —— 讓新引擎在旁邊跟著跑、收集數據去跟 OAI 比對，確認對齊後再轉正。這是降風險手段，不是物理修正。
- **takeover（接管）**：開啟後，delay KPM 真的改由 slot 引擎逐 SDU 的 sojourn 來算，退掉舊的 ÷30。

簡單說：shadow 是「先在旁邊跑、比對」，takeover 是「確認 OK 後正式接手」。

---

## 六、現在實際在跑什麼（重要：別只看 code 預設）

這點要特別講清楚，因為很容易誤判。**程式碼裡這些開關的「預設值」大多是關的，但實際在跑的 `ransim-du` 容器把它們覆寫開了。** 兩者不一樣：

| 開關 | code 預設 | 本機容器實際 | 意義 |
|---|---|---|---|
| `RLC_DELAY_MODEL` | `calib` | `calib`（關） | subtick 那條 FIFO 解析模型沒開；delay 走下面的 slot 引擎 |
| `SLOT_ENGINE_TAKEOVER` | `False` | **`on`** | slot 引擎正在接管 delay KPM（已非 ÷30） |
| `SLOT_ENGINE_SHADOW` | `False` | **`on`** | 收集 SDU arrivals 餵給引擎 |
| `DU_RU_INPROCESS` | `False` | **`on`** | cached 路徑，DU 直讀 cache |
| `DU_INPROCESS_SINR` | `False` | **`on`** | in-process SINR 啟用 |
| `SLOT_DISCARD_TIMER_MS` | `300` | `300` | RLC discard 門檻（ms） |
| `_OAI_SLOT_MS` | `1.0` | `1.0` | 物理上應是 0.5ms，目前被舊校準吸收（見第七節） |

**結論是：這台機器上，slot 引擎是真的在用、而且正在驅動 delay KPM。** 七項裡只有 subtick 那條（`RLC_DELAY_MODEL`）關著 —— 因為它跟 slot 引擎是兩條不同的 delay 路徑，這台機器選了 slot 引擎那條。你跑 cco 看到的 delay 數字，就是 slot 引擎逐 SDU 算出來的，不是除出來的。

---

## 七、離「真正對齊 OAI」還差什麼：0.5ms 是必要、但不充分

最後要誠實面對一個問題：**「用 0.5ms 在內部算」就等於符合 OAI 了嗎？答案是：方向對、機制對，但數值還沒到。**

0.5ms slot 引擎是「能誠實對齊 OAI 的必要條件」—— 它讓 delay 從真實物理浮現，而不是硬除。但要讓 magnitude 真的等於 OAI，還得讓**餵進引擎的每一個輸入也都對齊 OAI**：PRB 分配、MCS→TBS 表、SINR、TDD pattern、retx 行為，每一個都要對，delay 才會對。目前卡在這些地方：

- **瓶頸已從 delay 模型轉移到 scheduler。** ES 場景實測 delay 仍約 4.4 倍於 OAI，但這不是引擎算錯，而是 **PF scheduler 只配給 ES UE 約 8 個 PRB**（一個 cell 有 106 個）。PRB 給太少 → 每 slot 的 TBS 很小 → 佇列 drain 很慢 → delay 被餓得很高。引擎只是忠實地把這個「被餓出來的高 delay」報出來。所以下一刀要砍的是 scheduler 的配給策略，不是 delay 模型。

- **`_OAI_SLOT_MS = 1.0` 是顆未爆彈。** 物理上 band78 的 slot 應該是 0.5ms，但目前這個值被舊校準吸收成「剛好對」；要改成 0.5 必須跟整條 delay 校準一起動，單獨改會破壞既有對齊。

- **subtick 那條仍關著。** 它誠實算出來比 OAI 高，還在校準階段，所以目前 delay 走 slot 引擎而非 subtick。

- **其他**：delay 時基（P0b）還沒一起對齊；full_day @2x 對 OAI 的六個相位多數準（約 99/96/102%），但 IM 偏低（~73%）、EVE 偏高（~209%）；in-process SINR 的準確度綁在 channel cache 的正確性上。

---

## 八、總結

舊做法是「粗 tick 把 delay 量化到爆大，再除 30 假裝對」—— 數字對、物理假，換場景就崩。新做法是建一個 0.5ms 的 slot 引擎，逐 slot 用 `PRB → MCS → TBS` 把佇列 drain 出去，配上 retx、discardTimer、in-process SINR，讓 delay（= 離開 − 進來）、PRB、throughput 在 slot 層自洽，靠校物理參數對 OAI，而不是硬除係數。

這套東西在本機是真的開著在用（takeover 已接管 delay），只有 subtick 那條備援路徑關著。它把「對齊 OAI」的方式從「調一個 fudge」升級成「校一組物理參數」，地基已經鋪好；但最後一哩的數值對齊還卡在 scheduler 配 PRB（ES 4.4x）和幾個參數校準上 —— 那些修完，magnitude 才會真正等於 OAI。

---

*對應 commit：`403ee40`（sim-time honesty：achieved-speed 修復 + sub-tick delay 模型）、`51bdbaf`（slot engine：retx-aware PRB + RLC discardTimer + in-process SINR + takeover）。旗標狀態依 2026-06-10 `ransim-du` 容器實際 env。設計細節另見 `RANsim-DU/docs/plan/in-process-slot-engine.md`、`scheduler-mcs-consistency.md`。*
