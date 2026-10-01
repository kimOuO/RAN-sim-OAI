# (DT) mitlab 的決定:下一階段計畫 v0.2 的六項全部同意,照建議做

- 日期:2026-09-30 18:10Z
- 來自:DT 端(10.3.0.217),轉述 mitlab 在 DT 這邊的指示(原話:「六項都同意 照建議做」)
- 回覆:`01_計畫/(SMO)_下一階段計畫_討論稿v0.2_2026-09-30.md` 第 7 節
- 已同步通知 RIC 團隊(session `anr_xapps`)

## mitlab 的決定

| # | 事項 | 決定 |
|---|---|---|
| 1 | R6b v2(RIC 第二批 PM,29 項)的名稱 | **核准,名稱凍結。** A 組沿用第一批相同名稱、掛在 `EP_E2=<meid>` 物件(照 SMO 與 RIC 的建議) |
| 2 | N2 第一個 policy 類型 | **節能**(`ORAN_EnergySaving_4.0.0`)先做,負載平衡(`ORAN_LoadBalancing_3.0.1`)第二 |
| 3 | 類型編號與路徑 | **30001(節能)/ 30002(負載平衡),不經 `a1med-proxy`,PMS 直接對 RIC-A。** RIC 已接受;前提是 PMS 對 `ric-dt-71` 用 OSC adapter(`create_schema`),請 SMO 確認(`04_問題/(DT)_轉達RIC_接受30001-30002與不經proxy_前提是PMS用OSC_adapter_2026-09-30.md`) |
| 4 | 冒煙測試 | **同意** RIC 在 RIC-A 建測試類型(編號 1)驗 A1 路徑,不下控制,測完刪除。PMS 會看到它,SMO 知悉 |
| 5 | DT 的連線關係檔 | **停產。** 從下一場 run 起 DT 不再產出 `teiv_links_*`;需要比對時再臨時產 |
| 6 | 階段順序 | **N1 與 N2a 重疊 → N2b → N3 → N4 → N5**,N6 另議 |

## 各方接下來(依 v0.2)

| 誰 | 事項 |
|---|---|
| RIC | N1:實作第二批(一個 measInfo 多個 measValue、per-node 取樣、Prometheus 與 /proc 來源)→ 提供一個有 run 在跑的完整週期樣本。N2a:A1 管線(註冊 30001、xApp 宣告、收 20010 / 回 20011)+ 節能 xApp;冒煙測試可先做 |
| SMO | 確認 PMS 的 adapter 類型;準備 PMS 建 / 查 / 刪 policy 的步驟與從 O1 算 NCI 的工具;N1 樣本到了用實際轉檔程式檢查 |
| DT | 準備 N2a 的驗證場景:開鄰區關係、PM 週期 60 秒;起 run 前通知 RIC 與 SMO;N2a 開始前用一場 run 實測 A3 / PRB 配額的讀碼結論;選擇性:為 O1 補 `PEE.*` 能耗量測 |

DT 的第一步:先起一場「開鄰區關係、PM 週期 60 秒」的 run,確認 SMO 端 60 秒的檔正常入庫、UE 在有鄰區關係時的行為,並供 RIC 的 N1 樣本使用(A 組會有 4 個 measValue)。時間另行通知。
