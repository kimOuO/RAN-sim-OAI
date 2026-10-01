# (DT) 轉達 RIC:vespamgr 0.7.5-mit2 07:03:34Z 上線;心跳序號歸 0;測試告警 72004 請 SMO 確認;run D 停後 RIC 會 CLEAR,驗「跨 run 起停的 clear 能到」

- 日期:2026-10-01 07:10Z
1. **vespamgr 0.7.5-mit2** 07:03:34Z 上線(helm rev 6):xApp 通知後重產 ves-agent 設定,內容相同就不重啟。換版時 ves-agent 照原廠起了兩次,**心跳 eventId 從 heartbeat0000000000 重數**(07:04 起),之後不再重啟。
2. **驗證告警已舉**:07:07:17Z RAISE 72004 `smo-ves-test-alarm-6`(MINOR,sourceName ric-dt-71,applicationId smo-ves-test)→ 07:07:22Z vespamgr 送 `fault0000000001`。**請 SMO 確認 SDNR 有這筆 MINOR。**
3. 跨 run 起停:run D(`00bba8b4-20261001T070358Z`)07:03:43Z 起、約 07:19Z 停,起停各一次 appmgr 通知;run D 停後 RIC 才 CLEAR。預期 clear 後 ≤ 6 分鐘 SMO 收到 NORMAL、SDNR 歸 0(對照今天 05:37 那次 clear 被吃掉)。
4. 這場 run D 同時在驗 H1 / H3(見前一檔),互不影響。
