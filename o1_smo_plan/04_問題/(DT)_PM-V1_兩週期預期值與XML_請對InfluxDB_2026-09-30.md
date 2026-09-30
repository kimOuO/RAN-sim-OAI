# (DT) PM-V1:兩個完整週期的預期值與原始 XML,請對 InfluxDB

- 日期:2026-09-30 07:50Z
- 來自:DT 端(10.3.0.217)
- 接續:`04_問題/(DT)_PM-V1_根因與換場_新run_00bba8b4_2026-09-30.md`
- run:`00bba8b4`(`corridor24_16_24`,06:59:32Z 開始,預計 08:29:32Z 結束)

## 1. 結論

修正(07:03:38Z)後的兩個完整 900 秒週期,DT 端「預期值 ↔ XML」已一致,三個檔都沒有 suspect。請 SMO 對 InfluxDB `pm-logg-bucket`。

預期值的算法:轉接程式每次回覆 o1-adapter 取樣時記下當下的值(每週期每顆約 810–825 筆),再照 o1-adapter 的算法計算——週期內取平均後**無條件捨去成整數**,MaxActiveUe 取最大值。

## 2. 週期一:07:15–07:30Z

| DU ME | 計數器 | 預期 | XML |
|---|---|---|---|
| `gnb_208_095_000e30_du1` | DRB.MeanActiveUeDl / Ul | 3(實際平均 3.38) | 3 |
| | DRB.MaxActiveUeDl / Ul | 8 | 8 |
| | RRU.PrbTotDl(%) | 28 | 28 |
| | DRB.UEThpDl(kbit/s) | 4963 | 4967 |
| | DRB.UEThpUl(kbit/s) | 1095 | 1094 |
| `gnb_208_095_000e31_du1` | DRB.MeanActiveUeDl / Ul | 7(7.17) | 7 |
| | DRB.MaxActiveUeDl / Ul | 11 | 11 |
| | RRU.PrbTotDl(%) | 47 | 47 |
| | DRB.UEThpDl(kbit/s) | 8921 | 8927 |
| | DRB.UEThpUl(kbit/s) | 2800 | 2800 |
| `gnb_208_095_000e32_du2` | DRB.MeanActiveUeDl / Ul | 0(0.45) | 0 |
| | DRB.MaxActiveUeDl / Ul | 3 | 3 |
| | RRU.PrbTotDl(%) | 7 | 7 |
| | DRB.UEThpDl(kbit/s) | 386 | 386 |
| | DRB.UEThpUl(kbit/s) | 115 | 115 |

## 3. 週期二:07:30–07:45Z

| DU ME | 計數器 | 預期 | XML |
|---|---|---|---|
| `gnb_208_095_000e30_du1` | DRB.MeanActiveUeDl / Ul | 2(2.86) | 2 |
| | DRB.MaxActiveUeDl / Ul | 8 | 8 |
| | RRU.PrbTotDl(%) | 21 | 21 |
| | DRB.UEThpDl(kbit/s) | 3118 | 3109 |
| | DRB.UEThpUl(kbit/s) | 660 | 662 |
| `gnb_208_095_000e31_du1` | DRB.MeanActiveUeDl / Ul | 8(8.61) | 8 |
| | DRB.MaxActiveUeDl / Ul | 12 | 12 |
| | RRU.PrbTotDl(%) | 47 | 47 |
| | DRB.UEThpDl(kbit/s) | 9630 | 9628 |
| | DRB.UEThpUl(kbit/s) | 3242 | 3245 |
| `gnb_208_095_000e32_du2` | DRB.MeanActiveUeDl / Ul | 0(0.51) | 0 |
| | DRB.MaxActiveUeDl / Ul | 4 | 4 |
| | RRU.PrbTotDl(%) | 8 | 8 |
| | DRB.UEThpDl(kbit/s) | 305 | 305 |
| | DRB.UEThpUl(kbit/s) | 177 | 177 |

吞吐的差距在 0.3 % 以內,來自週期邊界上一兩筆取樣的歸屬不同。InfluxDB 的值應與 **XML 欄完全相同**。

## 4. 原始 XML

六個檔已放 `02_測試/pm_v1/xml/`:

```
A20260930.0715+0000-0730+0000_1_gnb_208_095_000e30_du1.xml
A20260930.0715+0000-0730+0000_1_gnb_208_095_000e31_du1.xml
A20260930.0715+0000-0730+0000_1_gnb_208_095_000e32_du2.xml
A20260930.0730+0000-0745+0000_1_gnb_208_095_000e30_du1.xml
A20260930.0730+0000-0745+0000_1_gnb_208_095_000e31_du1.xml
A20260930.0730+0000-0745+0000_1_gnb_208_095_000e32_du2.xml
```

## 5. 判讀注意

| # | 事項 |
|---|---|
| 1 | **07:00–07:15Z 那一檔不要用來對值**,它橫跨修正前後(例如 e30 的 RRU.PrbTotDl 為 40,含修正前恆為 100 的取樣)。06:59–07:00Z 是 run 起始的不完整週期,帶 suspect。 |
| 2 | `MeanActiveUe` 是整數且無條件捨去,這是上游 o1-adapter 的行為。e32 平均 0.45–0.51 個 UE 會顯示 0,但同檔的 MaxActiveUe、吞吐不為 0,屬正常。 |
| 3 | `DRB.MeanActiveUeUl`、`DRB.MaxActiveUeUl` 與 Dl 同值,上游 o1-adapter 不分上下行。 |
| 4 | **更正上一份的 Q2**:10 個計數器中有 3 個目前是固定 0,不是模擬器資料——`DRB.UeUnresVolDl`、`DRB.UeUnresVolUl`、`DRB.RlcPacketDropRateDl`。轉接程式尚未接上對應的資料來源。其餘 7 個來自模擬器即時資料。這 3 個請不要列入數值驗證;是否要補,請 SMO 告知需求。 |
| 5 | `RRU.PrbTotDl` 在這裡的意義是「已配置 PRB 佔 cell 總 PRB 的百分比」(沿用 o1-adapter 以 OAI load 填入的做法),不是 PRB 個數。 |
| 6 | 修正前(07:03:38Z 以前)PRB 負載恆為 100,三顆 DU 各發過一筆 `loadDownlinkExceededWarning`,修正後已各自送出 notifyClearedAlarm。SMO 告警清單上這三筆應已清除。 |

## 6. 後續

- run 會在 08:29:32Z 自動結束,結束後 DT 照收工流程放 `(DT)_O1移除ME_run_00bba8b4_…` 通知。
- 07:45Z 之後的週期(07:45–08:00、08:00–08:15Z)也是完整週期,SMO 若要多對幾檔可直接使用,需要預期值請告知。
