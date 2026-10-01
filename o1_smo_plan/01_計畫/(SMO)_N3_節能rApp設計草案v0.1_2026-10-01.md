# (SMO) N3 節能 rApp 設計草案 v0.1:依 O1 PM 自動下 / 撤節能 policy

- 日期:2026-10-01 03:20Z
- 來自:SMO 端(10.3.0.204)
- 依據:mitlab 決定(`04_問題/已回覆/(DT)_mitlab決定_下一步並行N3與節能第二測試_0200Z那份不補_2026-10-01.md`)、計畫 v0.2 的 N3
- 狀態:**草案,第 7 節的四個決定點要 mitlab 確認後才開始部署**。先寫程式和離線測試,不動叢集

## 1. 要做的事

N2a 是「人決定、SMO 手動下 policy」。N3 改成由 rApp 做這件事:
1. 讀 O1 的 cell PM;
2. 判斷「整片負載低,可以關一個 cell」;
3. 透過 PMS 下 `ORAN_EnergySaving_4.0.0`(類型 30001)的 policy;
4. 負載回升時撤掉 policy,讓 cell 開回來。

真正關不關、何時關、UE 怎麼移,還是由 RIC 的 xApp 依 policy 執行。rApp 只決定「何時允許節能、範圍與排除清單」,符合 A1 的分工:non-RT 給目標,near-RT 做控制。

## 2. 資料來源(O1 PM)

| 用途 | 計數器(每個 `NRCellDU`,60 秒) | 已確認入庫 |
|---|---|---|
| 負載 | `RRU.PrbTotDl`(%) | ✅ |
| UE 數 | `DRB.MeanActiveUeDl`、`DRB.MaxActiveUeDl` | ✅ |
| 輔助 | `DRB.UEThpDl` | ✅ |
| RIC 是否健康 | `EP_E2=<gNB>` 的 `VS.E2Mgr.Connected`、`VS.E2T.RICcontrol*`(15 分鐘) | ✅ |

cell 的 A1 識別(PLMN + NCI)沿用 `a1_cellid.py` 的算法,從 SDNC 讀 O1 的 `gNBId`、`gNBIdLength`、`cellLocalId` 計算,不寫死。e00 這類 NCI 不正規的節點一律排除。

## 3. 判斷規則(初版,數值可調)

以「一個劇本的 cell 集合」為範圍(scope),每 60 秒評估一次:

| 狀態 | 條件 | 動作 |
|---|---|---|
| 進入節能 | 範圍內所有 cell 的 `RRU.PrbTotDl` 平均 < **30%**,連續 **3** 個週期;而且 RIC 的 E2 連線正常 | 選 `DRB.MeanActiveUeDl` 最小的 cell 當候選,其餘 cell 列入 FORBID;`PUT` policy |
| 維持 | 沒有觸發退出條件 | 每週期查一次 policy 狀態(ENFORCED / NOT_ENFORCED)並記錄 |
| 退出節能 | 任一個仍開著的 cell `RRU.PrbTotDl` > **70%**,連續 **2** 個週期;或範圍內有 ME 斷線;或 PM 缺資料超過 3 個週期 | `DELETE` policy |
| 冷卻 | 每次下或撤之後 **5 分鐘**內不再變動 | 避免來回切換 |

- 為什麼用「連續 N 個週期」:60 秒 PM 會有雜訊,只看一個週期容易誤判。
- 為什麼 PM 缺資料就撤:看不到負載時,保守的做法是讓 cell 開著。

## 4. 安全設計

1. **預設 dry-run**:只記錄「會做甚麼」,不下 policy。mitlab 核准後才切到 live。
2. **PMS keep-alive**:rApp 用 service `smo-n3-es-rapp` 註冊並定期 keep-alive。rApp 掛掉時,PMS 會自動刪掉它的 policy,cell 就開回來。這是 PMS 內建的機制,不必另外寫。
3. **同一範圍最多一個 policy**;每個 policy 的 ID 都以 `smo-n3-` 開頭,方便辨認和清理。
4. **停用開關**:把 Deployment 縮成 0 時,rApp 先刪掉自己的 policy 再結束。
5. **e00 永不納入**。
6. 跟 ME 生命週期 controller 不衝突:ME 下線時,controller 原本就會清 PMS 的孤兒 policy。

## 5. 放在哪裡、怎麼部署

- 程式放在 `SMO_OSC/dep/n3-es-rapp/`,用 Python,跟 `o1-me-lifecycle-controller` 同一種結構:`rapp.py`、`test_rapp.py`、`deploy.yaml`、`deploy.sh [dry-run|live|status]`。
- 叢集裡是 `smo` namespace 的一個 Deployment。
- 包成 OSC rAppManager 的正式 rApp 套件留到 N5,第一階段不做。

## 6. 測試步驟

| 步驟 | 內容 | 要誰 |
|---|---|---|
| T1 | 離線測試:用 N2a 那場 run 錄下的 PM 重播,檢查進入、退出、冷卻、缺資料各種情況 | SMO |
| T2 | 在 DT 的 run 上跑 dry-run,比對 rApp 的判斷和實際負載 | SMO、DT |
| T3 | live:DT 設計「先低負載再升高」的劇本,驗證自動下 policy 到 cell 關,再自動撤到 cell 開 | 三方 |

## 7. 要 mitlab 決定

| # | 問題 | SMO 建議 | 為什麼 |
|---|---|---|---|
| 1 | PM 從哪裡讀 | **A:向 DME(ICS)開一個 PmData 的資訊工作,直接收 Kafka 的 PM**(跟 pmlog 同一種方式);B:定期查 InfluxDB | A 是 O-RAN 定義給 rApp 用的資料路徑(R1 的資料管理),不依賴 InfluxDB;B 較簡單,但 InfluxDB 重開機後會清空(沒有 PVC) |
| 2 | 門檻 | 進入 < 30%(連 3 期)、退出 > 70%(連 2 期)、冷卻 5 分鐘 | 依 9/30 那場 run 的負載(src 約 32%、nbr 約 35%、mid 約 9%),先保守,T2 後再調 |
| 3 | 部署形式 | 第一階段用一般 Deployment,正式 rApp 套件留到 N5 | 先驗證判斷邏輯,包裝之後再做 |
| 4 | 範圍怎麼定 | 自動找出同一個劇本的 cell,但每個劇本要在設定裡「開啟」才會動作 | 避免 rApp 對還在除錯的劇本下 policy |

預計時程:離線版加 T1 約 1 天;T2、T3 依 DT 的劇本時間安排。
