# Supported Intents — Interface Reference

支援的 case（mode）共 3 種，輸入用 KPM 指標，輸出走 E2SM-RC wrapper。

來源：`docs/supported-intents.md` v1.7。

---

## 1. Case 總表

| Case (mode) | cat | 用途 | 觸發 KPM | 控制 wrapper | RC Style/Action |
| --- | --- | --- | --- | --- | --- |
| IM (interference) | `im` | 干擾管理（軟限額） | `RRU.PrbTotDl` + `DRB.UEThpDl` + `DRB.RlcSduDelayDl` | `control_slice_level_prb_quota` | 2 / 6 |
| CCO (coverage/capacity) | `cco` | 覆蓋與容量優化 | `RRU.PrbTotDl`（gNB 間差距） | `control_handover` | 3 / 1 |
| ES (energy saving) | `es` | 軟節能 | `RRU.PrbTotDl` + `DRB.PdcpSduVolumeDL` | `control_handover` + `control_slice_level_prb_quota` | 3 / 1 + 2 / 6 |

三個 case 都只走 E2（不接 A1 / O1），service_model 固定 `E2SM-RC`。

---

## 2. 輸入介面（KPM Fields）

從 InfluxDB `e2sm_kpm.ricIndication` 撈，每個 field 提供 `{mean, max, min, p95, stddev, samples}`。

| Spec 名（yaml 用） | InfluxDB field | 單位 | IM | CCO | ES |
| --- | --- | --- | --- | --- | --- |
| `RRU.PrbTotDl` | `RRU_PrbTotDl` | 0-100 | 主 | 主 | 主 |
| `RRU.PrbTotUl` | `RRU_PrbTotUl` | 0-100 | 副 | 副 | — |
| `DRB.UEThpDl` | `DRB_UEThpDl` | kbps | 主 | 副 | 副 |
| `DRB.UEThpUl` | `DRB_UEThpUl` | kbps | — | — | — |
| `DRB.RlcSduDelayDl` | `DRB_RlcSduDelayDl` | ms | 主 | — | — |
| `DRB.PdcpSduVolumeDL` | `DRB_PdcpSduVolumeDL` | bytes | — | — | 主 |
| `DRB.PdcpSduVolumeUL` | `DRB_PdcpSduVolumeUL` | bytes | — | — | 副 |

命名雙軌：spec/yaml 用左欄 dot；InfluxDB query / dump JSON 用右欄底線。

不支援的指標（spec 出現會被 strategy-designer 拒絕）：SINR, BLER, RSRP/RSRQ, CQI 分布, RRC 連線數, HO 統計。

rfsim 環境常 0 的欄位：`DRB.UEThpUl`, `DRB.PdcpSduVolumeUL`, `RRU.PrbTotDl/Ul`（低負載整數截斷）。

---

## 3. 輸出介面（RC Wrapper API）

兩個 Python wrapper（`xapp-scaffolder/template/ric-app-hw-python/src/lib/rc/sender.py`）：

### 3.1 `control_slice_level_prb_quota`

```python
control_slice_level_prb_quota(
    node: str,            # gNB-CU meid，例如 "gnb_734_733_e00"
    ue: int,              # UE index（目前 single-slice 固定 0）
    min_prb: int,         # 0-100，最低 PRB 比例
    max_prb: int,         # 0-100，最高 PRB 比例
    dedicated_prb: int,   # 0-100，專屬 PRB 比例
)
```

- RC Style 2 / Action 6
- 影響 gNB-DU MAC scheduler `max_rbSize`
- 邊界：max ratio cap only（min/dedicated 暫不差異化）；single-cell；single-slice；DL only
- IM, ES 用

### 3.2 `control_handover`

```python
control_handover(
    node: str,            # gNB-CU meid
    ngap_id: int,         # AMF-UE-NGAP-ID
    f1ap_id: int,         # gNB-CU-UE-F1AP-ID
    plmn: dict,           # {"mcc": "001", "mnc": "01"}
    target_cgi: dict,     # {"plmn": {...}, "nr_cell_id": ...}
)
```

