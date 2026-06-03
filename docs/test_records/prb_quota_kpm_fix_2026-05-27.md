# PRB Quota KPM Fix — 2026-05-27

修復 xApp 下 RC PRB Quota 後 KPM `RRU.PrbTotDl` 報 100% 假爆的 bug;並驗證修完後 fix 在完整 ES 偵測 → RC 下發 → cap 生效鏈路上能正確報出物理 PRB%。

---

## 1. 觀察到的問題

xApp 下 E2 Control Style 2 / Action 6 (slice-level PRB quota) `max_prb=3%` 後,KPM `RRU.PrbTotDl` 報出來是 **100%**,跟 quota 限制行為矛盾:

- 預期:`max=3%` 限制 PRB 池 → 排程器最多分 cap 顆 PRB → KPM PRB% 應該 ≤ 3%
- 實際:KPM 直接報 100%
- 結果:RC/ES/CCO xApp 看到「我才剛限,反而看到 100%」會誤判 → 觸發錯誤決策

---

## 2. 根因分析(三層 bug 疊加)

### Bug 1 — PM aggregator 分母用 capped 容量

`RANsim-DU/main/apps/mac/services/optional/pm_aggregator/pm_aggregator.py:_CellWindowAccumulator`

`flush()` 內 `prb_pct_raw = prb_used_sum / n_prb_total_sum * 100`,**`n_prb_total_sum` 是 caller (tick_runner) 傳進來的 capped 容量**:

```
quota max=3% → cap_factor=0.03
cell_prb_total = max(1, int(prb_per_cell × 0.03))   = capped 容量
↓
PM aggregator 收到 (prb_used=cap, n_prb_total=cap)
↓
raw % = cap / cap = 100%
```

語意違反 3GPP TS 28.552 RRU.PrbTotDl 定義(分母是 cell 物理容量,不應受 quota 影響)。

### Bug 2 — `dump_pm` 出口同樣混淆

`tick_runner.py:683-688` 計算 `prb_pct_this_tick` 也使用 capped 分母,導致 Dashboard `/scenarios` 圖表跟 KPM 報的 PRB% 同樣失真。

### Bug 3 — PRB_OAI_CALIB ×10 線性放大 + clamp 100

`pm_aggregator.py:34` `PRB_OAI_CALIB=10.0`(2026-05-23 P1.11 加,為對齊 OAI rfsim normal phase)。

```
final_prb_pct = raw_pct × 10
clamp [0, 100]
```

- raw_pct ≤ 10% 時 ×10 還在合理區
- raw_pct > 10% 時 直接撞 clamp,報出 100% 失去區辨度
- xApp 看到 100% 無法分辨「中負載」「重負載」「真飽和」

文件 `oai_kpm_calibration_2026-05-23.md` 自己明寫:
> 取整 10 是經驗值,**不是物理常數**。
> Burst phase / 多 UE / 不同 BW 都「未驗證」,**比 delay calibration 不可靠**。

---

## 3. Fix 內容

### 改動 A — tick_runner 改傳物理容量

`RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py`

| Line | 改動 |
|---|---|
| ~415 | `accumulate_cell_tick(n_prb_total=cell_prb_total.get(...))` → `n_prb_total=prb_per_cell` |
| ~688 | `dump_pm` 內 `"prb_pct_this_tick": used / max(total,1) × 100` 改用 `prb_per_cell` 當分母 |

`quota_cap_factor` / `quota_max_prb_pct` 兩個欄位保留,xApp 想看 slice 限額仍可另外抓。

### 改動 B — PM aggregator 註解更新

`pm_aggregator.py:_CellWindowAccumulator` 註解明寫「`n_prb_total_sum` 必須是物理 capacity,不受 PRB quota 影響」。

### 改動 C — docker-compose 加 env 關掉 OAI calib

`docker-compose.yml` DU service:

```yaml
# 預設改回 1.0(raw 不校正),docs/test_records/oai_kpm_calibration_2026-05-23.md
# 對照測試前再切回 10.0。
PRB_OAI_CALIB: "1.0"
```

舊 env hook(`PRB_OAI_CALIB: float = float(_os.getenv("PRB_OAI_CALIB", "10.0"))`)沒動,跑 OAI 24hr 對照前一行 yaml 切回 10.0 + restart DU 即可。

---

## 4. 驗證流程

### 4.1 場景設計

修改 `es_1hr` scenario(透過 `Omniver-RAN/ScenarioController/upload` 覆寫 raw_json):

```json
"traffic": [{
  "ue_name": "es_ue_01",
  "profile": [[0, 5], [300, 2000]]
}]
```

