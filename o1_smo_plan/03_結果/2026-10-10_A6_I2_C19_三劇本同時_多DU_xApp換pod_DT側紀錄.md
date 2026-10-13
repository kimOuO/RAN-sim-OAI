# A6 / I2 / C19 —— 三劇本同時、多 DU、xApp 換 pod(DT 側紀錄)

- 日期:2026-10-10(T0 = 08:00Z)
- 狀態:DT 側紀錄完成;SMO、RIC 完整結果另見其 `03_結果/` 與訊息
- 計畫:`04_問題/(DT)_驗證A6_I2_C19_…_測試計畫_2026-10-10.md`、`04_問題/(DT)_mitlab核准三項_…_2026-10-10.md`
- 前置:RIC 停用 dt-exec R2(EXEC_PRB_HIGH_PCT 40 → 101,06:12:57Z 起,維持中);SMO rApp dry-run;SMO PM 鏈 07:37Z 修復

## 1. 開場與收場

| 劇本 | runId | 區塊 | ME | 開場(UTC) | 收場(UTC) |
|---|---|---|---|---|---|
| S1 corridor24_16_24 | 00bba8b4-20261010T080012Z | 3 | e30 / e31 / e32 + du1 / du1 / du2(6) | 08:00:00–08:00:15 | 08:31:00–08:31:57(手動) |
| S2 osm_ntust_test | 3c2161db-20261010T080316Z | 5 | e50 / e51 + du1 ×2(4,每 DU 3 cell) | 08:03:00–08:03:18 | **08:13:23 劇本跑完自動收場**(劇本長度 600 s,排程疏失) |
| S3 mdu_corridor_test | 89a45a6e-20261010T080617Z | 6 | e60 / e61 / e62 + e60_du1、**e60_du2**、e61_du1、e62_du2(7) | 08:06:00–08:06:23 | 08:28:00–08:29:00(手動) |

- 同時在線 ME:17(另有常駐 e00 的 2 個)。三場收場後 O1、CU、DU 容器皆清空,僅剩常駐 e00 的 O1。
- 測完已停用 60 秒 PM 覆寫:`run_logs/_o1_overrides.json` 改名為 `_o1_overrides.json.used_20261010`,之後的 run 恢復 900 秒。

## 2. A6(多劇本同時)

| 項目 | 結果 |
|---|---|
| O1 容器數 | 17 adapter + 8 facade,全部 Running |
| 劇本自然結束(S2) | SMO 控制器 08:13:33–08:13:41(8 秒)只清 S2 的 4 個 ME,S1、S3 不受影響 |
| 手動停場(S3、S1) | O1 容器全數移除;SMO 側結果待其報告 |
| **異常:e62 兩個 ME 的 netopeer2-server 消失** | `o1adapter-cucp-89a45a6e-2`(埠 2026)與 `o1adapter-du-89a45a6e-2`(埠 2027)啟動時印出「Starting netopeer2-server」,之後行程不存在、日誌無錯誤;SSH 連線被 reset。adapter 本體(VES 心跳)正常。SMO 控制器約 08:16Z 依寬限下線。e62 為 S3 最後啟動的 gNB,推測與多顆 adapter 同時初始化 sysrepo 有關;**容器已隨收場移除,日誌無法再查**,需重現 |
| VES 逾時 | 08:07、08:10Z 數顆 adapter 的 notifyFileReady 出現 `Timeout was reached`;SMO 表示 collector 該時段無錯誤紀錄,待對照 |

## 3. I2(一個 gNB 兩個 DU)

| 項目 | 結果 |
|---|---|
| O1 | e60 兩個 DU ME `e60_du1`(cell src,NETCONF 2023)、`e60_du2`(cell spare,NETCONF 3047,相差 1024)皆起並可讀 |
| E2 | e60 一個 E2 node 帶兩個 cell(e60:src NCI 0x3980000、e60:spare 0x3980001),RIC 正常訂閱 |
| RIC 側(08:40Z) | e60:spare 在 ran_func 5 pm_cell 1156 筆、ran_func 6 anr_kpm 1157 筆,與 e60:src 筆數相同、數值獨立 → 第二個 DU 的 cell 兩個 ran_func 都有回報 |
| FULLKPM 第二個 DU 的 PRB | **無法判定**:e60:spare 全程 0 UE(1296 筆歸檔樣本最大連線 0、PRB 0),FULLKPM 有 e60:spare 這個 cell 但 PRB 0 屬正常。程式上 CU 的 `_fetch_du_dump_pm()` 只讀 `HTTP_DU_HOST`(第一個 DU),仍是待驗風險;需讓 spare 承載 UE 的情境再測(例:src 節能時 UE 轉到 spare) |