- RC Style 3 / Action 1
- 觸發 gNB-CU `nr_HO_F1_trigger`
- CCO, ES 用

未實作的 RC（spec 出現會被拒絕）：cell off, Tx Power, antenna tilt, A1 policy, ASM 進階睡眠, DSS, ML 線上訓練, UL PRB Quota, 多 cell / 多 slice 差異化。

---

## 4. 各 Case 的 yaml 介面

通用結構：

```yaml
intent:
  scope: [E2]                          # 固定
  action: control                      # 固定
  primary_metric: <KPM dot 名>
  control:
    service_model: E2SM-RC             # 固定
    style: <int>
    action: <int>
    api: <wrapper 名>
    mode: <IM | CCO | EnergySaving>
decision_logic:
  type: threshold | sliding_window
  parameters: { ... }
  pseudo_code: |
    ...
```

### 4.1 IM (cat=im)

**在管什麼**

針對「**單一 cell 內部擁塞**」做管理，不是物理層真的消除干擾。

| 面向 | 內容 |
| --- | --- |
| 觀察對象 | 一個 cell 同時呈現三件事：PRB 占用高、UE 吞吐低、RLC SDU 延遲高 |
| 推論 | 這個 cell 內某 slice / UE 正在搶 PRB，造成排程器把資源切得太碎 → 延遲飆升（這是「擁塞 → 干擾」的 proxy，因為 OAI 沒有真實 SINR/BLER 給看）|
| 動作 | 對該 cell 的 slice 下「PRB 配額上限」，讓 DU MAC scheduler 不再讓 noisy slice 吃滿 PRB |
| 控制標的 | gNB-DU MAC scheduler 的 `max_rbSize`（每個 TTI 該 slice 最多分到幾個 PRB） |
| 不會做 | 不關 cell、不改 Tx Power、不改 modulation、不會跨 gNB 動 UE |

效果：把「噪音鄰居」壓下去 → 延遲恢復。屬於 **per-cell, per-slice, DL only** 的軟限額。

**intent**

| 欄位 | 值 |
| --- | --- |
| `primary_metric` | `DRB.RlcSduDelayDl` |
| `control.style` | 2 |
| `control.action` | 6 |
| `control.api` | `control_slice_level_prb_quota` |
| `control.mode` | `IM` |

**decision_logic.type** = `threshold`

| Parameter | 預設 | 意義 |
| --- | --- | --- |
| `prb_th` | 0.70 | `RRU.PrbTotDl` 高於則視為熱 |
| `thp_dl_low_th` | 5000 | `DRB.UEThpDl` (kbps) 低於則視為被擠 |
| `delay_dl_high_th` | 50 | `DRB.RlcSduDelayDl` (ms) 高於則視為延遲嚴重 |

觸發後動作：`control_slice_level_prb_quota(node, ue=0, min_prb=10, max_prb=50, dedicated=100)`。

### 4.2 CCO (cat=cco)

**在管什麼**

針對「**跨 gNB 之間的負載不均**」做管理，不是改覆蓋範圍（那要 O1 改 Tx Power / 天線傾角）。

| 面向 | 內容 |
| --- | --- |
| 觀察對象 | 多個 gNB-CU 的 `RRU.PrbTotDl` 比較，找出 hot cell（>0.85）與 cold cell（<0.30），且兩者差距 > 0.30 |
| 推論 | 在現有覆蓋下，UE 分配不均勻 → hot cell 排隊，cold cell 閒置 |
| 動作 | 對 hot cell 的「邊緣 UE」（朝向 cold neighbor 的）發 F1 Handover，把它們切到 cold cell |
| 控制標的 | UE 連到哪個 gNB-DU（透過 gNB-CU RRC `nr_HO_F1_trigger`） |
| 不會做 | 不關 cell、不調覆蓋、不改頻段、不對單一 cell 做 PRB 限額 |

效果：把整網 PRB 利用率拉平 → 整體 throughput 提升。「容量優化」的意涵就是 UE 重新分配，不是真的擴容。

