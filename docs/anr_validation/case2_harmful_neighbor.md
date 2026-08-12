# ANR 驗測 Case #2:有害鄰區(Harmful Neighbor)— sim 重現 + xApp 觀測

> 目標:重現 `ANR情境_v8.docx` 第 7 題「有害鄰區」— 某鄰區關係**存在**、訊號看似可換,
> 但換過去**接入一直失敗**(掉 UE 體驗),需 RIC xApp 用 ANR API **FLAG hoBlocklist 止血**。
> 日期:2026-08-12。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

---

## 1. 問題(Problem)

**有害鄰區**:`src_c0 → nbr_c0` 關係存在(NRT 有),但每次 A3 觸發換手到 nbr_c0
**接入都失敗(RandomAccessProblem)** → UE 留原 cell、體驗掉、反覆重試。反向 `nbr_c0 → src_c0` 健康。
對應題型:第 7 題。

| 拓樸 | 值 |
|---|---|
| `src_c0` | gnb=src, pci=20, arfcn=633333 |
| `nbr_c0` | gnb=nbr, pci=30, arfcn=633333 |
| NRT | `[src_c0↔nbr_c0]`(關係在,非缺漏)|
| UE | hu0-4,src_c0↔nbr_c0 之間連續震盪穿越 |

---

## 2. sim 能力補齊(force-fail 注入)

sim 原本 HO 只在「target RSRP 過弱 / cell 關閉」時失敗,做不出「訊號 OK 但接入壞」的有害鄰居。
補一個**忠實重現用**旗標(`handover_executor.execute_f1_handover`):

```
env HO_FORCE_FAIL_TARGET="nbr_c0"        # 逗號分隔可多 cell
env HO_FORCE_FAIL_CAUSE="RandomAccessProblem"  # 預設值
→ 凡 HO target 命中清單 → 一律 status=FAIL, failure_cause=該 cause, 不改 serving_cell
```
docker-compose CU 段設 `HO_FORCE_FAIL_TARGET: "nbr_c0"`。
⚠️ **compose env 改動要 `docker compose up -d cu` 重建才生效**(`docker restart` 不會套)。

## 3. 劇本 `anr_harmful_neighbor`

hu0-4 連續震盪穿越 src_c0↔nbr_c0(承 Case #1 震盪波形)→ A3 反覆觸發 src_c0→nbr_c0 →
每次強制失敗 → failCause 持續累積。A3:offset 1.0 / hys 0.5 / ttt 80ms。

---

## 4. 症狀觀測(func6 `ho_kpm` perNeighbourRelation,window 10min)

| 關係 | att/min | succ(last50) | failCause |
|---|---|---|---|
| **src_c0 → nbr_c0** | 3.4 | **0.52** | **RandomAccessProblem 2.4/min(累計 24↗)** |
| nbr_c0 → src_c0 | 1.6 | 0.90 | {}（健康) |

**特徵 = 單向 succ 塌 + failCause 持續累積,反向健康** → 有害鄰居簽章。累計持續成長 = sustained。

---

## 5. xApp 閉環(RIC:dt-anr-xapp anr_guard,10s poll)

| 步驟 | 動作 |
|---|---|
| ① 觀測 | 讀 func6 `kpmIndication` perNeighbourRelation |
| ② 診斷 | 某 (src→dst) `MM.HoExeSuccRatio_last50` < 0.6 且 `handoverFailureCauseRatePerMin` 持續 > 0 → 有害鄰居(RIC 另加 samples≥10、att≥0.5 防抖)|
| ③ 止血 | `SONTRIG_ANR_FLAG(src_c0, nbr_c0, flag=hoBlocklist, op=set)` |
| ④ 驗證 | FLAG 後 A3 略過 nbr_c0 → src_c0→nbr_c0 不再嘗試、無新 FAIL |
| 保護 | 同 (src,dst) 300s cooldown;必要時 op=clear 復原 |

---

## 6. 閉環時間軸(2026-08-12 07:45 UTC)

```
07:45:23  anr_guard 啟動(poll=10s, cooldown=300s)
07:45:33  DETECT harmful: src_c0→nbr_c0  succ=0.0 att=5.8/min RandomAccessProblem=5.1/min  ← 診斷條件全中
07:45:38  FLAG hoBlocklist=set 送出
07:45+    NRT: src_c0→nbr_c0 v1→v2 hoBlocklist=True（反向 nbr_c0→src_c0 保持 False,對照組未動)
          adapter: ANR RIC_CONTROL_ACK sent (22 bytes)
```
偵測到止血:**10 秒(一個 poll 週期)**。

---

## 7. 止血驗證(Result)

| 指標 | FLAG 前 | FLAG 後(+105s) | 判讀 |
|---|---|---|---|
| RandomAccessProblem 累計 | 持續↗（24→51) | **凍結 51** | ✅ 不再有新接入失敗 |
| nbr_c0 HO FAIL 累計 | 持續↗ | **凍結 51** | ✅ A3 不再嘗試換到 nbr_c0 |
| att/min（10min 窗) | 3.4 | 5.0→3.6 緩降 | 窗內舊嘗試殘餘,無新增 → 隨窗滑出 |
| NRT flag | ho_blocklist=False | **v=2, ho_blocklist=True** | ✅ 反向 v=1/False 未動(對照組)|

**核心止血成立**:重複接入失敗(RandomAccessProblem)**完全停止累積** = 有害鄰居出血點止住。

**誠實註記**:近 1 分 RLF 穩在 ~2/min(未歸零)。blocklist 把「HO 撞失敗」換成「UE 留 src_c0」,
當 nbr_c0 變主導伺服而 src_c0 衰落時少數 UE 會走 RLF —— FLAG 本質權衡(擋有害換手 ≠ 提供好鄰居)。
Case #2 目標(止住反覆接入失敗)已達成;要連 RLF 也壓下需後續「ADD 替代 target」動作,不在有害鄰區止血範疇。

---

## 8. 已知小瑕疵(不影響閉環)

- rc-probe `wait_ack` 回報 timeout(ACK 未在 5s 內回到等待處)。但 sim adapter 已送 ACK(22 bytes)
  且修復成功(version+1、flag=True 為鐵證)。屬 RIC 端回報通道問題(rc-probe 剛重啟 forward hack
  instance map 對不上),非 sim 端。

---

## 9. 結論

**「發現(perNeighbourRelation succ 塌 + failCause 累積)→ 診斷(succ<0.6 且 failCause 持續)
→ FLAG hoBlocklist 止血 → 觀察(接入失敗凍結、A3 skip)」整條由真的 RIC xApp 自動跑通。**

Case #2 是 ANR 驗測 campaign 第二個 use-case,達成。API 涵蓋:`FLAG`(hoBlocklist)。
