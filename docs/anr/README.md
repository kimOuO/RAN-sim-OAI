# ANR 文件索引(2026-08-26 重整)

- `v10/` — v10 campaign:總結報告(campaign_conclusion.md)、v10 規格 docx、觀測資料參數 pdf、
  RIC 往返回覆(v10_RIC八問回覆 / 第二輪 / 遷移須知)、to_sim/(RIC 交付的 RC 預編譯模組包)
- `validation/` — 十二題劇本規格與逐題驗證紀錄(case*)
- `v8/` — v8 時代規格與缺口分析(僅供追溯,已被 v10 取代)

劇本 JSON 在 `docs/scenarios/`(與 scenario store 同步);佈病腳本 `scripts/anr_arm.py`。
舊路徑 docs/ANRv10、docs/anr_validation 已併入本目錄(scenario _doc 內舊引用以此為準)。
- [已知限制與交付落差](v10/已知限制與交付落差.md) —— 卷面做不到的、RIC 面不驗的、壓縮邊界、基礎設施風險