**intent**

| 欄位 | 值 |
| --- | --- |
| `primary_metric` | `RRU.PrbTotDl` |
| `control.style` | 3 |
| `control.action` | 1 |
| `control.api` | `control_handover` |
| `control.mode` | `CCO` |

**decision_logic.type** = `threshold`

| Parameter | 預設 | 意義 |
| --- | --- | --- |
| `imbalance_gap` | 0.30 | gNB 間 PRB 差距觸發門檻 |
| `hot_th` | 0.85 | 熱 cell 門檻 |
| `cold_th` | 0.30 | 冷 cell 門檻 |

觸發後動作：對 hot cell 邊緣 UE 執行 `control_handover(node, ngap_id, f1ap_id, plmn, target_cgi)` 切到 cold neighbor。

### 4.3 ES (cat=es)

**在管什麼**

針對「**持續低載 cell 的軟性節能**」做管理。**沒有真的關電源**（那要 O1 NETCONF / 硬體配合），只是讓 scheduler 幾乎不分配資源，變相省 baseband 處理。

| 面向 | 內容 |
| --- | --- |
| 觀察對象 | 單一 cell 5 分鐘滑動窗口：`RRU.PrbTotDl` mean < 10% **且** `DRB.PdcpSduVolumeDL` mean < 1MB（兩者同時成立才算閒置）|
| 推論 | 這個 cell 沒在做事但還開著 → 浪費 |
| 動作（兩段式） | 1. `control_handover` 把殘留 UE HO 到鄰居 cell；2. `control_slice_level_prb_quota(min=0, max=5, dedicated=0)` 把該 cell 配額壓到極小 |
| 恢復觸發 | 再進入 ES mode 後，若 Volume 回升超過門檻 → 解封 `(min=10, max=100, dedicated=100)` |
| 控制標的 | 先是 UE 連線歸屬（HO），再是 DU MAC scheduler PRB 配額 |
| 不會做 | 不關 RU、不關電源、不改 sleep mode（這些要 O1 + 硬體）|

效果：低負載 cell 排程降到極低 → 軟節能。是 IM（壓配額）+ CCO（HO）兩個動作的時序組合，不是新動作。

**intent**

| 欄位 | 值 |
| --- | --- |
| `primary_metric` | `RRU.PrbTotDl` |
| `control.style` | 3（主：HO；副：Style 2 壓配額） |
| `control.action` | 1 |
| `control.api` | `control_handover` |
| `control.mode` | `EnergySaving` |

**decision_logic.type** = `sliding_window`

| Parameter | 預設 | 意義 |
| --- | --- | --- |
| `window_sec` | 300 | 滑動窗口長度（秒） |
| `prb_low_th` | 0.10 | `RRU.PrbTotDl` 5min mean 低於則視為低載 |
| `vol_low_bytes` | 1048576 | `DRB.PdcpSduVolumeDL` 5min mean 低於則視為無流量 |
| `es_min_prb` | 0 | 進 ES 後 min |
| `es_max_prb` | 5 | 進 ES 後 max（壓配額）|

觸發後動作：先 `control_handover` 把殘留 UE 趕走 → 再 `control_slice_level_prb_quota(min=0, max=5, dedicated=0)` 壓配額；恢復條件達成時用 `(min=10, max=100, dedicated=100)` 解封。

---

## 5. 變體 × 動作對應

每個變體 = 一個具體意圖 = 「**觸發條件 → 動作組合**」的綁定。同 case 的不同變體差在「看哪些 KPM」與「下哪些 wrapper」。

### 5.1 IM 變體

