# 回覆 RIC:v10 遷移八個問題

> sim 側 · 2026-08-25
> 三份新樣本一併附上(見文末)。**其中 Q2 與 Q3 是我們的錯,已修並重新導出樣本。**

---

## Q1 第 5 題的 UE 識別 —— 不能給 UE 清單,要走 ueGroup(sim 尚未支援,我們補)

**先講一個你們可能沒注意到的衝突**:我們**不能**在 func6 提供 UE 清單。

v10 全域限制 **L1(UE 匿名化)**:
> UE 識別於每筆量測／事件報告中獨立隨機產生,無法將任何兩筆報告關聯至同一 UE,
> **不可撰寫任何追蹤個別 UE 軌跡之邏輯**。

如果我們在 func6 送「該關係方向目前的 UE 清單」,那份清單本身就是可關聯的識別 ——
**等於幫你們違反 L1**。所以你們問的第 2 個選項,答案是不行,而且理由不在實作而在卷面。

**所以 `ueGroup` 才是本題設計的路**,你們的第 1 個猜測是對的。

**現況**:sim 目前的 Style 3 / Action 1 只吃 `amf-UE-NGAP-ID`
(`e2_control_actor.resolve_ue_id` 由 header 的 NGAP ID 反查 UeContext),
**還不支援 group**。這是 sim 的缺口,我們補。

**要請你們定的**:group 的選擇語意。我們傾向

```
ueGroup = { servingCellNcgi, targetPhysicalCellId, targetArfcn }
        → 「目前駐留於 servingCell、且量測回報中看得到該 (pci,arfcn) 的所有 UE」
```

這個語意不需要任何 UE 識別外流,sim 內部解析、對每個符合的 UE 執行 CGI 換手,
outcome 回「影響 N 個 UE」。**wire 格式請你們定**(E2SM-RC 的 UE Group IE 怎麼帶),
我們配合解碼 —— 因為那要看 rc-probe 送得出什麼。

你們的第 3 個選項(示意性地對取樣 UE 下令)我不建議:那會讓「換手改走 CGI 之後
ToWrongCellRate 回落」這個驗收條件無法成立,等於這題只做半套。

---

## Q2 推送週期 —— 我們標錯了,已修

**這題是我們的錯,而且錯得比你們發現的更深。** 原本有**三個各說各話的時間**:

| | 值 | 來源 |
|---|---|---|
| indication 推送週期 | 約 1 秒 | 你們訂閱時的 eventTrigger(預設 1000ms) |
| `granularityPeriod` 標示 | 60s | 一個獨立的 env,寫死 |
| **速率實際的計算窗** | **10 分鐘** | adapter 拉 indication 時帶的 `window_min` |

也就是說我們標「每分鐘」的速率,其實是拿 10 分鐘的窗算出來的 —— **你們照 60s 解讀會全錯。**

**已修**:
- adapter 改用 **60 秒窗**拉(`window_min=1.0`)
- `granularityPeriod` 改為**由實際窗推導**(`f"{window_min*60}s"`),不再是獨立 env
  → 結構上不可能再漂

**回答你們的三個影響**:
- **推送週期 = 你們訂閱時指定的**,預設 1 秒,與 `granularityPeriod` 無關。
  一秒推一筆、每筆是 60 秒滑動窗的聚合。
- 「連續 6 窗」= **6 × 5 分鐘 = 30 分鐘**。`trendLast30Min` 是我們**每 5 分鐘取樣一次**
  的六筆序列(見 `anr_history.py`),不是 6 筆 indication。
- 第 11 題的 6 小時 = 72 個 trend 窗。實測時我們會縮短,並在劇本 `_metadata` 標明是刻意加速。

---

## Q3 `MM.HoFailCumulativeSinceCreation` 是 **map** —— 我們輸出成 int 是錯的,已修

以 **docx 為準**。我們誤讀了肆章的文字定義:「準備＋執行」是在講**涵蓋範圍**
(兩個階段的失敗都算),不是要我們加總成一個數。docx 第 12 題的 pseudo code
用 `is empty` 判斷,也只有 map 說得通。

已改為依 cause 分列,實測輸出:

```json
"s19_c0 → d02_c0"  "MM.HoFailCumulativeSinceCreation": {}
"s19_c0 → n80_c0"  "MM.HoFailCumulativeSinceCreation": {"RandomAccessProblem": 40}
```

所以第 12 題**可以**看失敗原因的種類來鑑別,不只是有無。

---

## Q4 保護條目過濾 —— 確實只剩一層,我們認為可接受,但補了審計

你們的理解正確:`isRemoveAllowed` 不可觀測之後,**事前過濾在 xApp 側做不到**,
只剩 sim 的事後拒絕。

**我們認為這是 v10 的刻意設計**,理由是它同時把「旗標不可觀測」與「禁止對保護條目送
REMOVE」兩條並列 —— 那只可能推出一種操作型解讀:**送出去、被拒、改走 SMO_NOTIFY**。
第 9 題的「試著剪,被拒就換一條」正是預期行為,不是退化。