## 4. C19(dt-a1-xapp 換 pod)

DT 側時刻(CU 收到並 ACK = 歸檔 `run_control_event`;cell 狀態 = 每 3 秒取樣 `E2/CellState/read`):

| 事件 | SMO | inst | CU 收到 / ACK | e32:mid 狀態取樣 |
|---|---|---|---|---|
| 第一次 PUT | 08:10:01 | 188 es-on | 08:10:01.908(rtt 32.2 ms) | 08:10:04 isEnergySaving |
| DELETE | 08:11:01 | 189 es-off | 08:11:01.939(32.2 ms) | 08:11:04 active |
| RIC 換 pod(scale 0→1) | 08:12:00–08:12:34 | — | — | — |
| 第二次 PUT | 08:13:01 | 190 es-on | 08:13:02.220(96.9 ms) | 08:13:02 isEnergySaving |
| DELETE | 08:20:00 | 191 es-off | 08:20:03.450(29.2 ms) | 08:20:03.9 active |
| RIC 換 pod(補測) | 08:22:00–08:22:34 | — | — | — |
| 第三次 PUT | 08:22:35 | 192 es-on | 08:22:39.006(31.2 ms) | 08:22:38 isEnergySaving |
| DELETE | 08:27:00 | 193 es-off | 08:27:08.660(28.6 ms) | 08:27:10 active |

- 五次控制全數送達 RAN 並 ACK,mid 狀態與 O1 一致。
- **補回路徑未重現**:兩次「scale 0 → 舊 pod 消失 → scale 1」換 pod 後,PUT(隔 30 s / 3 s)都直接送到新 pod;20012 對帳每 60 秒運作中但無需補回。RIC:10/1 遺失發生在 helm 滾動換版後 a1mediator 舊連線殘留 9 分鐘;要重現需以 helm 滾動換版,另排。
- **RIC 側新發現**:inst 191 的 ACK 在 RIC 內延遲 10 秒(dt-a1-xapp 自己成為 12041 轉送者、同執行緒等待 rc-probe),dt-a1-xapp 判逾時並回 a1mediator ERROR;RAN 端 08:20:03.45 已執行。RIC 將於 xApp 端修正(RMR 收取與控制呼叫分執行緒)。

## 5. 待辦

1. e62 netopeer2 消失:以多劇本同時開場重現,保留容器日誌;必要時 adapter entrypoint 加 netopeer2 存活檢查與重啟。
2. 多 DU 的 FULLKPM PRB:設計讓第二個 DU 承載 UE 的情境驗證;或先改 CU 依 DuRegistry 逐 DU 讀 dump_pm。
3. C19 補回路徑:以 helm 滾動換版重現(RIC / SMO 排時間)。
4. dt-exec R2 維持停用,恢復時機待 rApp 門檻定案(C20)。
5. 排程前核對劇本長度(S2 600 s)。

## 6. SMO 結果(08:46Z,`03_結果/(SMO)_A6_I2_C19結果_A6與I2通過_C19正常路徑三輪通過_補回路徑未重現_2026-10-10.md`)

- **A6 通過**:17 ME 同時在線無變慢;每場收場只清該 runId 的 ME;控制器錯誤 0 筆;onboard 首場約 55 秒(等 RIC E2 清單)、後兩場 1–7 秒;PMS `ric-dt-71` 清單隨劇本增減正確;S2 每 DU 3 cell 的 InfluxDB / TEIV 正確;收場後只剩 e00。
- **I2 通過**:e60_du1 / e60_du2 各自 mount、TEIV 兩個 GNBDUFunction、InfluxDB series 各自獨立。小問題:**e60_du2 → e60 的 F1 連結在 TEIV 每 90 秒被控制器重建(約 14 次)**,推測同 CU 兩 DU 時 F1 關聯在 NCMP → TEIV 互相覆蓋;SMO 查控制器比對邏輯與 adapter。
- **C19**:正常路徑三輪通過(PUT 後 1–10 秒關、DELETE 後 3 秒開);補回路徑未重現。
- **e62**:SMO 控制器 08:16:41 依 600 秒寬限自動下線,收場無殘留;e62 的 PM 仍有入庫(SFTP 不依賴 NETCONF)。
- **VES 逾時**:collector 無錯誤紀錄;SMO 建議 DT 檢查 adapter 端 curl 逾時設定(17 顆同時送)。
- 待辦追加:6. adapter 的 VES curl 逾時設定;7. (SMO)多 DU 的 F1 連結重建問題。