| 變體 ID | 狀態 | 觸發條件 | 動作 | 用到的 wrapper |
| --- | --- | --- | --- | --- |
| `im-01` soft-mitigation | 現有 v1.7 | 單 cell 同時 `RRU.PrbTotDl > 0.70` + `DRB.UEThpDl < 5000` + `DRB.RlcSduDelayDl > 50` | 對該 cell slice 下 PRB 配額上限（`max=50, dedicated=100`） | `control_slice_level_prb_quota` (2/6) |
| `im-02` ho-walkaway | 規劃 | 單 cell `RRU.PrbTotDl ↑` + `DRB.RlcSduDelayDl ↑` | 把該 cell 邊緣 UE HO 走避到鄰居 | `control_handover` (3/1) |
| `im-03` hybrid-mitigation | 規劃 | 單 cell `PRB↑ + Thp↓ + Delay↑` 嚴重（門檻較 im-01 緊） | 邊緣 UE HO 走 + 同步壓剩餘 PRB 配額（雙管齊下） | `control_handover` (3/1) + `control_slice_level_prb_quota` (2/6) |

### 5.2 CCO 變體

| 變體 ID | 狀態 | 觸發條件 | 動作 | 用到的 wrapper |
| --- | --- | --- | --- | --- |
| `cco-01` load-balance | 現有 v1.6 | gNB 間 `RRU.PrbTotDl` 差距 > 0.30；hot > 0.85；cold < 0.30 | 對 hot cell 邊緣 UE 發 F1 HO 切到 cold neighbor | `control_handover` (3/1) |
| `cco-02` thp-equalize | 規劃 | gNB 間 `DRB.UEThpDl` 差距大（吞吐導向，非 PRB 占用導向） | 同 cco-01 但選擇邊緣 UE 與目標 cell 的判準改用吞吐 | `control_handover` (3/1) |
| `cco-03` preemptive-balance | 規劃 | `RRU.PrbTotDl` 上升斜率高（趨勢預測，門檻未達但快達） | 在達到門檻前先 HO 部分 UE 出去 | `control_handover` (3/1) |

### 5.3 ES 變體

| 變體 ID | 狀態 | 觸發條件 | 動作 | 用到的 wrapper |
| --- | --- | --- | --- | --- |
| `es-01` low-load-consolidation | 現有 v1.5 | 5min mean：`RRU.PrbTotDl < 0.10` **且** `DRB.PdcpSduVolumeDL < 1MB` | 1. HO 殘留 UE 到鄰居；2. 壓配額 `min=0, max=5, dedicated=0` | `control_handover` (3/1) + `control_slice_level_prb_quota` (2/6) |
| `es-02` volume-only-quench | 規劃 | `DRB.PdcpSduVolumeDL` 持續為 0（無 traffic 但可能仍有 idle UE attached） | 跳過 HO，直接壓配額 `max=5` | `control_slice_level_prb_quota` (2/6) |
| `es-03` scheduled-night-mode | 規劃 | 時段觸發（例：每日 02:00–05:00），不看即時 KPM | 同 es-01 兩段式（HO + 壓配額），時段結束自動解封 | `control_handover` (3/1) + `control_slice_level_prb_quota` (2/6) |

### 5.4 動作總覽（變體 × wrapper 矩陣）

| 變體 | `control_slice_level_prb_quota` (2/6) | `control_handover` (3/1) |
| --- | --- | --- |
| `im-01` | ✓ | — |
| `im-02` | — | ✓ |
| `im-03` | ✓ | ✓ |
| `cco-01` | — | ✓ |
| `cco-02` | — | ✓ |
| `cco-03` | — | ✓ |
| `es-01` | ✓ | ✓ |
| `es-02` | ✓ | — |
| `es-03` | ✓ | ✓ |

---

## 6. 拒絕清單（Stage 1 直接 reject）

| 使用者要求 | 原因 |
| --- | --- |
| 真關 cell / cell off | RC 規格無此 action |
| 改 Tx Power / antenna tilt | 要 O1 NETCONF |
| 下發 A1 policy / TSP | xApp 走 E2 不走 A1 |
| 動態頻段切換 / DSS | 規格範疇外 |
| 訓練 ML 模型 | 只支援推論型 placeholder |
| 看 SINR / BLER / RSRP | 現行 KPM 訂閱沒這些 field |
| UL PRB Quota | OAI 暫只 hook DL scheduler |
| 多 cell / 多 slice PRB 差異化 | OAI Phase C 暫只 single-cell single-slice |
