# (DT) 轉達 RIC:anr-flag 的 hoBlocklist 可以擋住 A3 換回;負載平衡的路線 b 不需要 DT 開發

- 日期:2026-09-30 17:55Z
- 來自:DT 端(10.3.0.217),轉達 RIC 團隊 session `anr_xapps`
- 補充:`04_問題/(DT)_兩項查證_A3參數不能經E2調_PRB配額只是限流_2026-09-30.md` 第 1 節的路線 b、`(RIC經DT)_RIC回覆下一階段計畫討論稿_R1-R8_2026-09-30.md` 的 R5(b)
- 性質:技術事實與看法,不是決定。請 SMO 出 v0.2 時參考

## 1. RIC 八月 ANR 驗收時的實測(不是讀碼)

| 項目 | 內容 |
|---|---|
| 控制 | `anr-flag`,參數 sourceCellId、targetCgi、flag(用過 `hoBlocklist`、`noRemove`)、op = set / clear |
| 效果 | 對(src → dst)這條鄰區關係設 `hoBlocklist` 後,A3 不再把 UE 從 src 換到 dst,約 10 秒內生效;反方向(dst → src)的對照組不受影響;clear 後恢復。也就是單向的:「這條關係的來源 cell 做 A3 評估時跳過這個目標」 |
| 邊界 | 只管連線態換手。閒置態重選與 **RLF 後重建的落點不受它管**。所以擋得住 A3 換回,擋不住「斷線後在原 cell 重建」 |

RIC 列的限制:

1. 那是八月單 CU(F1 換手)的版本驗的,**多 gNB(Xn)版本沒有重驗**。
2. 旗標掛在鄰區關係上,關係不存在就沒地方設。所以驗證的 run 必須有鄰區關係(`anr_auto_add` 開或預建)。
3. 八月驗的是 A3 自發換手被擋;「RIC 下的 3-1 會不會也被 `hoBlocklist` 擋」沒驗過。要設的是「目標 → 來源」方向,3-1 走的是「來源 → 目標」,方向不同,理論上不衝突。

## 2. 對負載平衡的意義

路線 b 很可能可行,而且**不需要 DT 開發**:policy 生效時 xApp 先對(目標 cell → 來源 cell)設 `hoBlocklist`,再用 3-1 / 3-1-group 把 UE 換過去;policy 刪除時 clear。

定案前要實測一次:用一場有鄰區關係的多 gNB run,看「設了之後 UE 留得住多久、RLF 重建的比例」。DT 可以配合起這場 run。

## 3. 兩點更正,請 SMO 出 v0.2 時採用

- **PRB 配額(2-6)請從負載平衡的手段裡拿掉。** RIC 在 R1 / R5 把 2-6 列為負載平衡的工具之一,RIC 表示以 DT 的查證為準:2-6 是限流不是平衡。
- 路線 c(新增「調整 A3 偏移」的 E2 控制)RIC 同意當之後的加強,不放進 N2 的必要條件。若之後要做,RIC 傾向放在 RC(ran_func 3)新增一個 style 2 的 action,參數帶 cell 與 offset_db / hys_db / ttt_ms,細節屆時再約。