**我們補的一層**:REMOVE 被拒現在會落審計事件

```json
{"action":"REMOVE_REJECTED","targetCellGlobalId":"...","by":"xapp",
 "reason":"PROTECTED_ENTRY"}
```

在 `relationChangeEvents` 裡看得到。這樣「送了但被擋」與「根本沒送」在稽核面分得開 ——
先前兩者都不留痕跡,你們的 `_guard_stale_remove` 又不看 result,一筆被拒的 REMOVE
會在兩邊同時隱形(那是你們上次幫我們挖出來的孿生洞)。

---

## Q5 `sourceCellNcgi: null` = 該 PCI 的樣本**全部來自當下沒有 serving cell 的 UE**

`bySourceCell` 記的是「回報這筆量測的 UE 當下的 serving cell」。
UE 掉話中(IDLE / 剛 RLF 尚未重建)時 `serving_cell` 是空字串,那筆就不計入,
全部樣本都是這種情況 → `by_source` 空 → `sourceCellNcgi` 取不到最大值 → `null`。

**不是「來源就是被回報的 cell 自己」**,請不要那樣解讀。

你們看到 null 的那份樣本,很可能就是我們 physics OOM 那段期間導的
(UE 全部掉話,serving_cell 清空)。新導的樣本裡兩筆都有正常來源:

```
reportedPhysicalCellId 20 → sourceCellNcgi "nbr_c0"
reportedPhysicalCellId 30 → sourceCellNcgi "nbr_c0"
```

**建議你們的 guard 把 `sourceCellNcgi == null` 當「證據不完整」處理而不是繼續判斷** ——
沒有來源就決定不了要對哪個 cell 下 ADD。要不要我們改成 fallback 到「UE 最後已知的
serving cell」?那會讓欄位更少空,但代價是那個歸屬是推測的。**傾向不做,除非你們需要。**

---

## Q6 `cgiResolutionSampling[]` 由 sim 自行決定,**而且會抽 NRT 查無的 PCI**

1. **sim 自行決定** —— 不需要你們先用 `RC_MEASCONFIG_REPORTCGI` 指定。
2. **抽樣對象 = 量測聚合裡出現過的每一個 `(pci, arfcn)`**,
   也就是**只要 UE 回報得到就會被抽,不管 NRT 裡有沒有**。

所以第 3、4 題確實可以改成被動讀取,省掉 REPORTCGI 往返。

`RC_MEASCONFIG_REPORTCGI` 仍然保留可用 —— 你們要主動抽某個特定目標、
或要控制 `attempts` 次數時還是走它。

---

## Q7 兩份有內容的樣本已附上

**Q1 重建統計**(`anr_indication_v10_q1_reestab.json`):
```json
"reestablishmentInboundByPreviousPci": [
  {"cellNcgi":"nbr_c0","byPreviousPci":[
     {"previousPhysicalCellId":20,"previousArfcn":633333,"ratePerMin":1.0}]},
  {"cellNcgi":"src_c0","byPreviousPci":[
     {"previousPhysicalCellId":30,"previousArfcn":633333,"ratePerMin":1.0}]}
]
```

**Q12 封鎖稽核對照組**(`anr_indication_v10_q12_blocklist_audit.json`):
兩條關係旗標完全相同,只有行為訊號不同 —— `d02_c0` 的 `cum` 是 `{}`、
`n80_c0` 是 `{"RandomAccessProblem":40}`,`hoValidated` 一 false 一 true。
這份可以直接拿去驗你們的四項行為訊號判斷鏈。

---

## Q8 一律帶 `.NCGI` 後綴

我們的實作**無條件加後綴**,不論幾個 serving cell。docx 第 12 題那個沒後綴的範例
是單 cell 的簡寫。你們的 parser 只要處理一種形狀。

---

## 附:三份樣本

| 檔案 | 用途 |
|---|---|
| `samples/anr_indication_v10_sample.json` | 通用形狀(已用修正後的 Q2/Q3 重導) |
| `samples/anr_indication_v10_q1_reestab.json` | 重建統計有內容(第 1 題觸發源) |
| `samples/anr_indication_v10_q12_blocklist_audit.json` | 第 12 題兩條對照關係 |

---

## 回覆你們的兩則回報

**關於 `xnBlocklist` 的自我陷阱** —— 你們這個觀察很準:
「clear 沒做紮實會製造出一個自己造成、看起來跟真的一樣的第 6 題」。

補一個 sim 側可用的鑑別點:**真的 Xn 不通時 `xnX2Established=false`,
而只是被 `xnBlocklist` 擋住時它仍然是 `true`**。兩者的 `MM.HoPrepInterFailRatePerMin`
都會是 `TXnRELOCprepExpiry`(病徵相同,如你所說),但 `xnX2Established` 分得開。
建議你們的 confirm 拿這個當交叉驗證。

**func2 訂閱中斷** —— 收到。那條斷了不影響 func6,但如果 Q1 最後要走
per-UE 而不是 ueGroup,你們會需要它。這也是我建議走 ueGroup 的另一個理由:
**不依賴另一支 xApp 的資料流**。
