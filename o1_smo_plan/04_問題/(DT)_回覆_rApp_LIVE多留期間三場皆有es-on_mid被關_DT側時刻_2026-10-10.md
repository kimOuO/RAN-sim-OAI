# (DT) 回覆:rApp LIVE 多留期間,三場 corridor run 皆收到 es-on(mid 被關)

- 日期:2026-10-10
- 回覆:`03_結果/(SMO)_T3第二場補時刻_未及時切回dry-run事件說明_C20意見_2026-10-10.md` 第 2 節
- 資料來源:DT 編排服務歸檔資料庫 `run_control_event`(CU 實際收到並 ACK 的 E2 控制)

## 1. 結論

三個時段**都有**經 A1 → RIC → E2 CCC 送達的 es-on,e32:mid 被關閉,CU 皆回 ACK。期間**沒有**對應的 es-off(enable)紀錄;mid 持續關閉至該場 run 收場。

| run(scene_run …00bba8b4,corridor24_16_24) | RIC run | E2 控制到達 DT(UTC) | 內容 | 結果 | ricLabel |
|---|---|---|---|---|---|
| 2026-10-01 18:12Z 起 | 25 | **2026-10-01 18:16:07.93** | CCC control_cell_disable,cell e32:mid,instId 178 | ACK(rtt 36.9 ms) | `…|mid|g25|a1es-smo-n3-corridor-on` |
| 2026-10-02 12:28Z 起 | 26 | **2026-10-02 12:33:07.87** | 同上,instId 181 | ACK(rtt 110.4 ms) | `…|mid|g26|a1es-smo-n3-corridor-on` |
| 2026-10-07 02:38Z 起 | 27 | **2026-10-07 02:42:08.22** | 同上,instId 185 | ACK(rtt 32.3 ms) | `…|mid|g27|a1es-smo-n3-corridor-on` |

- 三筆 ricLabel 皆為 `a1es-smo-n3-corridor-on`,即 rApp policy `smo-n3-corridor` 觸發的節能。
- 三場其餘控制為 RIC 自身的 ANR CGI 解析與 dt-exec 2-6 限流(e30:src、e31:nbr,max_prb 50),與 A1 無關。
- 影響:這三場 run 的 mid cell 自開場約 4 分鐘後關閉;該期間的資料(KPM、PM、換手 / RLF)皆受節能影響,使用時需註明。

## 2. 給 mitlab 的待決定事項(SMO 提出,DT 轉呈)

1. SMO 改正方案:`deploy.sh live <時長>` 強制帶結束時間;切 LIVE 時在 `03_結果/` 寫預定切回時間。
2. C20 長期方案:rApp 高負載退出改為 ≥ 45% 連 2 期(或加吞吐量條件);測試期間 dt-exec 對該劇本停用 R2(2-6 限流)。
3. G14:高負載退出不受 5 分鐘冷卻限制。

## 3. 另:A6 / I2 / C19 驗證計畫

見同資料夾 `(DT)_驗證A6_I2_C19_多劇本同時_多DU_xApp補回policy_測試計畫_2026-10-10.md`,請回覆可配合的 T0。rApp 本次請維持 dry-run;C19 的 policy 建議由 SMO 手動 PUT / DELETE。
