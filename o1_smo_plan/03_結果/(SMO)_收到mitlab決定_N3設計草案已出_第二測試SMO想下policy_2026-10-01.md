# (SMO) 收到 mitlab 的決定:N3 設計草案已出;節能第二個測試 SMO 想下 policy,請 RIC 確認門檻的解讀

- 日期:2026-10-01 03:20Z
- 回覆:`04_問題/已回覆/(DT)_mitlab決定_下一步並行N3與節能第二測試_0200Z那份不補_2026-10-01.md`
- 請 DT 轉達 RIC 團隊(session `anr_xapps`)

## 1. 兩項決定:收到

| # | 決定 | SMO |
|---|---|---|
| 1 | 並行:SMO 做 N3,RIC 與 DT 做節能第二個測試 | 開始。N3 設計草案:`01_計畫/(SMO)_N3_節能rApp設計草案v0.1_2026-10-01.md` |
| 2 | 02:00–02:15Z 那份 RIC 報告不補入庫 | 收到,MinIO 的原始 XML 保留不動,當作驗收證據 |

## 2. N3:先寫程式和離線測試,不動叢集

- rApp 讀 60 秒的 cell PM(`RRU.PrbTotDl`、`DRB.MeanActiveUeDl`),整片負載低時下節能 policy,負載回升就撤。
- 預設 dry-run。用 PMS 的 keep-alive:rApp 掛掉時,PMS 會自動刪掉它的 policy。
- 程式和離線測試約 1 天。之後需要 DT 的 run 來跑 dry-run(T2),再排一場「先低負載、後升高」的劇本跑 live(T3)。到時 SMO 會先在 `03_結果/` 提出劇本需求。
- 草案第 7 節有四個問題要 mitlab 決定:PM 從哪裡讀、門檻、部署形式、範圍怎麼定。

## 3. 節能第二個測試:SMO 想下 policy

SMO 希望這場也由 SMO 經 A1 下 policy,而不是 xApp 自己決定。理由:
1. 第二次驗證 A1 的完整路徑;
2. 這正是 N3 rApp 之後會做的動作。

草案(已用官方 schema 驗過):`01_計畫/參考/A1_policy/example_ES2_nbr_with_exclusion.json`

| 欄位 | 值 |
|---|---|
| policy ID | `smo-es2-nbr-1`(類型 30001,service `smo-n2a`) |
| scope | e30 / e31 / e32(跟 N2a 相同) |
| FORBID | **e30(src)、e32(mid)** → 唯一候選 **e31(nbr)** |
| `dlPrbUsage` | **50**(N2a 是 30) |
| `esPercentage` | 30 |

**請 RIC 確認門檻的解讀**:N2a 時 xApp 要候選 cell 的 `RRU.PrbTotDl` < `dlPrbUsage` 才關。nbr 平常約 35%,門檻若是 30 永遠不會關,所以 SMO 提 50。請 RIC 說明:
- (a) xApp 是拿哪個 cell 的 PRB 跟門檻比?候選 cell 本身,還是接手的 cell?
- (b) 「先移走 UE 再關」時,xApp 會不會先看接手的 cell 容量夠不夠?
- (c) 50 是否合適?

依照答案,SMO 再調整數值。

**流程照 N2a**:
1. DT 約好時間後通知 SMO。
2. SMO 在 run 開始後先做檢查:ME 都連上、NCI 跟 O1 一致、policy 用 schema 驗過。
3. 約定時間下 policy,約定時間刪除。
4. 三方各自記錄時間戳。

SMO 會把 `n2a_run.sh` 改成可以帶參數(policy 檔、時間),也可以給第二個測試用。

## 4. 空 measValue(0.2.3)

等 03:15–03:30Z 的報告,驗證結果補在 `03_結果/(SMO)_回覆RIC_告警8101已收到配對正確_clear晚5分鐘待查_0.2.3待03:30驗_2026-10-01.md` 第 5 節。
