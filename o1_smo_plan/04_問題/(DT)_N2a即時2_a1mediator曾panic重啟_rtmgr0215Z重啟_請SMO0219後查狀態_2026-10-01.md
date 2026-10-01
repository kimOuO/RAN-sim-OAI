# (DT) N2a 即時(第二則):a1mediator 02:12:20Z 收到 20011 後 panic 重啟;RIC 02:15Z 重啟 rtmgr;請 SMO 02:19Z 後再查狀態;02:25 刪除照原訂

- 日期:2026-10-01 02:15Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 需要 SMO 處理:**02:19Z 後再查 `smo-n2a-es-1` 的狀態;02:25Z 的刪除照原訂**;判讀時把第 3 節寫進結果

## 1. a1mediator panic 重啟(RIC 的回報)

- 02:12:20Z xApp 的 20011 **送到了**,但把 a1mediator 弄到 panic、容器重啟(02:12:21Z 回來,policy `smo-n2a-es-1` 還在 SDL 裡)。
- 原因:a1mediator 3.2.3 在 20010 把 `policy_type_id` 送成字串 "30001",但收 20011 時做 `interface{} → float64` 轉型;xApp 照收到的型別回字串就 panic。RIC 0.2.3 已改回數字(02:13:27Z 換上)。RIC 記進文件:**20011 的 `policy_type_id` 必須是數字**。這是 a1mediator 的脆弱點。

## 2. rtmgr 推送不恢復 → RIC 02:15Z 重啟 rtmgr

- a1mediator 重啟後 rtmgr 推不到它的路由表(每個週期 send failed),也推不到 dt-a1-xapp 的新 pod;沒有路由,a1mediator 送不出 20010(含 02:25 的 DELETE),xApp 的 20012 查詢也得不到回應。
- 這是 RIC 平台「元件重啟後 rtmgr 推送不恢復」的老問題,唯一有效的處理是 graceful 重啟 rtmgr(scale 0 → 1,約 30 秒,重啟後對所有端點重推一次)。**RIC 02:15Z 做。**
- 對這場 run 的影響:場景 xApp 與 submgr 的既有路由不變,只有「新路由」要等重啟後第一次推送(約 1 分鐘);dt-exec 若送控制,rc-probe 的 ack 路由不受影響。

## 3. 時程與判讀

- gNB 端:mid 自 02:10:03Z 起在節能,02:12:20Z 的重送冪等,狀態沒變。**gNB 這一側的效果不受上述兩件事影響。**
- a1mediator 目前狀態仍 NOT_ENFORCED(20011 到了但它崩了)。rtmgr 重啟、路由推到後,xApp 會再送 20012 取回 policy、重送 es-on(冪等)與 20011,預計 02:17–02:18Z 狀態才會變。**SMO 請 02:19Z 後查。**
- 02:25Z 的 DELETE 照原訂。若那時 a1mediator → xApp 的 20010 路由仍沒推到,DELETE 會到不了 xApp、mid 不會開回;屆時請 SMO 告知,DT 會從 gNB 端確認,RIC 再處理。
