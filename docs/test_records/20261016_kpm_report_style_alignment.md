# 2026-10-16 KPM 能力宣告與實際回報格式對齊(方案 A)

## 問題
E2 Setup 時 DT 在 KPM RAN Function Description 只宣告 Report Style 1(對應 Action Definition Format 1 /
Indication Message Format 1),但實際送給 RIC 的 indication 一律是 Format 3(per-UE)。依 E2SM-KPM v2.0.03,
Format 3 對應的是 Report Style 4 / 5,宣告與實際不一致。

另外訂閱解碼 `_decode_action_metrics` 只認 Format 1/2/3,而且 Format 2 讀錯欄位
(量測清單在 `subscriptInfo.measInfoList`,原本讀 `measInfoList`,會拿到空清單)。

## 修改
- `e2sm_kpm_codec.encode_kpm_ran_function_description()`:保留 Style 1(既有 xApp 相容,排第一個),
  新增 Style 4「Common Condition-based, UE-level Measurement」(ActionFormat 4、IndicationMessageFormat 3)。
  Style 4 的 UE 比對條件不逐條評估,回報該 cell 全部已附著 UE。
- `e2_subscription_codec._decode_action_metrics()`:支援 Format 1–5;修正 Format 2 欄位;
  每次解碼記一行 log(style、format、量測項數),之後可從 log 看出各 xApp 實際用哪個 Style 訂閱。
- 新測試 `tests/unit_test/test_kpm_report_styles.py`(7 項):宣告含 Style 4 且對應 Format 3、Style 1 仍在第一個、
  實際送出為 Format 3、Format 1/2/4/5 解碼。與 RC 宣告測試一起跑 18/18 通過。

## 尚未部署
程式碼已改,但 RAN Function Description 只在 E2 Setup 時送出;要讓 RIC 看到新宣告必須重啟 e2adapter
(重新 E2 Setup,所有 xApp 重新訂閱)。這會影響場域,需先和 RIC session 約時間,並確認 mobiflow、dt-anr、
dt-fullkpm 重訂閱後仍正常收 indication。

## 規格書
06_規格書 第 4.3 節原文已改(scratchpad `spec/ch48.js`、`build.js`),待 RIC 驗證後重建 v0.4。
