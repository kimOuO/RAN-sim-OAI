# (DT) 轉達 RIC:03:06:54Z 已把 vespamgr scale 到 0,measurement 立即停止

- 心跳與告警也同時暫停,幾分鐘內恢復(RIC 端在覆蓋的 config-file.json 加開關:預設關量測、不載入 plt-counter.json、Prometheus 位址指向無效,只送心跳與告警;helm upgrade 換 pod 後會通知)。
- 原因:RIC 端把 prometheusAddr 從原廠不可解析的 infra-cpro-server 改成真的 Prometheus,量測因此活過來。
- 告警清除順序:RIC 會先用 system_name=RIC 對目前那筆再送一次 clear(vespamgr 恢復後由 Alertmanager resolved 送出),等你們確認 node-id "RIC" 那筆清掉、清單歸 0 後,再換 alarm-go 新版、對 ric-dt-71 raise/clear 一輪。
- 請 SMO 端確認:VES log 停止暴增、pod 不再 evict;目前 VES 是否穩定(DT 的 PM 03:15Z 檔會送)。
