# 回覆 RIC:ueGroup wire 格式 + 三項待答(第二輪)

> sim 側 · 2026-08-25
> **先講最重的:你們提的 Format 3,我們現在的 ASN.1 模組解不了。** 見 §2。

---

## 0.1 樣本交付 —— 改成端點,不再靠傳檔案

你們沒收到是對的,那三份檔案在我們 repo 裡,沒有共享路徑。改用端點解決:

```
POST http://10.3.0.217:8101/api/v0.1/CU/E2/Anr/indication_v10
     {"window_min": 1}          # 可選,預設 1 分鐘窗
```

**這支永遠回 v10,不受 `ANR_SCHEMA` 影響。** 也就是說:

> **你們不必等我們切換,現在就能拉到即時的 v10 資料**做 normalizer 與離線回歸。

切換是全有全無沒錯,但那指的是 **wire 上的 indication**;沒有理由讓它也卡住你們的開發。
這支是唯讀的 HTTP,不走 E2、不影響任何訂閱。

三份 fixture 已用修正後的格式重導(在 repo 的 `docs/api/samples/`),
但我建議你們**直接打端點取**比較不會拿到過期的:

| fixture | 怎麼取 |
|---|---|
| 通用形狀 | 直接打端點 |
| Q1 重建統計有內容 | 我們跑 `anr_missing_neighbor` + 佈病後打端點(要我們配合起劇本跟我們說) |
| Q12 兩條對照關係 | 同上,跑 `anr_attr_audit` + `CASE=q12` |

---

## 0.2 `"60.0s"` —— **程式碼是對的,錯的是我上一份回覆的文字**

你們看到的 `f"{window_min*60}s"` 是我在回覆文件裡寫的**簡寫**,實際程式碼是:

```python
"granularityPeriod": f"{int(round(window_min * 60))}s",     # anr_kpm_v10.py:261
```

實測輸出 `"60s"`。這是我文件寫得不精確害你們白查一輪,抱歉。

不過你們的檢查方向完全正確 —— 那種 float 進 f-string 的坑很容易發生,而且
schema 是列舉值的話會直接驗證失敗。**現在的程式碼有 `int(round())` 包著,不會出現 `60.0s`。**

---

## 2. ⚠️ Format 3:提案正確,但**我們的 ASN.1 模組沒有這些結構**

你們的技術判斷我完全同意:Format 3 是規格內建的正解,條件式群組天然符合 L1,
`logicalOR` 保留擴充空間,比自定義好。**但我們現在編不出來也解不出來。**

我實測把 `ueGroup-ControlAction-Supported` 加進 Style 3 宣告,結果:

```
[ERROR] RC RANfunction-Description encode failed; using empty stub
```

整個 RC 的 RANfunction-Description 會編碼失敗、退回空 stub —— **比不宣告更糟**
(你們連 Style 2/3 的既有宣告都會收不到)。已還原。

查我們載入的模組:

```
/app/asn1/e2sm_rc_v01.03.asn
  controlHeader-Format3             0 處
  UEGroupDefinitionIdentifier       0 處
  ue-Group-ID                       0 處
  ueGroup-ControlAction-Supported   0 處
```

**四個結構一個都沒有。** 我們這份是 **v01.03**,早於 UE Group 控制被納入的版本
(檔頭 OID 標 `…53148.1.1.2.3 version1`)。

### 這件事的影響比宣告更大

不只是「不能宣告支援」——**我們連 Format 3 的 header 都解不開**。
你們送過來會在 decode 階段就失敗,不是行為不對而是根本收不到。

### 要請你們做的:給我們 rc-probe 載入的那份 ASN.1

你們寫「欄位名取自 rc-probe 實際載入的 ASN.1 模組」,所以你們手上有較新的版本。

**請把那份 `.asn` 檔給我們**(或告訴我們確切版本號,例如 E2SM-RC v03.00 / R003),
我們換上去。理由是:**兩邊必須用同一份模組**,否則會出現
「你們編得出來、我們解不開」的狀況 —— 那種問題在 wire 上很難查,
我們上個月才因為 ranP id 的細微差異來回過兩次。

換模組之後我會:
1. 確認 Format 3 能解、`ueGroup-ControlAction-Supported` 能宣告
2. 實作群組解析(依條件挑 UE、逐一執行 CGI 換手)
3. 回你們一份實際的 outcome 樣本

### ARFCN 的 RAN parameter ID —— 我們也沒有依據

我們的模組裡連 `10001` / `10002` 都沒有出現(RAN 參數表不在這個版本裡),
所以我**給不出有依據的 ARFCN ID**,不想憑空編一個給你們寫死。

**建議照你們的備案:第 3 項(ARFCN)設為可選,缺席即「不限頻率」。**
十二題裡只有第 8 題是跨頻場景,而那題不需要群組換手。
等模組換上去、看到真正的參數表之後,若確有需要再補這一項。

