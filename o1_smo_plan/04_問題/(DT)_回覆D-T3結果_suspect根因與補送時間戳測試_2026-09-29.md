# (DT) 回覆 D-T3 結果:e10 suspect 根因(上游 bug,已修)、補送時間戳測試已送

日期:2026-09-29 15:45Z。來自 DT 端。D-T3 全流程通過收到,謝謝。

## 2.1 `e10_du1` 完整週期被標 suspect —— 上游 adapter 的判斷有相位問題,已修(patch 0007)
- 查 run log:e10 的 adapter 在 15:00–15:15 無重啟、無 telnet 斷線、facade 無 HTTP 失敗,輪詢次數與 e11 相當(856 vs 859)。
- 根因在 OAI adapter `pm_data.c`:`suspect = (最後一筆取樣時間 − 第一筆取樣時間) < 900`。它每秒輪詢一次,若視窗內第一筆落在 15:00:01、最後一筆 15:14:59,差 898 s 就被標 true;e11、e12 剛好相位對齊才是 false。純粹看運氣。
- 修正:改為看視窗對齊 —— 第一筆距視窗起點 ≤5 s 且最後一筆距視窗終點 ≤5 s 才算完整;否則 suspect。`adapter-gnb:dt` 正在重建,e00 兩顆 adapter 會 recreate 一次(SDNC 會看到重連,約 15:50Z),之後的 run 也用新映像。
- 15:45、16:00 的 e00_du1 檔可用來確認不再誤標。

## 2.2 補送時間戳測試 —— 已用「週期起訖」重送 4 檔
- 依你們的推測(pmlog 用 `lastEpochMicrosec`),我查了 ranpm 原始碼:dfc 把 fileReady 的 `commonEventHeader.startEpochMicrosec / lastEpochMicrosec` 原樣放進 `collected-file` 訊息,`xmltransform.go` 再原樣填進 PM JSON header → pmlog 用它當時間。**所以補送時把這兩個欄位填成週期起訖,InfluxDB 時間就會是週期終點。**
- 15:37:32–15:37:48Z 已對 `gnb_208_095_000e00_du1` 重送 `1330-1345`、`1345-1400`、`1400-1415`、`1415-1430`(eventId `…_FileReady_resend2_*`),`startEpochMicrosec`=週期起、`lastEpochMicrosec`=週期終、`eventTime`/`fileReadyTime`=週期終,VES 皆 202。請查 InfluxDB 是否出現 13:45、14:00、14:15、14:30 四個時間點的資料;若有,先前 15:13 那 4 筆錯誤時間戳的資料可依 mitlab 決定刪除。
- 注意:adapter 正常送檔時 start/last 都填「送出當下」(週期終點 +1 s),所以正常資料的時間戳本來就約等於週期終點,無此問題。

## 其他
- FM 只讓 DU 告警的觸發方式:收到,下次照做。
- SMO 端的 ncmp-to-teiv-adapter 上游修正報告已由 mitlab 轉給我,已存檔;#5(ODUFunction dUpLMNId null)若上游修好,TEIV 的 ODUFunction 會自帶 PLMN,DT 不需補。
