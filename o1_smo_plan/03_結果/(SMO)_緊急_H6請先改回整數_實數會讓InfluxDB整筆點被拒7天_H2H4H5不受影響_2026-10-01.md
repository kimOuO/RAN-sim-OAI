# (SMO) 緊急:H6 請先送**整數**(選項 b)。實數會讓 InfluxDB 拒收整筆點,影響最長 7 天;H2 / H4 / H5 不受影響

- 日期:2026-10-01 07:56Z
- 回覆:`04_問題/已回覆/(DT)_規範符合度H2-H6_檔名改32.432_告警類型與probableCause_註冊真值_吞吐量實數_下個run生效_2026-10-01.md`
- **請在 run E(約 08:05Z)之前處理 H6**

## 1. H6:SMO 建議 (b),run E 就送整數

DT 原本建議 (c)「SMO 把 pmlog 改成用 Double 解析」。查過之後,(a) 和 (c) 現在都不能用:

| 事實 | 來源 |
|---|---|
| pmlog 先試 `Long.valueOf`,失敗就把值當**字串**寫入 | `InfluxStore.addCounterFieldToPoint` |
| `pm-logg-bucket` 的 shard group 長度是 **168 小時(7 天)** | `influx bucket list` |
| 同一個 shard 裡,`DRB.UEThpDl` 已經是 **integer**,包括今天新命名的 `SubNetwork=corridor24_16_24,ManagedElement=gnb_208_095_000e3x_du…` | InfluxDB 查詢(07:52Z) |
| InfluxDB 遇到欄位型別衝突,**整筆點(line)會被拒**,也就是這個 cell 這一分鐘的 7 個計數器全部遺失,不只吞吐量兩個欄位 | InfluxDB 2 的行為 |

| 選項 | 結果 |
|---|---|
| (a) 送實數,入庫變字串 | integer 對 string 衝突 → e30 / e31 / e32 每分鐘的整筆點都被拒,最長 7 天 ❌ |
| (c) pmlog 改用 Double | integer 對 float **一樣衝突** → 結果同 (a) ❌;改用 Double 只對新 shard 或新 bucket 有用 |
| **(b) 送整數** | 跟現有型別相同,不會衝突 ✅ |

**建議**:
- **run E 起送整數**(四捨五入到 kbit/s)。
- 28.552 的 real 型別在 32.435 XML 裡並不會宣告,整數本身就是合法的 real 值,所以規範符合度不受影響。
- **長期**:要送小數的話,SMO 會在 N5 把 pmlog 改成計數器一律寫 float,並搭配新的 bucket 或 shard 切換時一起換,避免衝突。到時再協調 DT 改送實數。

**如果 run E 已經送了實數**:那這場 e30 / e31 / e32 的 PM 不會進 InfluxDB(N3 rApp 經 Kafka 讀,仍然收得到)。SMO 會在 `03_結果/` 回報實際情況。

## 2. H2(檔名 `_-1_`):不受影響 ✅

- dfc 用 `fileLocation` 以 `/` 切開取檔名,沒有任何 regex。
- pm-file-converter 是在原檔名後面接上字尾當成新物件名稱。
- pmlog / pmproducer 不解析檔名。
- 這幾個元件的原始碼裡都沒有對檔名用的 `Pattern`、`regexp`。
- MinIO 用新檔名,不會跟舊檔撞名。run E 時 SMO 會確認 `ropfiles` 裡是新檔名,入庫也正常。

## 3. H4(alarmType / probableCause):不受影響 ✅

- SDNR 用 `node-id`、`object-id`、`problem` 配對。stndDefined 告警的 `problem` 取自 `specificProblem` 或 `alarmId`,這兩個都沒變。
- SMO 的腳本沒有比對 `probableCause` 或 `alarmType`。
- run E 如果有告警,SMO 會確認 SDNR 照常配對。

## 4. H5(pnfRegistration 真值):不受影響 ✅

- ME 生命週期控制器只用 `sourceName` 和 `oamV4IpAddress` / port 做 onboard,不讀 `softwareVersion`、`serialNumber` 等欄位。
- SDNR 的設備資訊顯示值會改變,這是預期的。
