# (SMO) 節能第二測試:SMO 已排程,04:30:00Z 下 `smo-es2-nbr-1`、04:50:00Z 刪;不設 dlPrbUsage

- 日期:2026-10-01 04:12Z
- 回覆:`04_問題/已回覆/(DT)_節能第二測試開始_run_00bba8b4-040908Z_不設dlPrbUsage_0430Z下policy_0450Z刪_2026-10-01.md`
- 請 DT 轉達 RIC 團隊(session `anr_xapps`)

## 1. 門檻

照 mitlab 04:05Z 的決定:**不設 `dlPrbUsage`**(policy 檔 `example_ES2_nbr_no_dlPrb.json`;官方 schema 允許省略,已驗過,不需要填 100)。SMO 在 03:44Z 發的「門檻 60」由這個決定取代。

## 2. SMO 的排程(`es_run.sh`,已在背景執行)

| 時間(UTC) | 動作 |
|---|---|
| 04:13 | 預檢:6 個 ME 都 connected(04:12 已確認)、NCI 跟 O1 一致、schema 驗過;任一不符就不下 |
| **04:30:00** | `PUT smo-es2-nbr-1`(type 30001、service `smo-n2a`;scope e30 / e31 / e32;FORBID e30、e32 → 候選 e31;esPercentage 30) |
| 04:30–04:50 | 每 30 秒查 PMS 的 policy 狀態;逐分鐘記錄三個 cell 的 `DRB.MeanActiveUeDl`、`DRB.MaxActiveUeDl`、`RRU.PrbTotDl` |
| **04:50:00** | `DELETE smo-es2-nbr-1`,並確認 RIC-A 與 PMS 上都已刪除 |

## 3. 同時進行的 N3 rApp(dry-run,不下 policy)

N3 rApp `n3-es-rapp` 已在 04:00Z 部署,目前是 dry-run,範圍就是 e30 / e31 / e32。它這場只會在日誌裡記下「會不會、何時決定節能」,**不會下任何 policy**,不影響這場測試。SMO 會把它的判斷跟實際負載一起整理進結果,這就是 N3 的 T2。

結果預計 05:00Z 前後寫在 `03_結果/`。
