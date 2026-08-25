# RAN sim 容量掃描報告 — 無建築(自由空間)最大 gNB/UE 支撐量

> 測試日期:2026-08-06 11:44–11:57(12.5 分鐘,7 組態)
> 測試工具:`scripts/capacity_test.py`(可重跑),原始輸出:`/home/mitlab/capacity_test.log`
> 環境:16 vCPU / 47GB RAM / NVIDIA A40(KubeVirt VM),driver 580.173.02

---

## 1. 摘要(TL;DR)

**無建築 + live 模式(每 TTI 即時 Sionna)+ 1x 速度下:**

| 維度 | 上限 | 保守甜蜜點 |
|---|---|---|
| **UE** | 10~15 個(20 個開始跟不上)| **10 UE** |
| **Cell** | 8~10 個(12 個臨界)| **8 cell(4 gNB)** |
| **建議組態** | — | **10 UE × 8 cell**(實測 achieved 1.215,餘裕充足)|

兩個維度的瓶頸**不同**:UE 卡在 **DU 的 per-UE 成本**;cell 卡在 **Physics/Sionna 單核飽和**。

---

## 2. 測試方法

### 2.1 判準
上限定義為「跟得上」而非「爆掉」:

- `achieved_speed_x ≥ 0.95`(1x 目標;低於此值 KPM 時間軸開始失真)
- KPM 有效率 ≥ 90%(CONNECTED UE 中 rsrp 非空比例)

### 2.2 場景與流程
- **無建築**:detach 地圖,Physics 推空幾何(自由空間,Sionna 最輕負載)
- gNB 300m 網格散布,每 gNB 2 cell(0°/180°);UE 分配至最近 gNB,繞 80~130m 方形軌跡(3 m/s)
- 每組態:清場 → 建物件 → Start(live_db)→ 每 UE 掛 1 Mbps CBR → 靜置 45s → 取樣 3 次(間隔 10s)→ Stop
- 提前終止:achieved < 0.8 即停止該維度加碼

### 2.3 掃描矩陣
- Phase A:UE ∈ {5, 10, 20, 40},固定 2 cell
- Phase B:cell ∈ {4, 8, 12},固定 10 UE

---

## 3. 實測數據

### 3.1 Phase A — UE 掃描(固定 1 gNB / 2 cell)

| UE | achieved_speed_x | KPM 有效 | DU CPU | Physics CPU | 判定 |
|---:|---:|---:|---:|---:|---|
| 5 | 1.029 | 5/5 | 13.9% | 49.6% | ✅ PASS |
| 10 | 1.123 | 10/10 | 46.4% | 61.7% | ✅ PASS |
| **20** | **0.843** | 20/20 | **77.1%** | 53.3% | ❌ FAIL |
| 40 | 0.531 | 40/40 | 62.0% | 78.3% | ❌ FAIL(半速)|

### 3.2 Phase B — Cell 掃描(固定 10 UE)

| Cell(gNB)| achieved_speed_x | KPM 有效 | DU CPU | Physics CPU | 判定 |
|---:|---:|---:|---:|---:|---|
| 4(2)| 1.182 | 10/10 | 62.0% | 96.9% | ✅ PASS |
| 8(4)| 1.215 | 10/10 | 32.7% | **103.3%** | ✅ PASS |
| **12(6)** | **0.916** | 10/10 | 9.3% | **103.1%** | ❌ FAIL(臨界)|

---

## 4. 瓶頸分析

### 4.1 UE 上限 → DU 的 per-UE 線性成本
20 UE 時 DU 吃到 77% CPU。per-UE 成本來源:RLC entity 處理、PF 排程、per-UE KPM 聚合、slot engine。

**關鍵反證**:20 UE × 2 cell = 40 條 Sionna path 就 FAIL,但 10 UE × 8 cell = 80 條 path 卻 PASS
→ **瓶頸不是光追 path 數,是 DU 對 UE 數的線性成本。**

### 4.2 Cell 上限 → Physics 單核飽和
Physics CPU 卡死在 ~103%(**單一 Python process ≈ 一顆核**)。Sionna 呼叫在 Physics 端序列化(engine lock 防並發改 receiver),cell(TX)越多每次 compute 越重,8 cell 已satur、12 cell 開始拖累 tick(achieved 0.916)。

### 4.3 平台品質觀察
- **KPM 在所有組態(含 40 UE 半速)都 100% 有效** —— 超載時「只會慢、不會產生壞資料」,KPM 語意可信。
- 超載表現為 achieved_speed_x 線性下滑(20 UE→0.84、40 UE→0.53),無崩潰、無資料遺失。

---

## 4.4 補充實驗:gNB 分組對照(cell 才是成本單位)

固定 **8 cell + 10 UE**,只變 gNB 分組方式:

| 分組 | achieved_speed_x | Physics CPU | DU CPU | 判定 |
|---|---:|---:|---:|---|
| 8 gNB × 1 cell | 1.052 | 103.4% | 27.9% | ✅ |
| 4 gNB × 2 cell | 1.062 | 103.0% | 9.2% | ✅ |
| 2 gNB × 4 cell | 1.194 | 102.1% | 22.1% | ✅ |

三組全 PASS,**Physics 都卡在同一個 ~103% 單核天花板**,achieved 差異(1.05~1.19)
在 run-to-run 變異範圍內(同組態不同輪實測過 1.06 vs 1.22)。

**結論:容量預算以「cell 總數」計,gNB 怎麼分組無關緊要。**
每個 cell = 一支獨立 Sionna TX + 一個 DU 排程迴圈;gNB 只是管理容器。

---

## 5. 擴容方向(若需更高容量)

| 手段 | 預期效果 | 代價 |
|---|---|---|
| **cached 模式**(precompute npz)| 拔掉 Physics → cell 上限大幅解放;UE 上限估可到 20~30(DU 成本仍在)| 需 per-scenario precompute;動態場景不適用 |
| **降速跑**(0.5x)| 容量約 ×2(wall tick 放寬一倍)| 模擬變慢 |
| DU per-UE 迴圈優化 | 直接抬高 UE 上限 | 工程改動(tick_runner/PF/PM)|
| Physics 多實例/多核 | 抬高 cell 上限 | Sionna engine 架構調整 |

---

## 6. 附註與侷限

- 本測試為 **live 模式**;劇本高倍速(cached)容量未測,預期顯著更高。
- 「無建築」為最輕光追負載;有建築(如 NTUST 254 棟)時 Sionna 每次 compute 變重,**cell 上限會更低**,UE 上限(DU-bound)影響較小。
- 斷點精度:UE 上限落在 10~20 之間、cell 上限落在 8~12 之間,如需精確值可用同工具二分細掃。
- 每組態靜置 45s + 3 樣本;更長時間的穩定性(如 30 分鐘)未在本輪驗證。

## 7. 重跑方式

```bash
nohup setsid python3 /home/mitlab/XAPP_DT/scripts/capacity_test.py \
  > /home/mitlab/capacity_test.log 2>&1 &
# 進度:tail -f /home/mitlab/capacity_test.log
```
掃描範圍改 `capacity_test.py` 底部的兩個 for 迴圈即可。