- **Phase A**:sim 0-300s,5 kbps —— 觸發 ES xApp 三條件 AND
- **Phase B**:sim 300-600s,2 Mbps —— 流量暴增驗證 quota cap

### 4.2 觀察點

跑全程透過 v2 monitor 持續取樣 `/E2Adapter/KpmSnapshot/RecentReader/read`(xApp 視角的 KPM)+ DU `dump_pm`(內部 raw),交叉比對。

### 4.3 結果表

| 階段 | sim 時段 | PdcpSduVolumeDL | RRU.PrbTotDl | UEThpDl | PRB used/total | quota | ES 三條件 |
|---|---|---|---|---|---|---|---|
| 暖機 | 0-30s | 0 → 1253 byte | 0 → 0.09% | 0 → 10 kbps | 0 → 1 | none | ramp |
| Phase A 穩態 | 30-200s | ~1253 byte (10 kbit) | ~0.09% | ~10 kbps | 1/273 | none | ✅ 三條件 AND 全過 |
| xApp 偵測 fire | t≈sim 200-270s | 同上 | 同上 | 同上 | 同上 | none → **max=3%** | xApp 下 RC ✅ |
| **Phase B 切換** | sim 300s | **122756 byte (982 kbit)** | **2.93%** | **982 kbps** | **8/273** | max=3% | 兩條失效 |
| Phase B 穩態 | 300-600s | 122756 byte | **2.93% 卡 cap** | 982 kbps | **8/273 卡死** | max=3%(xApp 沒拆)| 失效 |

### 4.4 三項 fix 驗證對齊

| 驗證點 | 觀察 | 結論 |
|---|---|---|
| Quota cap 限到 8 PRB | `prb_used=8` 卡死 | ✅ |
| KPM PRB% 用物理 273 當分母 | 8/273 = **2.93%**(不是 100% 也不是 8/8=100%)| ✅ |
| 沒被 ×10 calib 灌到 clamp | 2.93% raw 直接輸出 | ✅ |

---

## 5. 旁觀察(留給 xApp / RIC 端)

### 5.1 S3A1 Handover Control 一直 fail

```
control_failure_sent S3A1 — ranP missing=[1] extra=[3]
```

xApp 每次 fire 動作時除了 S2A6(Slice Quota)還連帶送一筆 S3A1(HO Control),但 RC encoder 漏帶必填的 ranP IE id=1,**xApp 端 encoder bug,非平台問題**。

### 5.2 xApp 沒有「拆 quota」邏輯

Phase B 進入後 ES 三條件失效(Thp/Vol 都 ×350 暴增超門檻),按 ES 設計應該主動 clear quota,但實測 xApp 把 quota 從 phase A 一路留到劇本結束。

建議 xApp 加 inverse trigger:三條件 AND 從「全過」flip 到「至少一條 fail」→ send `clear_prb_quota`。

### 5.3 xApp 偵測 latency

從 sim 開始到 xApp 真的下 quota 大約等了 200-270s sim(配 KPM 累積 mean + decision hysteresis)。劇本至少要跑超過這個 window 才看得到 RC 觸發。

---

## 6. 留作未來工作

| 項目 | 描述 |
|---|---|
| OAI 24hr 對照 | 跑前需切 `PRB_OAI_CALIB=10.0` + restart DU;測完切回 1.0 |
| KPM 新 metric `RRU.PrbSliceQuotaUsage` | 用 capped 分母,跟 `RRU.PrbTotDl`(物理分母)並存,方便 xApp 看「slice 內占用率」 |
| pm_aggregator unit test | 加 quota=N% 場景下確認 raw % 對齊 `prb_used / physical_capacity` |

---

## 7. 改動檔案清單

```
RANsim-DU/main/apps/tick/services/optional/runner/tick_runner.py     # bug 1 + 2 fix
RANsim-DU/main/apps/mac/services/optional/pm_aggregator/pm_aggregator.py  # 註解
docker-compose.yml                                                    # PRB_OAI_CALIB=1.0
Omniver-RAN postgres scenario `es_1hr`                                # profile 改 [[0,5],[300,2000]]
```

---

## 8. 關聯文件 / memory

- `docs/test_records/oai_kpm_calibration_2026-05-23.md` — PRB_OAI_CALIB=10 推導與限制
- `~/.claude/projects/-home-mitlab/memory/oai_alignment_params.md` — DT 對 OAI 物理層校正
- `~/.claude/projects/-home-mitlab/memory/cached_sinr_bug.md` — 同類「KPM 出口錯」bug 旁證
