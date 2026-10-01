# (SMO) 緊急回覆:run N 的 rApp 已在 15:33:06Z PUT(PMS 201);**這次 RIC-A 是 NOT_ENFORCED**(OTHER_REASON),xApp 0.2.6 沒有確認也沒有 es-on

- 日期:2026-10-01 15:41Z
- 回覆:`04_問題/已回覆/(DT)_run_N_1540Z尚無es-on_請SMO回rApp是否已PUT與PMS狀態_2026-10-01.md`
- **請 DT 立即轉達 RIC**

## 1. SMO / A1

| 時刻(UTC) | 事件 |
|---|---|
| **15:33:06** | rApp PUT `smo-n3-corridor`(e32/0 節能,FORBID e30/0、e31/0,`dlPrbUsage` 60):15:31–15:33 連 3 期平均 < 30%(SMO 的 PM 比 DT 估的早一期湊滿)→ **PMS 201** |
| 15:33:10 | RIC-A 清單有 `smo-n3-corridor`;PMS 顯示 `NOT_ENFORCED` |
| **15:41** | PMS:`{"enforceReason":"OTHER_REASON","enforceStatus":"NOT_ENFORCED"}`;**RIC-A `…/smo-n3-corridor/status` 也是 `NOT_ENFORCED`、`OTHER_REASON`**;O1 e32 仍 ENABLED |

## 2. 跟第一場(run M)不同的地方

| | run M(xApp 0.2.5) | run N(xApp 0.2.6) |
|---|---|---|
| RIC-A 狀態 | 13 秒內 **ENFORCED**(xApp 回 20011 OK) | 8 分鐘後仍 **NOT_ENFORCED**(OTHER_REASON) |
| es-on | 沒有 | 沒有 |

- 所以這次 xApp **沒有回 OK**(或回了 NOT_OK / 沒回)。可能的原因:
  - (a) 0.2.6 在等 PRB 時改回 NOT_ENFORCED,也就是 InfluxDB 的後備也沒拿到 PRB;
  - (b) 0.2.6 / dt-preproc 0.1.8 換版後,RIC 的路由(20010 → dt-a1-xapp)又沒推到。今天 rtmgr 對「換版後重推」已經修過 mit5,但仍請確認。
- 請 RIC 查 dt-a1-xapp 15:33:06 以後的日誌,以及 rtmgr 對 20010 / 20011 的路由。
- **關於 PRB 後備**:SMO 這邊的 InfluxDB 名稱是 `SubNetwork=corridor24_16_24,ManagedElement=gnb_…_du<N>,GNBDUFunction=<N>,NRCellDU=0`(04:37 起的新命名)。如果 0.2.6 讀的是 RIC 自己的 InfluxDB(KPM 直寫)就與 SMO 無關;如果它查的 measurement 名稱是舊格式,就會查不到。

## 3. 處理建議

- rApp 判斷正確,**維持 LIVE、照時程跑完**:15:45 起 B 階段,rApp 應該會因高負載 DELETE;C 階段會再 PUT 一次。如果 RIC 在 run 中修好,C 階段可以驗 es-on。
- 結束後 SMO 切回 dry-run。

## 附:rApp 這場每期的判斷(到 15:41)

| 時刻 | 內容 |
|---|---|
| 15:29:32 | ROP 15:30 no PM mes=ok disabled=- candidate=None |
| 15:30:51 | ROP 15:30 no PM mes=ok disabled=- candidate=None |
| 15:31:06 | ROP 15:31 00e30/0=25%/4ue/re4 00e31/0=18%/5ue/re2 00e32/0=0%/0ue/re1 mes=ok disabled=- candidate=None |
| 15:32:06 | ROP 15:32 00e30/0=12%/3ue/re4 00e31/0=5%/5ue/re2 00e32/0=2%/0ue/re0 mes=ok disabled=- candidate=None |
| 15:33:06 | ROP 15:33 00e30/0=11%/4ue/re2 00e31/0=17%/5ue/re3 00e32/0=1%/0ue/re0 mes=ok disabled=- candidate=None |
| 15:33:06 | CREATE smo-n3-corridor: energy-save e32/0, FORBID ['e30/0', 'e31/0'] |
| 15:33:06 |   PMS HTTP 201  |
| 15:34:06 | ROP 15:34 00e30/0=8%/4ue/re1 00e31/0=6%/5ue/re2 00e32/0=1%/0ue/re0 mes=ok disabled=- candidate=e32/0 |
| 15:35:06 | ROP 15:35 00e30/0=7%/5ue/re5 00e31/0=5%/4ue/re2 00e32/0=3%/0ue/re3 mes=ok disabled=- candidate=e32/0 |
| 15:36:07 | ROP 15:36 00e30/0=7%/4ue/re3 00e31/0=9%/4ue/re4 00e32/0=6%/0ue/re2 mes=ok disabled=- candidate=e32/0 |
| 15:37:06 | ROP 15:37 00e30/0=6%/4ue/re4 00e31/0=4%/5ue/re1 00e32/0=5%/0ue/re3 mes=ok disabled=- candidate=e32/0 |
| 15:38:06 | ROP 15:38 00e30/0=9%/4ue/re2 00e31/0=6%/5ue/re1 00e32/0=1%/0ue/re1 mes=ok disabled=- candidate=e32/0 |
| 15:39:06 | ROP 15:39 00e30/0=6%/4ue/re1 00e31/0=8%/5ue/re1 00e32/0=2%/0ue/re1 mes=ok disabled=- candidate=e32/0 |
| 15:40:06 | ROP 15:40 00e30/0=6%/4ue/re1 00e31/0=6%/4ue/re0 00e32/0=0%/0ue/re0 mes=ok disabled=- candidate=e32/0 |
| 15:41:06 | ROP 15:41 00e30/0=9%/3ue/re1 00e31/0=9%/5ue/re4 00e32/0=5%/0ue/re0 mes=ok disabled=- candidate=e32/0 |

## 4. RIC 的解釋(15:46Z):跟 SMO 看到的一致

- 15:33:06 a1mediator 送出的 20010,寫進了通往換版前舊 pod 的死連線而遺失 → xApp 沒收到 → 沒有 20011 → PMS / RIC-A **NOT_ENFORCED**(SMO 15:41 已核對,一致)。
- SMO 照 RIC 要求**維持 LIVE、不重起 run**;第二輪 PUT 預期約 16:03,SMO 會以 O1 e32 變成 DISABLED、PMS ENFORCED 為準回報。
- 建議 RIC 補上 20012 對帳(每 60 秒),以後換版後的第一筆就算遺失,也能在一分鐘內自動補回;這對 SMO 的 rApp 也是保護。
