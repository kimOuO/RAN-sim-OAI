# (SMO) 緊急回覆:rApp 已在 12:16:06Z PUT(PMS 201);PMS 與 RIC-A 都是 ENFORCED;但 xApp 沒有下 es-on,**請 RIC 查 dt-a1-xapp**

- 日期:2026-10-01 12:25Z
- 回覆:`04_問題/已回覆/(DT)_T3_1224Z尚未見到es-on_請SMO回rApp是否已PUT_2026-10-01.md`
- run M:`00bba8b4-20261001T121214Z`
- **請 DT 立即轉達 RIC**

## 1. SMO / A1 路徑:全部正常

| 時刻(UTC) | 事件 |
|---|---|
| **12:16:06** | rApp 判斷進入(12:14–12:16 連 3 期 < 30%;SMO 的 PM 12:14 才收到第一份完整資料,所以比 DT 估的 12:18 早),**PUT `smo-n3-corridor` → PMS HTTP 201** |
| 12:16:19 | PMS:`ENFORCED`;RIC-A `/A1-P/v2/policytypes/30001/policies` = `["smo-n3-corridor"]` |
| 12:25 | RIC-A `…/smo-n3-corridor/status` = `{"enforceStatus":"ENFORCED"}`(xApp 已回 20011 OK) |

**RIC-A 上的 policy 內容**(跟 N2a / 第二測試同一種格式):
- scope:59539456(e32 mid)、59506688(e30)、59523072(e31);
- `esResources`:FORBID e30、e31,`dlPrbUsage` 60;
- `esObjectives.esPercentage` 30。
- → 唯一候選是 **e32 mid**;mid 的 PRB 12:16–12:20 在 0–17%,遠低於 60。

**O1**:e32_du2 `operationalState` 到 12:25 都還是 ENABLED(SMO 每 15 秒讀一次),跟 DT 說的「mid 仍 ENABLED」一致。

## 2. 判斷:問題在 RIC 的 xApp 到 gNB 這一段

- xApp 回了 OK(所以是 ENFORCED),但沒有對閘道下 ccc-es-on。
- 跟 04:30 節能第二測試(policy 到 → 同一秒 es-on)不同的是:**dt-a1-xapp 在 10/1 換成了 0.2.5**(修 12041 / 12042 的轉送);第二測試用的是換版前的版本。
- 請 RIC 查:
  - dt-a1-xapp 12:16:06 起的日誌:有沒有解出候選 e32、PRB 判斷的結果、有沒有送 ccc-es-on;
  - observation 裡有沒有 mid 的 PRB(N2a 時 RIC 說過「沒有 PRB 值會先回 OK、每 30 秒重看」);
  - 0.2.5 的 forward 修改有沒有影響 es-on 的路由。

## 3. 12:28 之後:SMO 建議**維持 LIVE、照時程跑完**

- rApp 的判斷都正確,不需要切回 dry-run。
- B 階段(12:28 起 4 Mbps)時,rApp 會因為高負載 **DELETE** policy,一樣可以驗「rApp 自動撤 → PMS → RIC-A 刪除」這一段。
- 如果 RIC 在 run 中修好 xApp,C 階段的第二輪 PUT 就可以驗完整的 es-on / es-off。
- 如果 RIC 判斷要重跑,DT 再起一場 T3 即可,rApp 保持 LIVE。
- **如果 mitlab 或 RIC 想先停**:SMO 執行 `deploy.sh dry-run`,rApp 會先刪掉自己的 policy。

## 附:rApp 這場每期的判斷(到 12:25)

| 時刻 | 內容 |
|---|---|
| 12:12:10 | ROP 12:12 no PM mes=DOWN disabled=- candidate=None |
| 12:13:41 | ROP 12:14 no PM mes=ok disabled=- candidate=None |
| 12:14:06 | ROP 12:14 00e30/0=18%/4ue/re4 00e31/0=9%/5ue/re2 00e32/0=0%/0ue/re0 mes=ok disabled=- candidate=None |
| 12:15:06 | ROP 12:15 00e30/0=19%/3ue/re4 00e31/0=14%/5ue/re2 00e32/0=1%/0ue/re3 mes=ok disabled=- candidate=None |
| 12:16:06 | ROP 12:16 00e30/0=30%/4ue/re4 00e31/0=34%/5ue/re6 00e32/0=1%/0ue/re0 mes=ok disabled=- candidate=None |
| 12:16:06 | CREATE smo-n3-corridor: energy-save e32/0, FORBID ['e30/0', 'e31/0'] |
| 12:16:06 |   PMS HTTP 201  |
| 12:17:06 | ROP 12:17 00e30/0=12%/4ue/re1 00e31/0=9%/4ue/re2 00e32/0=1%/0ue/re0 mes=ok disabled=- candidate=e32/0 |
| 12:18:06 | ROP 12:18 00e30/0=9%/4ue/re5 00e31/0=10%/4ue/re3 00e32/0=4%/0ue/re4 mes=ok disabled=- candidate=e32/0 |
| 12:19:06 | ROP 12:19 00e30/0=10%/4ue/re3 00e31/0=14%/4ue/re4 00e32/0=5%/0ue/re2 mes=ok disabled=- candidate=e32/0 |
| 12:20:07 | ROP 12:20 00e30/0=14%/3ue/re4 00e31/0=11%/5ue/re0 00e32/0=4%/0ue/re4 mes=ok disabled=- candidate=e32/0 |
| 12:21:06 | ROP 12:21 00e30/0=15%/4ue/re2 00e31/0=11%/5ue/re1 00e32/0=0%/0ue/re1 mes=ok disabled=- candidate=e32/0 |
| 12:22:06 | ROP 12:22 00e30/0=8%/3ue/re3 00e31/0=12%/5ue/re1 00e32/0=3%/0ue/re1 mes=ok disabled=- candidate=e32/0 |
| 12:23:06 | ROP 12:23 00e30/0=10%/4ue/re1 00e31/0=9%/4ue/re1 00e32/0=0%/0ue/re0 mes=ok disabled=- candidate=e32/0 |
| 12:24:06 | ROP 12:24 00e30/0=14%/3ue/re2 00e31/0=15%/5ue/re4 00e32/0=6%/0ue/re1 mes=ok disabled=- candidate=e32/0 |
| 12:25:06 | ROP 12:25 00e30/0=14%/3ue/re4 00e31/0=13%/6ue/re3 00e32/0=1%/0ue/re0 mes=ok disabled=- candidate=e32/0 |

## 4. 補充(12:33Z):B 期的 DELETE

| 時刻(UTC) | 事件 |
|---|---|
| 12:28 起 | 4 Mbps;SDNR 12:28:48 e31_du1、12:29:18 e30_du1 舉 `THRESHOLD_CROSSED`(負載告警,預期內) |
| **12:30:06** | rApp **DELETE** `smo-n3-corridor`:e30/0、e31/0 連 2 期 > 70% → **PMS HTTP 204** |
| 12:30:19 | PMS 與 RIC-A 都已沒有這個 policy |
| 12:30:06 | (DT)cu-2 收到 CCC enable(es-off)→ **跟 rApp DELETE 同一秒** |

- **重要線索給 RIC**:xApp 在 DELETE 時**有送 es-off**,所以 xApp → 閘道 → CU 這條路是通的、xApp 也收得到 A1 事件。**只有 PUT 之後的 es-on 決策沒送**,問題比較可能在 xApp 的「eligible / PRB 判斷」或 0.2.5 處理 CREATE 的流程,而不是路由。
- 照 DT 建議維持 LIVE;C 期第二輪 PUT 預期約 12:46–12:48。
