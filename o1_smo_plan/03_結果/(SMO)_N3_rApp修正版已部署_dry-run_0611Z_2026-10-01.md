# (SMO) N3 rApp 修正版已部署(dry-run,2026-10-01 06:11Z)

- 日期:2026-10-01 06:13Z
- 回覆:`04_問題/已回覆/(DT)_mitlab決定_rtmgr採A_N3_rApp修正版可部署dry-run_2026-10-01.md`
- 依據:mitlab 同意部署,模式維持 dry-run(05:55Z,經 DT 轉達);切 LIVE 前仍要另外請 mitlab 核准

## 1. 版本與時間

| 項目 | 內容 |
|---|---|
| 部署 | SMO 執行 `SMO_OSC/dep/n3-es-rapp/deploy.sh dry-run`,pod `n3-es-rapp-64cf86bb97-mvbrn` 於 **06:11:12Z** 啟動,`LIVE=false` |
| 程式版本(sha256 前 12 碼) | `rapp.py` **148e96a2e92a**、`rapp_logic.py` **e53e45db8a85**;已確認叢集 ConfigMap 裡的內容跟本機相同 |
| DME 工作 | `n3-es-rapp` 重新註冊 HTTP 201,送往 `n3-es-rapp-pm` |
| 設定 | 進入 < 30% 連 3 期、退出 > 70% 連 2 期、冷卻 300 秒、缺 PM 3 期撤、UE 流失(< 50%、連 3 期、基準至少 4 UE)撤、`dlPrbUsage` 60;範圍 `corridor` = e30 / e31 / e32 |

## 2. 這版包含的修正

| # | 修正 | 來源 |
|---|---|---|
| 1 | 同一分鐘各 DU 的報告對齊成同一時段 | 04:11 第一次在線運作時發現 |
| 2 | 解析 DT 的新命名(`measObjLdn` 相對於 ME,ME 從 `measuredEntityDn` 或 `sourceName` 取) | DT 04:37 通知;05:13 已用新命名的 PM 驗過 |
| 3 | 「UE 流失就撤」(覆蓋洞保護),加上至少 4 UE 的基準 | 節能第二測試的覆蓋洞;05:02 在線判斷時基準只有 2 UE |
| 4 | 沒有 PM 時也照時間判斷(避免狀態跨 run 帶著走) | 05:09–05:13 兩場 run 之間發現 |

**部署後驗證**:06:12:42Z 沒有 run、沒有 PM 時,rApp 仍判斷了一次空時段(`no PM … mes=DOWN`),修正 4 生效 ✅。17 項離線測試通過。

## 3. 接下來

- **T2**:DT 下一場 run 開始時請通知。SMO 會比對 rApp 的判斷(進入、選擇候選、撤除)跟實際負載。
- **T3**:等 DT 提「先低負載、再升高」的劇本草案。切到 LIVE 要另外請 mitlab 核准。
- rtmgr 採 (A):收到。8101 那兩筆的 clear 還沒到 SMO(見 `03_結果/(SMO)_回覆RIC_8101兩筆clear未到SMO_…`),等 RIC 查。
