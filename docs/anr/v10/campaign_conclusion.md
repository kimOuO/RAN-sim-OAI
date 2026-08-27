# E2SM-ANR v10 遷移暨十二題 Campaign 總結報告(sim 側)

> 2026-08-26 · RAN DT sim 團隊 · 對應 RIC 側總結(dt-anr-xapp 0.1.0-v10 build9,2026-08-26 03:25)
> 狀態:**v10 十二題全數在 live wire 完結**(2026-08-26 16:55:02 第 6 題收尾;RIC 側 dt-anr-xapp `0.1.7-v10`,離線測試 159)

## 一、Campaign 概述

目標:將模擬器與 RIC xApp 的 ANR 觀測/控制介面從 v8 遷移至 **ANR情境測驗_v10** 規格,
並以真實佈病 fixture 在 live E2 wire 上逐題驗證十二個 ANR 病徵的偵測→處置→恢復閉環。

歷時 35 輪往返(2026-08-25 ~ 08-26),四個工作段:
1. **fixture 輪**(第 8~15 輪):8 題非窗口 fixture 佈病、RIC 逐題拉真資料驗偵測
2. **換模組窗口**(第 16~20 輪):RC 內層切 RIC 預編譯模組(`RC_MODULE_V10`),
   Format 3(UE Group)全鏈路上線,三態(EXECUTED/PARTIAL/NO_MATCH)wire 實證
3. **v10 切換 + 病灶生命週期輪**(第 21~33 輪):`ANR_SCHEMA=v10` 上線、
   共存煙霧(閉環收斂 + 20 分靜默雙綠)、Q6/Q7/Q5/Q11 全循環
4. **閉環抽驗**(第 34~35 輪):Q1/Q10 在 wire 走完 偵測→RC→NRT 回讀→行為確認

## 二、十二題判定總表(sim 側證據)

| 題 | 病徵 | 驗法 | sim 側關鍵證據(時戳 08-25/26 UTC)|
|---|---|---|---|
| 1 | 缺漏鄰區 | 閉環抽驗 | 乾淨重跑:RLF 群 03:22~03:24 → ADD 03:24:36 → SUCC=4/FAIL=0 → RLF 歸零 |
| 2 | 換手縫隙 | fixture | s25→n35 關係剪除;PathSolver 實測窗(gap ≈ +0.1dB)|
| 3 | 深邊緣缺鄰 | fixture(**判準改寫後重驗**)| 幾何重佈:s28 零陷深邊緣駐點,serving −107.6 / 缺的 n91 **實測 +19.8dB**、既有鄰區更弱;n91 標 barred(量得到不得駐留)→ 07:43:10 重驗收綠。**卷面 0.6/min 的絕對稀疏做不到**(每 tick 每 UE 都記錄),改用相對稀疏 —— 已記交付落差 |
| 4 | 未知鄰區 | fixture | cgi_resolve(301) 唯一解;bySourceCell 歸屬 |
| 5 | PCI 混淆 | **全循環** | 混淆偵測 → 消歧(owned 唯一)→ Format 3 群組換手 02:09:35 EXECUTED 5/5 → twc=0 |
| 6 | Xn TNL | **全循環** | 08-25 全自動輪:FLAG_SET 16:07:25 → CLEAR 16:42:59 → RECOVERED 17:07:10。08-26 劇本自動化輪:16:17:09 止血 → 16:55:02 RECOVERED,但 xn=true 為人工補。**08-27 B2 從嚴輪(第三次嘗試)**:病期固定 4 分鐘產生 15 次 TXnRELOCprepExpiry 失敗 → 05:48:28 止血(64 秒,對方持續性閘修復後的正常值)→ **05:52:26 刻意重啟 CU,時間軸存活、已過時間累加不歸零** → 05:56:29 修好 → 05:56:39 解封 → 低速恢復 20 分(0.9 次/分)。全程無人介入 |
| 7 | 有害鄰居 | **全循環(劇本自動化連續輪)**| 08-25:成對 SET 17:26:58;L4 探測-重封 300→600→1200s 封頂;19:18:36 RECOVERED。08-26:`anr_fixture` 七步時間軸無人值守連續跑完 14:40:33→14:57:45 |
| 8 | 跨頻缺層 | fixture | 3.5G→2.1G 三條關係剪除;干擾計算僅同頻(inter_freq gate)|
| 9 | NRT 容量 | fixture | `nrtCapacity {limit, used=max, usedByCell}`;ADD_REJECTED 真形狀 |
| 10 | 過期 PCI 重指 | 閉環抽驗 | 03:14:56 REMOVE(stale-pci)+ADD 同秒原子重指 → pci 205→233 → 失敗歸零 |
| 11 | 殭屍關係 | **全循環** | 雙零 REMOVE 02:27:16 REMOVED;保護拒絕(REJECTED_PROTECTED)+不重試;單零不誤刪 |
| 12 | 屬性稽核 | fixture + live 自然發生 | d02(無據封鎖,cum=0)vs n80(正當,cum=40);Q6 關係被稽核判「有失敗史不動」|

