# (DT) 轉達 RIC 團隊回覆:O1 E2 節點清單的依賴條件近期不變;o1mediator 每小時會斷一次 NETCONF

- 日期:2026-09-30
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps` 的回覆(經 mitlab 轉貼)
- 背景:DT 把「SMO 的 `o1-me-lifecycle-controller` 會讀 RIC 的 `o-ran-sc-ric-gnb-status-v1:ric/nodes`」這項依賴告知了 RIC 團隊
- 需要 SMO 處理:**第 2 節請確認控制器的容錯**;其餘為知會

## 1. RIC 的回覆:三個依賴條件近期都不會改

| 條件 | RIC 的說明 |
|---|---|
| `ran-name` = DT 的 ME 名稱(`gnb_208_095_000eXY`) | 09-27 與 DT 定案的槽位命名,不會改 |
| 連線狀態可分辨 | o1mediator 每次被 NETCONF 讀取時現查 e2mgr 的節點狀態,沒有快取;值是 `connected` / `disconnected` |
| RIC 的 O1 持續可讀 | o1mediator 是原廠 0.6.4,未改版,不在任何改動計畫內 |

RIC 團隊的承諾:改 meid 命名、停 O1、動 e2mgr 或 o1mediator、改閘道清節點的行為之前,會先通知 DT 與 SMO。

## 2. 請 SMO 確認:o1mediator 每滿 1 小時會關一次 NETCONF session

RIC 團隊說明這是已知行為:每滿 1 小時 NETCONF session 會被關一次,SDNC 會立即重連。**控制器要能容忍那一次讀取失敗。**

請確認控制器在讀不到 RIC 節點清單的那一輪:

- 不會把「讀不到」當成「清單是空的」,進而把 gNB 從 PMS 移除或刪掉 E2 連線關係;
- 會沿用上一輪的結果或跳過這一輪。

## 3. run 結束時清單的實際行為(SMO 先前想知道的)

| 步驟 | 行為 |
|---|---|
| DT 的 E2 adapter 停止 | 送 E2 Reset 並關 SCTP,e2mgr 幾秒內把該 gNB 標成 `disconnected`(09-28 實測約 8 秒) |
| DT 的編排服務對 RIC 閘道送刪除場景 | 預設連 R-NIB 一起清,節點立即從 e2mgr 消失,O1 清單下一次讀就沒有它 |

所以從 run 結束到清單看不到該 gNB,最多等於控制器 60 秒輪詢的一個週期。常駐的 e00 不會消失。

補充(DT):自動重啟時也會走「停 → 起」,節點會短暫變成 `disconnected` 或消失再回來,與第 2 節同理,請確認控制器在寬限時間內不因此移除 PMS 歸屬。今天 10:23Z 的自動重啟實測沒有誤清,供參考。

## 4. R6 第一批 PM 量測清單

狀態不變:仍待 mitlab 直接向 RIC 團隊核准。
