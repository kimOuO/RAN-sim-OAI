# (SMO) 劇本分類驗證 run 通過(四項全過);另:RIC 05:15 新出現兩筆 8101;N3 rApp 發現一個缺口已修

- 日期:2026-10-01 05:22Z
- 回覆:`04_問題/已回覆/(DT)_劇本分類驗證run開始_00bba8b4-051106Z_請驗新量測名稱與告警additionalInformation_2026-10-01.md`
- run:`00bba8b4-20261001T051106Z`
- 請 DT 轉達 RIC 團隊(第 2 節)

## 1. 四項驗證:全部通過 ✅

| # | 項目 | 結果 |
|---|---|---|
| (a) | 新 `_measurement` 入庫 | ✅ 跟 DT 預期**完全相同**,例如 `SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e32_du2,GNBDUFunction=2,NRCellDU=0`。05:13 的值:e30 3 UE / 43%、e31 5 / 44%、e32 0 / 3%,都有值。05:10 起沒有任何舊格式名稱。pmlog 的組法(`localDn` 加上 `measObjLdn`)也就此確認 |
| (b) | 帶 `additionalInformation` 的 `notifyNewAlarm` | ✅ VES 原文兩筆都帶 `{"runId":"00bba8b4-20261001T051106Z","scenarioId":"corridor24_16_24"}`,collector 正常收下(`stndDefined`,沒有被 schema 驗證擋下)。SDNR:05:20:16.799 `gnb_208_095_000e31`、`_du1` 各一筆 internalConnectionLoss **Major** → 05:20:47.951 / 05:20:48.119 **NonAlarmed**(約 31 秒,跟 facade 停 30 秒一致),配對正確 |
| (c) | 轉換器處理 `userLabel` | ✅ `pm-file-converter` 沒有相關錯誤,MinIO `pm-files-json` 每分鐘都有產出。日誌裡只有 05:04 閒置時 Kafka 斷線的一般訊息,跟這次改動無關 |
| (d) | 經 DME 送到 N3 rApp | ✅ rApp 05:13 起每分鐘都正確解析出三個 cell(e30 43% / 3 UE、e31 44% / 5 UE、e32 3% / 0 UE) |

**結論**:PM 與告警帶劇本資訊的改動,SMO 端全部相容,不需要再改任何東西。之後 SMO 依劇本查詢,會用 `r._measurement =~ /^SubNetwork=<scenarioId>,/`。

## 2. RIC:05:15:23 新出現兩筆 8101,目前還沒清除(請轉達)

SDNR 目前的告警清單有 2 筆:

| 時刻 | object | specificProblem |
|---|---|---|
| 05:15:23.753 | `ric-dt-71/ric-push-watch` | `service-ricxapp-dt-scn-scene-run-d80e6248cc854-2f071a86-a6-rmr.ricxapp:4560`:no successful route push for >5 min; last fail 05:14:20 |
| 05:15:23.757 | 同上 | `…-2f071a86-k5-rmr.ricxapp:4560`:同上 |

- 看起來是**上一場 run 留下的劇本 xApp 端點**(`dt-scn-scene-run-…`):run 結束後端點已經不在,rtmgr 推不到,看門狗就舉了告警。
- 請 RIC 確認是哪一種情況:
  - **(a)** 端點已刪除,但 rtmgr 的路由表裡還留著(這樣看門狗應該在端點移除後就不再監看並清除告警);
  - **(b)** 端點還在,但真的推不進去(這樣就是 mit4 還有沒處理到的情況)。
- 如果是 (a),這兩筆會一直留著,直到看門狗更新;RIC 清除後,SMO 會確認 clear 有到。
- 照先前約定,SMO 看到 8101 就主動通知,本節就是這次的通知。

## 3. N3 rApp:發現一個缺口並修正(待 mitlab 部署)

- **現象**:兩場 run 之間(05:09–05:13)完全沒有 PM 時,rApp 就不做任何判斷,「ME 斷線就撤」「PM 缺太久就撤」兩條保護都沒觸發;dry-run 的節能狀態從上一場帶進了這一場。
- **影響**:現在是 dry-run,只是日誌狀態不對。如果是 LIVE,policy 會跨過兩場 run 留著。
- **修正**:超過 90 秒沒有判斷,就用一個空的時段判斷一次。ME 斷線時立刻撤;ME 還連著但缺 PM,連續 3 期才撤。另外,「UE 流失就撤」加上最低 4 個 UE 的基準,避免 UE 很少時誤判。17 項離線測試通過。
- 在 mitlab 執行 `deploy.sh` 之前,叢集上的 rApp 不會有這些修正;不影響這場 run。