## 三、本輪落地的介面/機制(sim 側)

- **v10 觀測 schema**(`ANR_SCHEMA=v10`,CU 每請求讀):扁平鍵、無 rlfKpm 容器、
  旗標不可觀測(Q12 考點)、granularityPeriod=實際計算窗
- **`measSampleRatePerMin` per-(source,target)**:`bySourceCell` 歸屬,
  且歸屬以「量測當時 serving」入列(`MeasurementLog.serving_cell` 新欄)
- **Format 3(UE Group)全鏈**:adapter 解碼(logicalOR 名稱比對、條件解包、
  target CGI 與逐 UE 同源抽取)→ CU 條件解析(駐留+近 2 分量測)→ 逐 UE 換手
  → count-only outcome(L1:UE 識別不出 E2);三態 + target 解不開回 REJECTED
- **事件流完備性**:`flagChangeEvents`/`relationChangeEvents` 均帶 `sourceCellNcgi`;
  changeEvents 過濾只按 source(ghost-target 事件是 Q11 敘事本體,不得吞)
- **`cgiResolutionSampling.nrCellIdentity`(+byNcgi)**:混淆時逐候選 NCI,
  供 Q5 自動鏈直指 target(hash fallback 與換手 resolve 同一對照表)
- **注入熱開關**:`tmp/ho_force_fail.txt`(寫檔即生效)取代 env 注入 ——
  L4 計時不被容器重啟打斷,且杜絕 env 跨場撞名污染

## 四、互抓 bug 帳(對帳 RIC 第三十四輪 §四)

**sim 側被抓/自抓並修畢**:
- `bySourceCell` 單 key 輪替(查詢時 serving 壓扁時間軸)→ 量測時 serving 入列
- changeEvents ghost-target 過濾吞證據(Q11 兩謎同根)→ 只按 source 過濾
- `relationChangeEvents` 缺 sourceCellNcgi → 補齊
- adapter 群組分支雙缺口(條件 pycrate 容器未解包、target CGI 未走抽取)
- CU 中場重啟 ⇒ UE manager 執行緒重建不重 camp ⇒ UE 量測流默死(坑 7)
- `HO_FORCE_FAIL_TARGET` env 殘留污染 Q1 抽驗場(坑 8);
  伴生自首:SUCC=99 誤報(跨場累計,坑 9:計數必界時間窗)
- 群組 outcome 缺席(CU 跑舊碼:窗口重啟清單漏 CU)
- 早期:legacy A3 雙路徑、nrtCapacity 語意、granularityPeriod、HoFailCumulative 型別

**RIC 側被抓/自抓並修畢**(見其總結):拒後重試、幽靈 FLAG_CLEAR、
probe 靜默假恢復、帳本歧義、_cell_nci 映射、Q8 空表早退、Q10 PRB 誤鎖等。

**互驗無罪**:CU matcher(六連 NO_MATCH = mid 駐留窗僅 ~8s/趟的幾何事實)。

## 五、劇本資產狀態(前端 /scenarios 頁)

scenario store(omniver_backend:8001)與 `docs/scenarios/*.json` **全數一致**
(2026-08-26 逐筆 raw_json 比對):十二題 + `anr_neutral_healthy` 共 13 筆即 v10 最終版,
前端頁面無需更新。v10 的佈病(旗標、搬 UE、ghost 關係)由 `scripts/anr_arm.py`
在執行期套用,不入 JSON —— 重跑任一題:起劇本 → 等 90s → `CASE=qN` → 多次取樣驗持續。
殘留兩筆待決:`anr_recamp_test`(除錯)、`anr_veto_variant`(v8 變體)—— 可刪未刪。

## 六、backlog(不擋完結,雙方認領)

**sim 側**:
1. CU 重啟 ⇒ 斷流三層根因(E2 訂閱側 / adapter polling / UE manager 不重 camp)——
   目標「重啟後全鏈路自癒」,backlog 首位
2. physics OOM(12g 上限)+ 重建後空場景自動重推
3. power_dbm 接線、A3 failure backoff、標準 IndicationMessage Format 3 載體、
   E2AP 版本差(v2.0.3 vs v3.0)文件化

**RIC 側**(其 v10.1):快照新鮮度閘、A3 backoff 等。

## 六之二、2026-08-27 B2 從嚴輪:三次才跑對,失敗原因各不相同

