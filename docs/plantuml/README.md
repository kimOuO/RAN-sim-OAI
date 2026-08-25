# XAPP_DT 端到端時序圖 (PlantUML)

跨服務的 ran-sim → Omniverse 端到端流程時序圖套件。沿用 `Physics_sim/docs/plantuml/UC1~4` 的畫法(`!pragma teoz true`、box 巢狀分組、`group [Function]` + `autonumber`),但每個 box = 一個容器/服務。

> 與程式碼有出入時**以原始碼為準**。本套件基於 2026-07 現況程式碼繪製。

## 圖清單

| 檔案 | 主題 | 涵蓋 |
|---|---|---|
| `UCA_sim_start.puml` | **Sim 啟動** | `SimController.start` → 清場 → 廣播速度 → 建 session → scene-apply(C.1–C.5) → UE attach(RRC/F1AP) → set quota/A3 → tick 啟動 |
| `UCB_tick_dataflow.puml` | **一個 tick 的資料流(核心)** | RLC buffer → SINR(live-HTTP 或 in-process) → PF 排程 → RLC drain → DL TTI → RU SINR/CQI → UL(TCP-ACK) → PM → slot engine delay → 每 N tick flush KPM 給 CU |
| `UCC_e2_closed_loop.puml` | **E2 閉環** | E2 Setup/Subscription → KPM 上行(E2SM-KPM Format3) → RC 下行(Style2/3 落地 PRB quota / HO / Cell On-Off) → push_control_action |
| `UCD_omniverse_viz.puml` | **Omniverse 視覺化 + 歷史/回放** | UE 位置/訊號 ingest、CU HO/RC fire-and-forget、Kit USD 渲染、Dashboard playback |
| `UCE_precompute_cached.puml` | **Precompute → cached 模式** | 離線逐 tick 算 path_gain → `.npz` → RU/DU 查表跳過 Sionna |

**閱讀順序**:UC-A(怎麼起) → UC-B(核心心跳) → UC-C(對 RIC 閉環) → UC-D(視覺化/回放) → UC-E(加速用的離線快取)。

## 渲染成 PNG

本機需有 `plantuml`(含 Java):

```bash
sudo apt-get install -y plantuml          # 一次性安裝
# 產生全部 PNG（輸出到同目錄）
plantuml -tpng docs/plantuml/*.puml
# 或 SVG
plantuml -tsvg docs/plantuml/*.puml
```

VS Code 亦可用 "PlantUML" 外掛即時預覽。