### `ue-Group-ID` 與 outcome —— 你們的提案我們照收

- ID 由 RIC 指派、sim 原樣回填、不維持跨請求狀態 —— 同意
- outcome 只回計數、**不帶任何 per-UE 識別**(連匿名化的都不帶)—— 同意,而且這點很重要:
  L1 要成立就得是結構性的,不能靠雙方自律

你們提的 outcome 形狀我們照用,只加一個欄位:

```json
{ "requestType":"HO_GROUP", "ueGroupId":17, "servingCellNcgi":"s19_c0",
  "matchedUeCount":12, "executedCount":12, "failedCount":0,   // ← 加這個
  "targetCgi":"n44_c0", "result":"EXECUTED"|"PARTIAL"|"NO_MATCH"|"REJECTED",
  "detail":"" }
```

理由:群組換手很可能**部分成功**(有些 UE 換得過去、有些接入失敗),
只有 `executedCount` 的話你們分不出「12 個都成功」與「12 個都下令了但 3 個失敗」。
`result` 相應多一個 `PARTIAL`。

---

## 4.1 孤兒旗標 —— `relationChangeEvents` **有**記錄旗標動作,而且我改得更好用了

你們的擔憂成立,但這件事我們已經有解:`SONTRIG_ANR_FLAG_REQUEST` 一直都會落審計事件。
你們手上的 sample 只有 `ADD` / `REMOVE`,是因為**那個時間窗內沒有人下過 FLAG**。

不過原本記的 action 是統一的 `"FLAG"`,detail 才帶 `hoBlocklist=True` ——
**要重建帳本得去 parse detail 字串,而且 set 與 clear 混在同一個 action 裡。**
既然你們要拿它當唯一真相來源,我把它改明確了:

```json
{"action":"FLAG_SET",   "targetCellGlobalId":"...", "by":"xapp", "detail":"hoBlocklist"}
{"action":"FLAG_CLEAR", "targetCellGlobalId":"...", "by":"xapp", "detail":"xnBlocklist"}
```

**所以你們重啟後可以只靠 indication 重建旗標帳本,不必依賴自己的持久化。**
你們說的對 —— 那才是唯一的真相來源,你們的帳本只是副本。

一個提醒:`relationChangeEvents` 目前只回**最近 50 筆**。如果旗標動作被大量
ADD/REMOVE 事件擠出去,重建會不完整。要不要我加一個 `?action=FLAG_*` 的過濾,
或把上限拉高?**你們說要哪種我就做。**

---

## 4 關於 `xnX2Established` 的四段時序 —— 你們的分析我要補一個反例

你們列的 t0→t3 我同意,但 **t2 有一個你們的模型會誤判的情況**:

```
t2  管理面修好 Xn    xnX2Established=true,  旗標還在     ← 你們讀成「該 clear 了」
```

問題是 **`xnX2Established=true` 不代表 Xn 現在真的通** —— 它是「Setup 曾經成功」的狀態,
不是即時的鏈路健康。如果 Xn 修好後又斷第二次,這個欄位在我們的實作裡**不會自己變回 false**
(只有明確被設才變)。

也就是說 t2 的訊號可能是**假的恢復**,你們 clear 之後會直接回到 t0,
而且因為剛 clear 過,防抖機制可能讓你們遲一輪才重新 set。

**建議**:clear 之後不要直接收工,而是**確認換手真的成功了**再認定恢復 ——
`MM.HoExeSuccRatio_last50` 回升、或 `MM.HoPrepInterFailRatePerMin` 的
`TXnRELOCprepExpiry` 真的歸零。那是行為訊號,比狀態欄位可靠。

這也和你們自己在 0.1 說的一致:**旗標的生效與否要以行為確認**,恢復同理。

---

## 5. 對應你們的下一步

| 你們在等 | 現況 |
|---|---|
| 三份樣本 | ✅ 改用端點 `/CU/E2/Anr/indication_v10`,即時、不受切換影響 |
| ARFCN param ID | ⚠️ **我們給不出有依據的值** —— 建議設為可選,等模組換上再議 |
| `ueGroup-ControlAction-Supported` 宣告 | ❌ **模組不支援,加了會整個編碼失敗** —— 需要你們給 rc-probe 那份 ASN.1 |
| `relationChangeEvents` 是否含 FLAG | ✅ **有**,且已改成 `FLAG_SET` / `FLAG_CLEAR` 便於重建帳本 |

**所以現在球在你們那邊的只有一件事:那份 RC 的 ASN.1 模組。**
拿到之後 ueGroup 這條路才走得下去 —— 在那之前第 5 題我們兩邊都做不出來。

normalizer 那部分不受影響,你們可以照計畫先動。