RIC 要求以從嚴判準重驗第 6 題(全程無人介入 + **中途故意重啟 CU** + 序列完整 + 心跳不中斷),
起因是 08-26 那輪的時間軸隨 CU 重啟死亡、最後由人補完。跑了三次:

| 輪 | 結果 | 失敗原因 |
|---|---|---|
| 一 | 行為確認零樣本 | 走廊單向(去程 8.5dB / 回程 1.6dB < A3 門檻),UE 有去無回;且維持條件停在「環境修好」那一刻,而行為確認需要的正是那之後的樣本 |
| 二 | 病徵零失敗 + 恢復由我方促成 | 病期只有 12 秒(長度外包給對方的反應速度),UE 來不及走到觸發區;我宣告「本輪不套用修好的程式」,但續跑機制自動載入了它 |
| 三 | ✅ 三段乾淨 | — |

**三條由此固化的通則**:
1. **佈場方要能獨立決定病徵的存在時間**,不能由觀測方的反應速度決定(自變數不可由被測對象控制)
2. **維持條件要延續到 xApp 判定恢復為止**,不是到環境修好為止
3. **「我沒有主動讓它生效」不等於「它不會生效」** —— 有自動化機制在跑時,任何改動都要先問「有沒有東西會替我套用它」

**互相遮蔽**(本輪最值得記的結構):第二輪的「12 秒偵測」看起來像對方的進步,實際上是
「我方病期太短」與「對方持續性閘無清除點」兩個 bug 疊加的結果 —— 各自的症狀恰好是對方的
正常表現,所以雙邊都沒發現,還互相讚美。**「結果看起來對」在雙邊系統裡的證據力遠低於單邊系統。**

## 七、2026-08-26 收尾輪:六個 bug 的共同根

當天雙方各三個 bug,**沒有一個是機制設計錯**,全部發生在「判斷的依據」上:

| 錯法 | sim 側 | RIC 側 |
|---|---|---|
| 依據被污染 | 幾何用估算不用實測(第 7 題壞三次)| PRB 硬閘 ×3;基準被病灶自己填滿 |
| 依據不受控 | `wait_event` 數歷來事件;孤兒行程清掉注入 | `_sparse_watch` 靠外部事件才清 |
| 依據沒驗活性 | **日誌有行 ≠ 程序活著**;argparse 靜默退出 | 宣告要掃卻沒掃 |
| 語意沒理解 | — | 次數窗 vs 時間窗;baseline 窗長 |

歸結成一句可跨專案用的原則:
**「我依據的東西,是不是我理解且控制得住的?」**

### 由此落地的兩件事

1. **時間軸心跳**(`anr_fixture --status`,commit `69e966c`):活性判準是
   「心跳新鮮 < 30s **且** 行程存在」。分得出活著/卡住/剛死三態,而看日誌三態相同。
   心跳寫在每步驟、兩個等待迴圈每輪、**以及分段的 sleep** —— 300 秒 sleep 不切段的話,
   中間五分鐘沒有活性訊號,同一個誤判會原地重演。
2. **基準相對判準的適用邊界**(RIC 側寫入 `_mro_not_flat` docstring 禁令):
   `baseline` 只在「病灶持續時間 < 基準窗」時可靠。第 6 題病灶 40 分鐘後
   `RRU.PrbTotDl.s07_c0` 的 baseline 從 12 漲到 100、trend 六格全 100。
   **只可用於排除閘,不可用於觸發條件**(排除閘失效只是多做事;觸發條件失效是漏偵測)。
   限制寫在會被讀到的地方(函式 docstring)而非只寫在設計文件。

### 流程改進(當天見效)

**凡在信裡宣告的待辦,下一封信要回報做了沒。** 待辦分兩層,只對點名層點名:
點名層 =「沒做正在造成當下阻塞」(如 PathSolver 強制實測);記錄層 = 想做但不擋事。

### 「結果對 ≠ 理由對」

當天出現四次僥倖:孤兒行程碰巧清對注入、基準污染碰巧讓路正確、
人工補 xn 讓鏈條走完、`succ_last50` 次數窗碰巧因流量高而沒踩到逾時。
四次都記錄在案 —— 換一個流量低的場景,最後一項會準時踩到。

## 八、經驗結晶

坑目錄擴至 9 條(記憶 `anr-scenario-arming-pitfalls`):先跑再佈病要搬 UE、
重建不看旗標修幾何、訊號差一律 PathSolver 實測、窄窗病調 offset、
重啟暫態等 recamp、持續性多取樣、CU 中場重啟殺量測流、env 注入跨場撞名、
計數必界時間窗。雙向通則:「快照是結果不是歷史;事件流斷供時,
發送日誌是第二信源;查日誌再定罪,且計數要界窗。」
