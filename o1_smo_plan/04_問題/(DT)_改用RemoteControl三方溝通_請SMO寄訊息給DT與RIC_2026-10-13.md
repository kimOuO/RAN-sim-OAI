# (DT) mitlab 指示:三方改用 Remote Control 溝通,請 SMO 先寄一則訊息給 DT 與 RIC

- 日期:2026-10-13
- mitlab 指示:DT、SMO、RIC 三方改用 Remote Control 直接傳訊息,由 DT 統籌指揮。所有進度、本次測試項目、環境準備、完成事項都要讓另外兩方知道;權限做不到的事回報 DT,由 DT 向 mitlab 確認。
- 連線測試結果:DT 寄給 `dt-smo-connect-0c [155b4b]` 失敗(DT 端看不到這個名稱);RIC 也寄不到。RIC 與 DT 之間已用 bridge 位址接通。

## 請 SMO 做

1. 用 SendMessage 寄一則訊息給 **DT**,位址用 `bridge:session_01T5EaASvqw6TCseHMaP6Deh`(若不通再試名稱 `xapp-dt-6b`)。
2. 也寄一則給 **RIC**,位址用 `bridge:session_015zoj9ru6HH8LXUuSPjWPxF`(名稱 `anr_xapps (2) [30becd]`)。
3. 訊息內容:確認收到,以及 SMO 目前狀態(修好的 F1 控制器是否仍待部署、有無其他進行中工作)。

收到 SMO 的訊息後,DT 與 RIC 都能取得 SMO 的回覆位址。共用資料夾繼續作為正式紀錄。
