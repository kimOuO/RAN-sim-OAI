# 驗證 A6 / I2 / C19 —— 測試計畫

- 日期:2026-10-10
- 狀態:SMO 已同意(05:10Z);RIC 已回覆(08:00Z 起可,需先清磁碟);待 mitlab 決定 T0
- 發起:DT(mitlab 指示「驗證 A6、I2、C19」)
- 對應待辦:A6 同時多劇本未實測、I2 多 DU 尚無劇本可驗、C19 dt-a1-xapp 0.2.7 漏收 policy 後對帳補回

---

## 1. 測試劇本(三場同時)

| 代號 | 劇本 | scene_run | 模式 | gNB / DU / cell | 預期 ME 數 |
|---|---|---|---|---|---|
| S1 | corridor24_16_24 | …00bba8b4 | cached 1× | 3 gNB、各 1 DU、各 1 cell | 6(3 CU-CP + 3 DU) |
| S2 | osm_ntust_test | …3c2161db | cached 1× | 2 gNB、各 1 DU、各 3 cell | 4(2 CU-CP + 2 DU,每 DU 3 個 NRCellDU) |
| S3 | mdu_corridor_test(新,自 livetest_corridor 複製) | …89a45a6e(scene_run-ab983bfd796f48659837773489a45a6e)| live 1× | 3 gNB;**src gNB 2 個 DU**(src_du0:cell src;src_du1:cell spare,已改為啟用) | 7(3 CU-CP + 4 DU) |

- 加上常駐 e00 的 2 個 ME,SMO 同時在線約 **19 個 ME**(SMO 控制器設計目標 20–30)。
- 每場的 E2 區塊於開場時分配,開場後於本檔「第 5 節 實際紀錄」補上 meid / ME 名稱 / runId。
- PM 週期:`_o1_overrides.json` 仍為 `{"pm_interval": 60}`,本次沿用 60 秒,測完恢復 900。

## 2. 時間線(T0 = 雙方確認後約定的開始時間)

| 時間 | 動作 | 驗證 |
|---|---|---|
| T0 | 起 S1 | — |
| T0+3 | 起 S2(S1 運作中) | A6:新增 ME 時既有 ME 不受影響 |
| T0+6 | 起 S3(S1、S2 運作中) | A6、I2 |
| T0+10 ~ T0+25 | 三場同時運作 | A6 穩態;C19 於此區間進行(見第 4 節) |
| T0+25 | 停 S2(其餘運作中) | A6:單一劇本下線時只移除該劇本 ME |
| T0+28 | 停 S3 | 同上 |
| T0+31 | 停 S1 | 全數下線,只剩 e00 |
| T0+45 | SMO 確認清理結果 | 收工 |

## 3. A6 / I2 驗收項目

**SMO 側**
1. SDNC:各 ME 皆 mount 成功;S3 src gNB 的兩個 DU ME 各自 mount,各有 1 個 NRCellDU。
2. InfluxDB:每個 DU ME 各自有 PM series;`SubNetwork=<scenarioId>` 三個劇本各自可分開查;S3 兩個 DU 的 series 不互相覆蓋。
3. 告警:各劇本告警帶各自的 scenarioId / runId;無跨劇本誤配。
4. TEIV:三個劇本的 gNB、DU、cell 皆出現;S3 src gNB 下有 2 個 DU。
5. 生命週期:每停一場,只移除該劇本的 ME(notifyMOIDeletion → 控制器 unmount);其餘劇本 ME 持續正常;最後 SDNR 告警清單歸 0(e00 除外)。
6. 控制器無錯誤日誌、無重複 mount、無殘留。

**DT 側**
1. 每場 O1 容器(facade + adapter)數量正確;S3 src gNB 有 `o1adapter-du-…` 與 `o1adapter-du-…-du2` 兩顆。
2. 每個 DU ME 的 NETCONF 讀得到自己的 NRCellDU 與三態;S3 兩個 DU 的 telnet 埠相差 1024。
3. 每場停止後,該場 O1 容器全數移除;其他場不受影響。

## 4. C19 驗收(dt-a1-xapp 0.2.7 漏收後對帳補回)

目標:重現「xApp 換 pod 後 a1mediator 第一筆 20010 遺失」,確認 0.2.7 於 60 秒內以 20012 對帳補回 policy,並對 DT 下 es-on。

建議流程(對象 S1 corridor24_16_24,候選關閉 cell = mid;細節以 RIC / SMO 意見為準):

| 時間 | 誰 | 動作 |
|---|---|---|
| T0+12 | RIC | 重啟 / 換 dt-a1-xapp pod(重現換 pod 情境) |
| T0+13 | SMO | 手動 PUT 節能 policy(類型 30001,scope = S1 的 mid cell NCI;不依 rApp、不設 dlPrbUsage 門檻,避開 C20) |
| ≤ T0+15 | RIC | 記錄:20010 是否到 xApp;若未到,20012 對帳何時補回 |
| ≤ T0+15 | DT | 記錄 es-on 到達時間、mid 關閉、O1 operationalState=DISABLED、UE 搬移 |
| T0+20 | SMO | DELETE policy |
| ≤ T0+21 | DT | 記錄 es-off 到達、mid 恢復、O1 ENABLED |

驗收:policy PUT 後 ≤ 90 秒內 DT 收到 es-on(含對帳補回路徑);DELETE 後 es-off 到達;三方時間線吻合。
若 20010 正常送達(未重現遺失),仍記錄為「正常路徑通過」,並請 RIC 評估是否需人為製造遺失再測一次。

## 5. 實際紀錄(開場後由 DT 補)

| 劇本 | runId | E2 區塊 | meid | ME 名稱 |
|---|---|---|---|---|
| S1 | | | | |
| S2 | | | | |
| S3 | | | | |

## 6. 請對方回覆

- **SMO**:可配合的 T0;第 3 節驗收項目是否需增減;C19 的手動 PUT / DELETE 是否可由 SMO 執行;rApp 本次維持 dry-run。
- **RIC**:可配合的 T0;三場同時接 RIC 的負載是否可以;C19 由 RIC 換 dt-a1-xapp pod 的方式與時間點。
