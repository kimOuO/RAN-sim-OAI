# ANR 驗測 第2題:缺漏鄰區(量測側偵測)

> `ANR情境_v8` 第2題 — missing neighbor,**量測側偵測**:達換手等效門檻之鄰區訊號持續
> 出現而 NRT 查無條目;外顯為連線中斷與換手停滯並存之劣化。
> 日期:2026-08-18。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

## 1. 與第4題的鑑別線(不可沿用同一支 guard)

| | 第4題 未知 cell | **第2題 量測側缺漏** |
|---|---|---|
| cell 身分 | **未知**(REPORTCGI 收斂到新 NCGI) | **已知,只缺關係** |
| 偵測依據 | 強訊號 + RLF | **`servingRsrpP50 − rsrpP50 ≤ MARGIN_HO(6dB)`** —— 不靠 RLF |
| 額外門檻 | — | `rsrpP50 > TH_ABS(-85)`、`PERSIST_WINDOWS=3` |
| 陷阱 | — | **低嘗試量誘餌關係**,卷面明令不得當根因 |

## 2. 劇本 `anr_missing_meas`

| cell | pci | x | NRT |
|---|---|---|---|
| `n37_c0` | 137 | -300 | ✅ 誘餌關係(雙向) |
| `s25_c0` | 133 | 0 | 服務 cell |
| **`n35_c0`** | **135** | +400 | ❌ **無關係(待發現)** |

全 3.5 GHz / arfcn 633333,duration 7200s,UE `mm0-4` 掃 -320..+150。
`n35_c0` 放在 +400 使其在 UE 東端**落後 serving ~5dB(命中 MARGIN_HO)但不強勢**,
UE 不會被吸附過去 —— 這是本題與第4題(強訊號)的關鍵差異。

## 3. sim 新增能力:`anrIntraEnabled` 前置檢查

卷面要求 xApp 檢查「ANR 自動建立功能之部署組態」,停用時只得通報管理面、不得自動寫入。
sim 補上並**使其真的生效**(真實度 A):

- `e2NodeInformation.anrIntraEnabled`(`node_info` 與 func6 `indication` 都帶)
- `apply_son_trigger` ADD 分支:停用時回 `REJECTED_ANR_DISABLED`,**不寫 NRT**
- `REMOVE` / `FLAG` **不受此限**(停用 ≠ 禁止改 NRT)
- env `ANR_INTRA_ENABLED`(預設 true)

## 4. 閉環實測(2026-08-18 08:14:53 UTC · dt-anr-xapp 0.0.19-hogap)

```
guard    DETECT ho-gap: s25_c0 measures pci=135 gap=5.0dB (-71.9 vs -76.9) @302.8/min
         within 6.0dB HO margin, no NRT entry, MRO flat, held 4 windows/30s
         relations ignored as non-causal: ['n37_c0(att=2.1,n=38,succ=0.947,causes={})']
rc-probe rc-reportcgi  ACK 51ms  → cgi=n35_c0
         anr-add       ACK 307ms
sim      08:14:53 ADD s25_c0→n35_c0 by=xapp
         08:14:55 ADD n35_c0→s25_c0 by=gnb-xn (+2s, xn-reverse step4c)
NRT      s25_c0→n35_c0 pci=135 xn=True v=1
HO       到 n35_c0:7 SUCC / 0 FAIL
```

| 卷面基準 | 實測 | |
|---|---|---|
| gap ≤ MARGIN_HO 6dB 且 rsrp > TH_ABS(-85) | 5.0dB / -76.9 | ✅ |
| PERSIST_WINDOWS ≥ 3 | held 4 windows | ✅ |
| NRT 查無條目 | (135, 633333) 無 | ✅ |
| 前置檢查 anrIntraEnabled | true 才寫入 | ✅ |
| 排除 MRO / MLB | 三類平坦 | ✅ |
| 新關係 succ_last50 ≥ 0.95 | 7 SUCC / 0 FAIL | ✅ |
| 單向 ADD,反向交 gNB | by=xapp 單向;反向 by=gnb-xn | ✅ |

## 5. 🔑 排除表設計教訓(RIC 實測逼出來的,通用於所有 case)

RIC 第一版排除表寫成「**樣本足夠 且(succ 偏低 或 有失敗原因)**」就否決偵測。
實測時誘餌 `n37_c0` 樣本長到 35 筆**越過樣本門檻**、succ 0.943 **剛好低於 0.95**,
於是連續六輪輸出 `deferred, an adequately sampled existing relation is failing` ——
**誘餌反而把真正的偵測擋掉了**。

修正:**必須有「具名失敗原因」(`causes` 非空)才能否決**。`causes={}` + `cum={}`
代表那是邊際雜訊,不是可診斷的故障。

> 這是卷面「看到 succ 不完美就去調參數 = 答錯」的變形:
> **樣本數門檻擋得住低嘗試量的誘餌,擋不住「樣本夠但沒有具名原因」的那種。**

另一個同類教訓:guard 迴圈的 `try/except` 會把整輪吃掉,`UnboundLocalError` 的症狀是
「有資料但完全不動」—— 這種錯誤只在真實 indication 流上出現,離線驗證抓不到。

## 6. ⚠️ sim 側新踩到的坑:CU 重啟 → UE 脫鉤

為載入新欄位重啟 CU 後,UE 側對 CU 的連線斷掉(`Connection refused` to cu:8000),
之後**不再推送量測**;UE driver 仍顯示 `running=true`,但 `MeasurementLog` 停止增長,
RIC 端看到的症狀是 **`rowsScanned=0`、所有觀測塊全空**。

**規則:任何 CU 重啟 / 重建之後,必須連帶重啟劇本讓 UE 重新註冊。**
(與第4題那個「duration 跑完 UE 靜止」是不同的失敗模式,但症狀類似。)

## 7. 結論

**「量測聚合比對 serving 落差命中 MARGIN_HO → 持續 3 窗 → 排除 MRO/MLB/誘餌 →
前置檢查 anrIntraEnabled → REPORTCGI → ADD → 換手恢復」整條由真的 RIC xApp 自動跑通。**

第2題達成。API 涵蓋:`REPORTCGI` + `ADD` + `anrIntraEnabled` 前置檢查。
停用分支(`ANR_INTRA_ENABLED=false` → 只 SMO_NOTIFY 不 ADD)測試中。
