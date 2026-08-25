# 回覆 sim:Q1 fixture 已取 + 共存風險已實測 + 模組清單(第五輪)

> RIC 側 · 2026-08-25(第五輪)
> **編號約定**:`ASK-n` = 我方澄清提問;`第 n 題` = 十二題情境測驗。
>
> 你們問的整合風險我**實測過了**,結論在 §2 —— 可以共存,附可重跑的腳本。
> 第 1 題 fixture 已拉完,**劇本可以切了**。

---

## 1. 第 1 題 fixture 已取,可以切劇本了

連拉三次(07:15:57 / 07:16:00 / 07:16:03),三份一致,已存為
`fixtures/v10/q1_missing_neighbor.json`。**佈病狀態符合預期**:

```
neighbourCellRelations               0 條      ← 缺漏鄰區已佈成
reestablishmentInboundByPreviousPci  2 筆      ← 第一題的觸發源
  nbr_c0 ← prevPci=20, previousArfcn=633333, 1.0/min
  src_c0 ← prevPci=30, previousArfcn=633333, 1.0/min
flagChangeEvents                     2 筆      ← 新容器,見 §4
servingCells                         nbr_c0(PCI 30) / src_c0(PCI 20)
```

normalizer 已對這份 fixture 跑過回歸,**第一題的判斷鏈讀得到**:
`prevPci=20 → nbr_c0 @ 1.0/min ≥ 門檻 0.2/min` 且 NRT 查無 —— 觸發條件成立。

**`previousArfcn` 確認到貨**(ASK/C2-1 結案)。另外注意這個容器是**巢狀**的
(`cellNcgi` + `byPreviousPci[]`),和 docx 第 12 題範例裡那個扁平形狀不同 ——
我們照實際輸出寫,提一下以免文件之後被改成扁平。

**請切 `anr_attr_audit` + `CASE=q12`。** 切好跟我們說,我們自己拉。

---

## 2. 你們最擔心的整合風險:**實測過了,可以共存**

你們問「兩份 E2SM-COMMON-IEs 在同一個 pycrate GLOBAL 會不會打架、
症狀出現在跟 RC 無關的 KPM 上」—— 這個顧慮是對的,所以我不用推論回答,直接跑。

### 2.1 實驗設計(等同你們的載入方式)

```
1. compile_text(e2ap_v2.asn1 + e2sm_v3.00.asn + e2sm_kpm_v2.0.03.asn)   ← 執行期編譯
2. generate_modules(...) → import                                        ← 產生 runtime 模組
3. KPM 往返編解碼,記下位元組                                            ← 基準
4. import 預編譯的 E2SM_RC(自帶 E2SM-COMMON-IEs)
5. KPM 再往返一次 → 與基準比對
6. RC Format 3 編一次
7. KPM 第三次往返 → 再比對
```

### 2.2 結果

```
  [匯入 RC 之前] KPM 往返 OK, 5 bytes
  已匯入 RC。其 E2SM-COMMON-IEs OID: [1, 3, 6, 1, 4, 1, 53148, 1, 1, 2, 0]
  [匯入 RC 之後] KPM 往返 OK, 5 bytes
  RC Format 3 編碼 OK: 24 bytes
  [RC 編碼之後] KPM 往返 OK, 5 bytes

結果:KPM 三次位元組一致 = True
```

**兩份 COMMON 的 OID 完全相同**(`…53148.1.1.2.0`),GLOBAL 裡後者覆蓋前者,
但**編譯完成的物件持有的是直接參照而不是名稱查找**,所以 KPM 不受影響。

### 2.3 一個誠實的但書

這個實驗用的是**我們的檔案**:COMMON 來自 `e2sm_v3.00.asn`,你們的是內嵌在
kpm 檔裡的那一份。**若兩份 COMMON 的定義本身有結構差異,結論不保證可以套用。**

所以我把實驗打包成可重跑的腳本,**請你們用自己的檔案跑一次再換模組**:

```
E2_data_v10/coexistence_test.py        # 改上方三個路徑常數即可
判讀:三次 KPM 往返位元組必須完全相同,且 RC Format 3 可編碼
```

這一步你們列在「拿到檔案後要做的事」第 2 項,我先幫你們把腳手架搭好。

---

## 3. 你們問的兩件事

### 3.1 rc-probe 總共載入哪些模組

**只有兩個,而且我們從來沒載入過 KPM** —— rc-probe 是純控制端:

```python
from pycrate_asn1dir.E2AP import E2AP_PDU_Descriptions   # pycrate 套件內建的 E2AP
from .asn1.E2SM_RC import E2SM_RC_IEs                    # 我們給你們的那份
```

`asn1/` 目錄下只有 `E2SM_RC.py` 一個檔,它的結尾是:

```python
init_modules(E2SM_COMMON_IEs, E2SM_RC_IEs, _IMPL_)
```

也就是 **COMMON + RC 兩個模組**。E2AP 用的是 **pycrate 套件自帶的**,不是我們的 .asn。

**所以「一次編出全部」的那份我們沒有** —— 我們的 E2AP 來自套件、RC 來自這個預編譯檔、
KPM 根本沒載。這也解釋了為什麼我們從來沒遇到你們擔心的那個問題:
**這個組合在我們這邊從未出現過。**

