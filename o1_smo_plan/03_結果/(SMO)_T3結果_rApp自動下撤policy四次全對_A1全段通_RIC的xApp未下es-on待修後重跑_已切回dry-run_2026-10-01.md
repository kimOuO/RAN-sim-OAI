# (SMO) T3 結果:rApp 自動下 / 撤 policy 4 次全部正確,A1 全段通;RIC 的 xApp 沒有下 es-on(cell 沒關),待 RIC 修好後重跑;rApp 已切回 dry-run

- 日期:2026-10-01 12:54Z
- 回覆:`04_問題/已回覆/(DT)_T3_LIVE_run_M開始_00bba8b4-121214Z_流量0.2至1228Z_4Mbps至1243Z_2026-10-01.md`
- run M:`00bba8b4-20261001T121214Z`(12:12:01–12:52:01Z),rApp LIVE 12:10:39–12:53:48Z
- 完整紀錄:`SMO_OSC/dep/n3-es-rapp/t3/t3_trace_20261001.log`(rApp 每期判斷、PMS / RIC-A 每 15 秒、O1 每 15 秒、SDNR)
- 請 DT 轉達 RIC 團隊

## 1. 時間軸(SMO 側)

| 時刻(UTC) | 事件 | 結果 |
|---|---|---|
| 12:12:30 | corridor 三個 ME 上線,O1 e30 / e31 / e32 都 ENABLED | |
| **12:16:06** | **rApp 自動 PUT** `smo-n3-corridor`(e32/0 節能,FORBID e30/0、e31/0):12:14–12:16 連 3 期平均 < 30% | PMS **201** |
| 12:16:19 | PMS `ENFORCED`;RIC-A 清單有這個 policy | ✅ PUT 到 ENFORCED ≤ 13 秒 |
| 12:16–12:30 | **e32 一直是 ENABLED**;DT 沒有收到 es-on | ❌(RIC xApp) |
| 12:28 | B 階段(4 Mbps);SDNR e30 / e31 `THRESHOLD_CROSSED`(負載告警,反覆舉起和清除) | 預期內 |
| **12:30:06** | **rApp 自動 DELETE**:e30/0、e31/0 連 2 期 > 70% | PMS **204**;DT 同一秒收到 es-off ✅ |
| 12:30:19 | PMS 與 RIC-A 都沒有 policy | ✅ |
| 12:43–12:44:37 | C 階段(0.2 Mbps);負載告警全清,SDNR 0 | ✅ |
| **12:46:06** | **rApp 第二輪自動 PUT**(12:44–12:46 連 3 期低負載;冷卻在 12:35 就已結束) | PMS **201** |
| 12:46:09 | PMS `ENFORCED`、RIC-A 有 policy | ✅(3 秒) |
| 12:46–12:52 | **e32 仍 ENABLED** | ❌(同上) |
| 12:52:31 | run 收場,ME 斷線 | |
| **12:53:36** | **rApp 自動 DELETE**:ME 斷線(沒有 PM 也照時間判斷,收場後約 1.5 分鐘) | PMS **204** |
| 12:53:46 | PMS / RIC-A 都沒有 policy | ✅ |
| 12:53:48 | SMO 執行 `deploy.sh dry-run` 切回;PMS service `smo-n3-es-rapp` 隨 rApp 停止一併移除 | ✅ |

## 2. 驗收點(DT 草案第 3 節)

| # | 驗收點 | 結果 |
|---|---|---|
| 1 | 進入節能的時刻與候選 | ✅ 開始後約 4 分鐘(12:16),候選 e32/0(UE 最少、ENABLED);第二輪 12:46 也一樣 |
| 2 | PUT → es-on → cell 關閉 ≤ 5 秒;O1 DISABLED;PM 歸零 | ❌ **PUT → ENFORCED 正常,但 es-on 沒送**,e32 沒有關,O1 沒變 DISABLED |
| 3 | 覆蓋洞保護 | 不適用(cell 沒關);全程 UE 合計和重建次數都正常(例如每期重建合計 5–20),沒有誤觸發 ✅ |
| 4 | DELETE → es-off → cell 開回 ≤ 5 秒 | ✅ 12:30:06 DELETE,DT 同一秒收到 es-off(cell 本來就開著,所以是冪等) |
| 5 | SDNR 沒有殘留告警;收場後 rApp 撤除 | ✅ 告警 12:44:37 歸 0;收場後 12:53:36 撤除 |
| 6 | 三方時間一致 | SMO 這邊:PUT 12:16:06 / 12:46:06,DELETE 12:30:06 / 12:53:36;DT 的 es-off 12:30:06 一致。es-on 沒有發生,無法比對 |

## 3. 結論

- **SMO / rApp / PMS / A1:T3 要驗的「rApp 自動決策並經 A1 下、撤 policy」全部通過**:4 次 PUT / DELETE,時機、原因、內容都對,而且每次都在 13 秒內反映到 RIC-A。
- **沒過的只有 RIC 的 xApp**:policy 到了,xApp 回 OK(ENFORCED),卻沒送 es-on;但 DELETE 時有送 es-off。所以問題在 **dt-a1-xapp 0.2.5 處理 CREATE 後的節能判斷**,不在路由。
- **需要重跑 T3**:RIC 修好 xApp 後,用同一劇本和參數再跑一場,驗驗收點 2(cell 真的關、O1 DISABLED、PM 歸零、鄰 cell 接手)。SMO 的 rApp 不用改;重跑前請 mitlab 再核准一次 LIVE(`deploy.sh live`)。

## 4. 給 RIC 的線索

- 兩次 CREATE 的 policy 內容一樣:scope [59539456, 59506688, 59523072]、FORBID [59506688, 59523072]、`dlPrbUsage` 60;候選 e32 的 PRB 在 0–8%(< 60)。
- 跟 04:30 節能第二測試的差別:那次是 SMO 手動下、沒有 `dlPrbUsage`、xApp 是 0.2.5 之前的版本。**請 RIC 檢查 0.2.5 在有 `dlPrbUsage` 時的 eligible 判斷**(例如 observation 有沒有 mid 的 PRB、單位是不是 %,或判斷式的方向)。
