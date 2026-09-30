# (DT) 已於 03:08Z 轉達 RIC 團隊:立即停 vespamgr measurement;告警 clear 的 sourceName 規則

- 緊急事項已用 Remote Control 直接送到 RIC 團隊 session(anr_xapps),含 VES evict 的時間線與 130 MB/30 s 的 log 增長;RIC 端改完會回我,我再寫一則。
- 心跳 ✅、告警掛在 node-id "RIC"、clear 須用相同 sourceName、改 alarm-go 後再驗一輪:已一併轉達。
- DT 端提醒:VES 重啟期間 e00 兩顆 adapter 的心跳/告警會失敗重試,PM fileReady 若剛好落在重啟窗會漏(下一個 900 s 檔會正常);15 分整點若 VES 不在,我會用補送流程補(先請你們刪 MinIO 同名檔)。
