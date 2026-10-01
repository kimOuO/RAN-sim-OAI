# (SMO) mitlab 同意的兩項都完成:rApp 新版 08:58Z 已部署(dry-run);run H 壞點已刪

- 日期:2026-10-01 09:13Z
- 回覆:`04_問題/已回覆/(DT)_mitlab同意_部署N3_rApp新版dry-run_刪除run_H壞點_2026-10-01.md`

## 1. N3 rApp 新版:✅ 已部署(mitlab 08:58Z 執行 `deploy.sh dry-run`,比 DT 轉達的決定還早)

| 項目 | 內容 |
|---|---|
| pod | `n3-es-rapp-845f66f5c4-tg2kk`,08:58:22Z 啟動,`LIVE=false` |
| 版本(sha256 前 12 碼) | `rapp.py` efd5c28b71bb、`rapp_logic.py` **af0655726f5d**(已確認跟叢集 ConfigMap 一致) |
| 包含 | 逐 cell(`<cu>/<cellLocalId>`,範圍從 O1 讀)、O1 狀態退出條件、只考慮在服務中的 cell(spare cell 不列入)、UE 流失(基準至少 4 UE)、沒有 PM 也照時間判斷 |
| 劇本 | `corridor`(e30–e32)、`livetest`(e40–e42) |
| 在線驗證 | run I 09:08:06 選 e42/0、FORBID e40/0 和 e41/0,spare 的 e40/1 不列入;09:12:36 ME 斷線後撤除 |

## 2. run H 壞點:✅ 已刪(09:13Z)

- 刪除對象:`SubNetwork=livetest_corridor,ManagedElement=gnb_208_095_000e42_du2,GNBDUFunction=2,NRCellDU=`,只有 **1 個點**(時間戳 08:42:00.952Z,8 個欄位)。
- 指令:`influx delete --start 08:42:00Z --stop 08:42:01Z --predicate _measurement="<上面的名稱>"`,只比對完全相同的量測名稱,時間窗口 1 秒。
- 刪後:這個名稱 0 個點 ✅;正確的 `…e42_du2,GNBDUFunction=2,NRCellDU=0` 在 08:40–09:13 仍有 24 個點,沒有受影響 ✅。
