# (DT) T3 兩場 DT 側總結:閉環各段驗畢;遺留 C20(dt-exec 限流與 rApp 退出門檻牴觸)待三方定

- 日期:2026-10-01 16:15Z;run N 16:09:34Z 收場。完整紀錄如下(同 `03_結果/2026-10-01_N3_T3_LIVE_rApp自動節能閉環_DT側紀錄.md`);請 SMO 補 run N 的 PMS ENFORCED 時刻、收場 DELETE 時刻、切回 dry-run 時刻。

- 參與:SMO(N3 rApp LIVE、PMS)、RIC(a1mediator、dt-a1-xapp 0.2.5→0.2.6、dt-preproc 0.1.8、dt-exec)、DT(corridor24_16_24、CU 流量覆寫腳本 `02_測試/n3_t3/t3_load.py`、O1)
- **結論:閉環每一段都已在 LIVE 下各自驗到**:rApp 自動 PUT(4 次)→ A1 → xApp es-on → gNB 關 cell → O1 回報 DISABLED;rApp 自動 DELETE(高負載 / ME 斷線)→ es-off。中間暴露 RIC 三個平台問題(兩個已修、一個待定),詳見第 4 節。

## 1. 兩場 run

| | run M `00bba8b4-20261001T121214Z` | run N `00bba8b4-20261001T152921Z` |
|---|---|---|
| 流量(每 UE) | 0.2 → 4.0 → 0.2 Mbps(15 / 15 / 10 分) | 同 |
| rApp PUT | **12:16:06** ENFORCED 12:16:19;第二輪 **12:46:06** ENFORCED 12:46:09 | **15:33:06**(20010 遺失,NOT_ENFORCED) |
| es-on 到 DT | 無(RIC dt-preproc 撞號 → 無 PRB → xApp policy-wait) | **16:02:17**(RIC 16:00:30 重啟 xApp 補拿 policy)→ p17 Xn 換到 src → mid isEnergySaving;**16:02:19 O1 e32 DISABLED / INACTIVE**;16:02–16:09 mid 0 UE |
| rApp DELETE | **12:30:06**(src/nbr 連 2 期 > 70 %)→ DT 同秒 es-off;12:53:36(ME 斷線) | B 期無(dt-exec 2-6 把 PRB 壓在 ≤ 50 %,未達 70 %);run 停後 ME 斷線撤 |
| PRB A / B 期 | A 2–30 %;B 76–100 % | A 1–17 %;**B 41–55 %(被限流)** |

## 2. 驗收點(草案第 3 節)
| # | 驗收點 | 結果 | 證據 |
|---|---|---|---|
| 1 | rApp 自動進入、候選正確 | ✅ | run M 12:16:06 / 12:46:06、run N 15:33:06,候選皆 e32 mid(0 UE) |
| 2 | PUT → es-on → cell 關 ≤ 5 s;O1 DISABLED;PM 歸零 | ✅(run N) | 16:02:16 xApp 收 CREATE → 16:02:17 es-on ACK → CU 同秒關 → 16:02:19 O1 DISABLED;16:03 起 e32 PM 0 |
| 3 | 覆蓋洞保護不誤觸發 | ✅ | 兩場 UE 合計、重建次數皆正常 |
| 4 | DELETE → es-off → 開回 ≤ 5 s | ✅(run M) | 12:30:06 DELETE,DT 同秒 es-off |
| 5 | SDNR 無殘留;收場 rApp 撤除 | ✅ | run M 12:44:37 告警歸 0、12:53:36 撤;run N 收場撤(SMO 補) |
| 6 | 三方時間一致 | ✅ | PUT / DELETE / es-on / es-off 皆同秒或 ≤ 13 s |

## 3. 從 PUT 到 cell 關閉的延遲
- 正常路徑(run N 補拿後):xApp 收到 → es-on → CU 關 → O1 更新:**≤ 3 秒**。
- 含 rApp 判斷:條件成立(連 3 期)後 ≤ 1 個 PM 週期內 PUT;PUT → ENFORCED ≤ 13 秒。

## 4. 暴露的問題(RIC 平台)
| # | 問題 | 狀態 |
|---|---|---|
| C18 | dt-preproc 場次起點查詢未限時間,與 9/22 同劇本 run 撞號 → 08:01Z 起 observation 無 cell PRB → xApp 對帶 dlPrbUsage 的 policy 一直 policy-wait(run M 兩輪)。同一根因使 dt-exec 整個下午不下 2-6(T2 校正因此量到 70–100 %) | **已修**:dt-preproc 0.1.8(限 12h)+ dt-a1-xapp 0.2.6(PRB 後備讀 KPM) |
| C19 | 換 xApp pod 後 a1mediator 送的第一筆 20010 寫進舊連線遺失(run N 15:33:06) | RIC 將加 xApp 每 60 秒 20012 對帳;不在 run 中換版 |
| **C20** | **dt-exec 的 2-6(PRB > 40 % → 上限 50 %)與 rApp 的「> 70 % 退出」牴觸**:只要 dt-exec 在,高負載退出永遠不會觸發 | **待三方定**:T3 期間 dt-exec 對該劇本停用 2-6,或 rApp 退出門檻改 50 %,或 rApp 把 dt-exec 的限流視為「負載已高」 |

## 5. 下一步
- C20 定案後可再跑一場「單場內完整 PUT → 關 → DELETE → 開」(目前兩段分別在兩場驗過)。
- SMO 建議正式長期 LIVE 前讓「高負載退出」不受 5 分鐘冷卻限制(G14)。
- 第二場驗覆蓋洞保護(候選落在 nbr)留待之後。
