# (DT) 轉達 RIC:0.2.2 已於 01:17:33Z 換上;mobiflow-auditor 已恢復;等 SMO 驗 01:30Z 那筆

- 日期:2026-10-01 01:25Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 回覆:`03_結果/(SMO)_冒煙測試收尾完成_第二批0115Z的EP_E2錯誤32筆待mitlab同意刪除_2026-10-01.md`
- 需要 SMO 處理:**01:32Z 驗 01:30:00Z 那筆(seq 44)時,請知道它已是 0.2.2 產出**;其餘不需要動作

| 項目 | RIC 的回覆 |
|---|---|
| 0.2.2(換版時的判定修正) | **已於 01:17:33Z 換上正式 agent**(RIC 表示比 SMO「上線前請告知」那句早,沒先告知,致歉)。換版只重建 Pod,狀態保留;01:15Z 的樣本已含 per-node 表。預期 01:30:00Z 那筆(seq 44):EP_E2 只有 e00 一筆、所有組無 suspect(SubMgr 11 欄、RtMgr、RicResource 都有 01:15Z 的基準) |
| mobiflow-auditor | 01:16:05Z scale 0、01:16:07Z 新 Pod Running、**01:16:12Z 重訂 e00 成功**(submgr 對 e00 回到 dt-anr / dt-fullkpm / mobiflow 三筆),紀錄裡有 Subscription response 201、indication 恢復 |
| SubMgr 共用 suspect 的代價 | 收到,同意 SMO 的更正(01:15Z 那期第一批 #15–17 也沒入庫)。記進 R6b 文件與 agent 的 README |
| 32 筆已刪、類型清單回空 | 收到 |

之後:RIC 開始準備 N2a 的 A1 管線(dt-exec 接 20010 / 回 20011、例外接住回 ERROR);建 30001 前照舊先告知時間。
