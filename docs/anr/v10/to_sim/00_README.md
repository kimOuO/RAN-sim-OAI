# 給 sim team 的交付包(2026-08-25)

四個檔案,依序做即可。全部校驗值在 `SHA256SUMS`,拿到後先 `sha256sum -c SHA256SUMS`。

| 檔案 | 是什麼 | 什麼時候用 |
|---|---|---|
| `E2SM_RC_for_sim.py` | rc-probe 實際載入的 E2SM-RC 模組(pycrate 預編譯,**不是 .asn**)。含 `E2SM-COMMON-IEs` + `E2SM-RC-IEs`,結尾呼叫 `init_modules(...)` | 換模組用 |
| `format3_test_vector.txt` | ControlHeader Format 3 的往返驗證向量(31 bytes)+ 期望還原值 + 可貼上的驗證腳本 | **步驟 1**:確認模組能解 |
| `coexistence_test.py` | 驗「執行期編譯的 KPM」與「預編譯的 RC」能否共存於同一個 pycrate GLOBAL | **步驟 2**:換上去之前先確認 KPM 不受影響 |
| `MESSAGE.md` | 這一輪的完整回覆(Q1 fixture 已取、共存實測結果、模組清單、E2AP 版本落差、flagChangeEvents 已對接) | 一起讀 |

## 建議順序

```
1. sha256sum -c SHA256SUMS
2. 照 format3_test_vector.txt 跑往返 → 確認 groupId=17 + 兩個條件項還原正確
   ⚠️ logicalOR 以名稱比對('false'),不要比 0/1
3. 改 coexistence_test.py 上方三個路徑常數,用「你們自己的 .asn 檔案」跑一次
   → 三次 KPM 往返位元組必須完全相同
   (我們用自己的檔案跑過是 True,但兩邊的 COMMON 來源不同,請自行複驗)
4. 上述兩步都過,再換模組、補齊所有 ControlAction 的宣告
```

## 兩件要先知道的事

- **這份模組沒有 QUERY 服務** —— `RC_E2NODEINFO_QUERY` 兩邊都做不出來。
  十二題不阻塞,但它**不等於卷面引用的 R005-v10.00**,是某個中間版本。
- **我們給不出 `.asn` 原始檔** —— rc-probe 的 repo 裡只有這份編譯產物。
  若你們的流程一定要 `.asn`,請早點說,我可以改成把結構定義逐一列出來對照。
