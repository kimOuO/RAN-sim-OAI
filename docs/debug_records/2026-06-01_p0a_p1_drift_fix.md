# P0a + P1 修復:消除「設定 vs 實際達成」漂移造成的過量注入

> 產出日期：2026-06-01
> 對應問題：sim 倍速漂移(設定 10x 實際 6.7x)→ traffic_gen 用設定值灌 → 1.49× 過量注入
>          → throughput / buffer / delay 失真。根因見 [[bottleneck 診斷]] 的 ③a。

---

## 改了什麼(只動「時間記帳」,不動 MAC/RLC/scheduler 數學)

### P0a — DU 暴露「實際達成倍速」achieved_speed_x

`sim_speed_x` 是設定值(`sim_dt/wall_tick`),但 loop 在負載下 body 塞不進 wall_tick
時實際跑不到。新增 `achieved_speed_x` = 近 ~1s 內 tick_count 真實增長率換算 —— 唯一
誠實的「sim-time 跑多快」來源。

| 檔案 | 改動 |
|---|---|
| `RANsim-DU/.../tick/services/optional/runner/tick_runner.py` | 加 `_achieved_speed_x` 欄位 + `achieved_speed_x` property + `_update_achieved_speed()`(loop 每輪呼,每 ~1s 重算)+ start() 重置視窗 |
| `RANsim-DU/.../tick/actors/tick_controller_actor.py` | `read` (`_status_dict`) 與 `dump_pm` 輸出加 `achieved_speed_x` |
| `RANsim-DU/.../tick/serializers/tick_state_serializers.py` | serializer 加 `achieved_speed_x` 欄位 |

→ 純加,零行為改變。`POST /DU/Tick/TickController/read` 現在回 `achieved_speed_x`。

### P1 — UE traffic_gen 用 achieved 而非設定值算注入量

| 檔案 | 改動 |
|---|---|
| `RANsim-UE/.../ue_lifecycle/services/sim_speed.py`(新) | 背景 poll DU `achieved_speed_x` 的 cache(鏡像 e2adapter/CU 的 sim_speed.py pattern,lazy-start daemon,每 1.5s 刷新) |
| `RANsim-UE/.../ue_lifecycle/services/traffic_gen.py` | 新增 `_effective_sim_speed_x()`(achieved>0.1 用 achieved,否則 fallback 設定值);`_current_rate_mbps`(piecewise schedule)與 `tick()`(注入量)兩處改用它 |

**安全護欄**:3x 無漂移時 achieved == 設定 → effective == 設定 → 注入量位元級相同
→ 不破壞已在 3x 擬合的 OAI 校正。只有高倍速漂移時才修正過量注入。

### P1-out — KPM 送出頻率也改用 achieved(輸出側鏡像)

輸入側(inject)修了,輸出側(KPM 送 RIC)有同款 bug:CU `indication_producer`
用 `period_ms / speed` 算送出節奏,而 `speed` 來自 CU `sim_speed.get_speed()` —— 過去
cache 的是 DU 的設定 `sim_speed_x`(10),不是 achieved(6.7)。設定 10 → 每 100ms 送,
但新 KPM 每 149ms(=1000/6.7)才來 → 過量送出 ~1.49×(含 1/3 重複)。

| 檔案 | 改動 |
|---|---|
| `RANsim-CU/.../e2/sim_speed.py` | `_refresh_from_du` 改 cache `achieved_speed_x`(fallback 設定值),producer/e2adapter 自動跟上 |

→ 性質比 inject 輕傷:**不污染 KPM 數值**(每筆都是 CU 當下真值),只是冗餘 + 頻率失真。
e2adapter pull CU speed → 自動修正,不用改。

---

## 實測驗證(es_1hr,traffic 窗 sim 720-1020)

| 指標 | 修復前 10x | **修復後 10x** | 3x baseline | 真值 |
|---|---|---|---|---|
| throughput | 2.94 Mbps (+47% 失真) | **1.94 Mbps** ✓ | 1.94 | ~2.0 |
| buffer avg | 245 KB | **167 KB** ✓ | 167 | — |
| achieved_x | 6.73(反推) | **6.94(P0a 直讀)** | ~3.0 | — |
| delay | 58.8 ms | 56.6 ms | 30 | (③b 未修) |

**過量注入完全消除** —— 10x 下 throughput / buffer 回到與 3x 相同的真值。
delay 沒同步降是預期(③b 時基問題刻意延後)。

**3x 回歸測試(關鍵安全驗證)** — 修復前後位元級相同,OAI 校正未破壞:

| 指標 | 修復前 3x | 修復後 3x | 差異 |
|---|---|---|---|
| achieved_x | (無此欄) | 3.00x = 設定 3 | 零漂移 |
| throughput | 1.94 Mbps | 1.99 Mbps | +2.5%(噪音) |
| delay | 29.9 ms | 30.4 ms | +1.7%(噪音) |
| buffer | 167 KB | 170 KB | +1.8%(噪音) |

差異全在 run-to-run 噪音(fast-fading 隨機相位 + 取樣抖動)範圍內。

**P1-out 驗證(KPM 送出頻率)** — 10x 下 CU KPM speed 是否跟 achieved(而非設定 10):

| | 設定 | DU achieved | CU KPM speed | 吻合 |
|---|---|---|---|---|
| 穩態(wall>35s) | 10.0 | 6.99 | **7.02** | 100.3% ✓ |

producer 改用 achieved → 每 ~143ms 送一筆(對上數據速率),過量送出/重複消除。
注:前 30s CU 顯示 10.0 是 orchestrator 啟動 `KpmSpeed/set(10)` 的 30s override TTL
(既有行為,且 es_1hr 前 30s idle 無 traffic,無害)。

---

## 刻意「沒做」的部分(避免重蹈 _OAI_SLOT_MS 覆轍)

**P0b — delay 改 sim-time 原生量測:延後。**
segmenter 現在用 wall-clock 算 delay,再經 `_DELAY_CALIB`(`/30` 等擬合標量)校正成
對齊 OAI。改 delay 時基 = raw 值變 = 擬合校正全錯 → 必須重跑整個 OAI 對齊。這跟
[[oai_slot_delay_calib_dont_touch]] 是同一個耦合,不可單獨改。

→ 這也是為什麼修復後 delay 數字沒降:throughput/buffer 走的是「注入量」路徑(P1 修了),
delay 走的是「wall 量測 × 擬合校正」路徑(P0b 沒碰)。要讓 delay 也誠實,得做 P0b +
重新擬合(屆時 `/30`、`_OAI_SLOT_MS` 那串可一併退役,改用真實物理:OAI slot 0.5ms vs
DT tick sim_dt)。

---

## 影響

- **解開「安全倍速」綁手綁腳**:過去只能壓到 3x 躲漂移(犧牲壓縮比);現在高倍速下
  throughput/buffer 不再失真。delay 仍受 ③b 限制,要全面可信還需 P0b。
- **可觀測性**:`achieved_speed_x` 上線 → 監看工具 / Dashboard 可直接顯示漂移,不必再
  從 tick_count 手算。

## 關聯
- `docs/debug_records/2026-06-01_oai_slot_delay_calib_dont_touch.md` — 為何 P0b 不能草率做
- `docs/test_records/full_day_24hr_3x_kpm_v7_2026-05-25.md` — OAI 校正在 3x 擬合的證據