mobiflow(收 KPM 的那支)是另一個 process、另一套載入,兩者不在同一個 GLOBAL 裡。

### 3.2 我們的 E2AP 版本 —— 這裡有個你們會想知道的落差

**rc-probe 用的是 pycrate 0.7.11 內建的 E2AP,而那份是 v3.0**,不是 v2.0.3:

```
E2AP-PDU-Descriptions OID: [1,3,6,1,4,1,53148,1,2,1,0]
含有 RICaction_AddedForModification_Item / RICaction_RemovedForModification_Item
    / RICaction_ConfirmedForModification_Item …
    ← 這些是 E2AP v3.0 才引入的 subscription modification IE
```

而 **e2term 是 OSC `ric-plt-e2:6.0.8`**(E2AP v2.0 世代)。

也就是說**我們這邊本來就跑著 v3.0 編碼器對 v2.0 e2term**,而且**一直正常運作** ——
因為 `RICcontrolRequest` / `RICcontrolAcknowledge` 的 IE 組成在 v2→v3 之間沒有變動,
我們用到的訊息剛好都落在共通子集裡。

**對你們的意思**:你們外層 v2.0.3 沒問題,不需要為了 RC 換 E2AP。
但如果之後有人要用 subscription modification 之類 v3.0 才有的程序,兩邊都得先對齊。
**這件事我建議也記下來當獨立議題,不要混進 v10 切換。**

---

## 4. `flagChangeEvents` 獨立容器 —— 已對接,normalizer 通過

拆成獨立容器是對的,理由你寫得比我清楚:
「後者會讓同一個 ring 有兩種保留規則,之後誰維護都要重新理解一次」——
同意,規則單純比省事重要。

**已對接完成**。有兩個實作細節提一下:

1. 容器位置在 **`e2NodeInformation.flagChangeEvents`**(不是頂層),我們照實際輸出接的。
2. 旗標名在 **`flag`** 欄位,不是 `detail`。我們兩個都收(新的優先),
   這樣你們若有舊版殘留也不會漏。

用 Q1 fixture 裡那 2 筆真實事件驗過:

```
FLAG_SET   nbr_c0 xnBlocklist  06:50:47.469
FLAG_CLEAR nbr_c0 xnBlocklist  06:50:47.498   ← 較新
→ 重建帳本:nbr_c0.xnBlocklist = False        ✅ 正確
```

---

## 5. normalizer 進度

**已完成,47 項回歸測試全過**,fixture 用你們的真實輸出(不手寫假資料)。

它吸收了三項機械變更(扁平鍵、值物件、容器合併),另外做了兩件事:

- **從事件流還原 `relationAgeSec`** —— 這是我們自己挖出來的坑:
  第 1/2/3/4 題共用的 ADD 路徑用 `relationAgeSec < 20s` 防 xn-reverse 競態,
  欄位移除後那個 veto 會永遠不成立、競態直接回來。
  現在改由 `relationChangeEvents` 的 ADD 時戳推導(標為年齡下界),
  20 秒的窗一定還在 ring 裡,夠用;而 1800 秒的 aging 用途推不出來就是 `None`,
  正好逼第 11 題改用你們的雙歸零判準。
- **移除的旗標用「讀了就拋例外」的哨兵** —— 若回 `None` 或 `{}`,
  舊寫法 `(r.get("flags") or {}).get("hoBlocklist", False)` 會**安靜地讀成 False**,
  等於捏造「這條關係沒被封鎖」。捏造的 False 比缺值危險,因為它看不見。

---

## 6. 檔案還是沒送出去 —— 需要你們開一條路

你們給的目的地我收到了:

```
scp <path>/E2SM_RC_for_sim.py mitlab@10.3.0.217:/home/mitlab/XAPP_DT/
```

但**我們這台沒有到 10.3.0.217 的私鑰**(`~/.ssh` 只有 `authorized_keys`,沒有 id_*),
所以這條指令在我們這邊會停在 `Permission denied (publickey,password)`。

三個選項擇一:
1. **你們的 public key 給我們** → 加進 10.3.0.71 的 `authorized_keys`,你們主動來拉
2. **我們開一個臨時 HTTP** → 給你們 URL,`curl` 完就關
3. **8101 那支 API 加一個上傳路徑**(或給我們一個可寫位置)

校驗值不變:`311870 bytes / MD5 92c759d04c0d48411c3c91ee32fbe12c`

---

## 7. 球位

| 事項 | 誰 | 狀態 |
|---|---|---|
| 開檔案傳送的路(三選一) | **你們** | ⛔ 唯一卡住第 5 題 |
| 切 `anr_attr_audit` + `CASE=q12` | **你們** | 第 1 題已取完,可以切 |
| 共存風險 | 雙方 | ✅ 我方已實測可共存,腳本已給,請用你們的檔案再跑一次 |
| E2AP 版本落差 | 雙方 | ✅ 已釐清:我方 v3.0 編碼器 / v2.0 e2term,共通子集運作正常;建議當獨立議題 |
| `flagChangeEvents` | 雙方 | ✅ 已對接並用真實事件驗過 |
| normalizer | 我們 | ✅ 完成,47 測試通過 |
