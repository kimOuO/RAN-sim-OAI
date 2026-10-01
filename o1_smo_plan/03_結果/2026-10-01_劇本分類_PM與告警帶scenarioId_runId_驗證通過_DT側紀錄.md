# 劇本分類(治本):PM 與告警帶 scenarioId / runId —— 驗證 run 通過,DT 側紀錄

- 日期:2026-10-01(mitlab 05:00Z 決定「資料本身帶劇本,治本;參考 RIC 與 DT 的做法」)
- 驗證 run:`00bba8b4-20261001T051106Z`,`corridor24_16_24`,seed 12,PM 60 秒,05:10:53–05:36:19Z
- SMO 結果:`03_結果/(SMO)_劇本分類驗證run通過_四項全過_…_2026-10-01.md`(05:22Z)
- **結論:DT 自檢三項 + SMO 四項全部通過;SMO 端不需再改任何東西。待辦 A1 / A3 完成。**

## 1. 問題
SMO 收到的 PM 與告警只帶 ME 名稱,ME 名稱又會被不同劇本的 run 重用;只有 pnfRegistration / notifyMOIDeletion 帶 scenarioId / runId。SMO 端無法直接按劇本切資料(A1)。

## 2. 做法(對照 DT ↔ RIC:閘道以 `scenarioId` + `labels.scene_name` 分類)
| 資料 | 改動 | 規範依據 |
|---|---|---|
| PM `fileSender localDn`、`managedElement localDn` | `SubNetwork=<scenarioId>,ManagedElement=<me>`(`dnPrefix` 仍 `SubNetwork=DT`) | TS 32.435 V17:DN = dnPrefix + localDn;範例 `localDn="SubNetwork=CountryNN,…,ManagedElement=…"`;TS 28.622 SubNetwork 可巢狀 |
| PM `managedElement userLabel` | `runId=<runId>` | 32.435 選用自由文字 |
| PM `measObjLdn` | `GNBDUFunction=<N>,NRCellDU=0`(相對 ME;原本重複帶 ME) | 32.435 範例 `measObjLdn="RncFunction=RF-1,UtranCell=…"` |
| 告警 `notifyNewAlarm data.additionalInformation` | `{"scenarioId": …, "runId": …}` | TS 28.111 選用欄位(AttributeNameValuePairSet);`notifyClearedAlarm` 無此欄位,不加 |
| 常駐節點(e00) | 不加 SubNetwork 層,userLabel / additionalInformation 標 `permanent` | — |

- 實作:`02_測試/o1-adapter-dt/config/pmData-measData.xml`(`@dn-scn@`、`@run-label@`)、`config/ves-new-alarm.json`(`@scn-id@`、`@run-id@`)、`dt-entrypoint.sh`(依 `O1_SCENARIO_ID` / `O1_RUN_ID` 代入);映像 `adapter-gnb:dt` 重建。不改 C 程式。
- SMO 入庫(pmlog,`_measurement = fileSender.localDn + "," + measObjLdn`)結果:**`SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e31_du1,GNBDUFunction=1,NRCellDU=0`**。runId 刻意不放進名稱(避免每 run 一組 series);按 run 用 A2 的 run 對照表。
- 歷史資料(09-29 至 10-01 05:09)名稱為 `ManagedElement=<me>,ManagedElement=<me>,GNBDUFunction=…`。

## 3. 驗證
| # | 項目 | DT 自檢 | SMO |
|---|---|---|---|
| 1 | PM XML 欄位(三個 DU 第一份 05:12–05:13 檔) | ✅ DN / userLabel / measObjLdn 正確,7 項有值(e30 3 UE/43 %、e31 5/44 %、e32 0/3 %) | (a) ✅ 新 `_measurement` 與預期完全相同、有值;05:10 起無舊格式 |
| 2 | 告警(05:20:02Z 停 e31 facade 30 秒) | ✅ CU/DU adapter 各一筆 notifyNewAlarm 帶 additionalInformation,VES 202;05:20:43 恢復後各一筆 notifyClearedAlarm | (b) ✅ VES 原文帶兩欄位;SDNR 05:20:16 Major → 05:20:47/48 NonAlarmed,配對正確 |
| 3 | 轉換器 | — | (c) ✅ pm-file-converter 無錯,MinIO 每分鐘有 JSON |
| 4 | DME → N3 rApp | — | (d) ✅ rApp 05:13 起每分鐘解析出三個 cell |

## 4. 附帶
- SMO 依劇本查詢:`r._measurement =~ /^SubNetwork=<scenarioId>,/`;N3 第 7 節第 4 項「自動辨識劇本範圍」可直接用 SubNetwork。
- SMO N3 rApp 發現缺口:兩場 run 之間無 PM 時不做判斷,dry-run 狀態跨 run 帶過;已修(90 秒無判斷即空判斷一次;UE 流失退出加最低 4 UE 基準),待 mitlab `deploy.sh`。
- RIC 05:15:23Z 兩筆新 8101(上一場 run 的劇本 xApp 端點),已轉 RIC 確認。
- 樣本:`02_測試/pm_v1/xml_scn/`。
