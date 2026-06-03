# 為什麼 `_OAI_SLOT_MS=1.0` 不能單獨改成 0.5(待查 → 已查結論)

> 產出日期：2026-06-01
> 對應檔：`RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py:321`
> 觸發問題：「OAI 的 scheduler tick 是不是 1ms?」→ 發現 sim 裡假設寫錯 → 查能不能改

---

## TL;DR

- **物理事實**：真實 OAI 的 MAC scheduler 是 **per-slot** 跑(`gNB_dlsch_ulsch_scheduler(frame, slot, …)`），slot 長度 = `1ms / 2^μ`。你的 band78 conf `subcarrierSpacing = 1` → **μ=1 → slot = 0.5ms**,不是 1ms。(1ms 是 μ=0 / 15kHz,或 LTE TTI 的直覺。)
- **sim 裡寫錯**：`tick_runner.py:321 _OAI_SLOT_MS = 1.0`，註解（:304）也寫「OAI slot 1ms」。對 band78 物理上錯了 2×。
- **但不能單獨改 1.0 → 0.5**：這個值已被經驗擬合的 `/30` 因子「吸收」。單獨改會把 v7 唯一的 ⭐⭐⭐ delay 對齊（normal-1 16.91ms ≈ OAI 14.4ms）直接砍半成 ~8.5ms，**從對的變成錯的**。

---

## 鐵證（來自 `full_day_24hr_v7`，sim_dt=250ms）

delay 校正邏輯（P1.15，`tick_runner.py:324-327`）：
```python
if _bo > 50000:  _DELAY_CALIB = _OAI_SLOT_MS / 30.0      # 高流量分支
else:            _DELAY_CALIB = _OAI_SLOT_MS / _SIM_DT_MS  # 低流量分支
```

normal-1（195 kbps 持續累積，bo 過門檻）走**高流量分支**：
```
reported = raw × (_OAI_SLOT_MS / 30) = raw × (1.0/30) = 16.91ms ≈ OAI 14.4ms ⭐
改 0.5:  raw × (0.5/30)              =  8.46ms          → 對齊 117% → 59% ✗
```

`/30` 不是物理推導 —— 註解自己寫「8.3× scaling」，是凹出來對齊 14.4ms 的**純擬合標量**。`_OAI_SLOT_MS=1.0` 是這個乘積裡的因子，兩者一起被 fit。抽掉一個，另一個就露餡。

---

## 三個選項

| 選項 | 動作 | 結果 |
|---|---|---|
| **A（推薦）** | 什麼都不動 | `1.0` 在數值上「錯得剛好」，`/30` 為配它而凹。動它只有壞處。 |
| **B（純正名）** | `_OAI_SLOT_MS 1.0→0.5` **同時** `/30→/15`（低流量分支同理補） | 乘積完全不變（0.5/15 = 1.0/30），純 refactor，讓常數反映 band78 物理、註解不再誤導。**零準確度收益。** |
| **C（禁止）** | 只改 `1.0→0.5`、不動 `/30` | **破壞 normal-1 對齊**，唯一的錯誤選項。 |

---

## 更深的 takeaway

整個 `_DELAY_CALIB` 不是物理模型，是一串手調擬合標量（`/30`、`50000` threshold、phase-aware 分支），v7 自己都還在追 v8、normal-2 過頭到 310%。這印證了 [[bottleneck 診斷]] 的 ③b：**delay 度量沒建在健全時間基底（wall/sim 混用），只好用經驗標量補。**

→ 真正根治是 **P0：單一 sim-clock，delay 用 sim-time 原生量測**。那時才能用真實物理關係（OAI slot 0.5ms vs DT tick sim_dt）做校正，`_OAI_SLOT_MS=0.5` 才會變成有意義、可信的常數，而不是凹 `/30`。

---

## 關聯
- `docs/test_records/full_day_24hr_3x_kpm_v7_2026-05-25.md` — delay 對齊數據來源
- `docs/test_records/oai_prb_calc_evidence_2026-05-23.md` — OAI 原始碼證據鏈
- `tick_runner.py:300-327` — delay calib 實作
- OAI: `common/utils/nr/nr_common.c:1344` (`num_slots_subframe = 1<<mu`)、`openair2/LAYER2/NR_MAC_gNB/gNB_scheduler.c:147`
