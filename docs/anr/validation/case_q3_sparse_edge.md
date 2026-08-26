# ANR 驗測 第3題:深邊緣稀疏樣本型缺漏

> `ANR情境_v8` 第3題 — missing neighbor,**深邊緣稀疏樣本型**:弱覆蓋區僅少數 UE 回報之鄰區缺漏。
> 日期:2026-08-18。狀態:**✅ 端到端閉環成立(sim + RIC 雙邊驗證)**。

## 1. 與第2題的鑑別線

| | 第2題 量測側缺漏 | **第3題 深邊緣稀疏** |
|---|---|---|
| 樣本量 | 充足(~100/min) | **稀疏** —— 卷面明令不得以樣本少駁回 |
| 判定依據 | gap ≤ MARGIN_HO(6dB) | 稀疏但趨勢穩定 + 高於 `TH_ABS` + NRT 查無 |
| 額外鑑別 | — | **`nrtCapacity` 證明容量非阻斷**(對照第9題) |

## 2. 劇本 `anr_sparse_edge`

主走廊 `n51_c0`(pci118,-300)—`s28_c0`(pci101,0)—`n52_c0`(pci122,+300) 有健康雙向關係;
**`n91_c0`(pci209,遠角落 460/440)無關係**。`dw0-3` 走廊震盪、`dw4` 在走廊與深邊緣間**來回掃動**。
duration 86400s(24h),arfcn 633333。

## 3. 閉環實測(2026-08-18 12:28 UTC · dt-anr-xapp)

```
DETECT sparse-edge: n52_c0 (from sourceCellNcgi) measures pci=209
       rsrp=-82.9dBm @3.9/min vs median 21.4/min — sparse but steady 5/7 windows
       NRT no entry, capacity 4/32 not blocking, MRO flat
REPORTCGI ×3 → 三次一致 cgi=n91_c0 unique
12:28:12  ADD n52_c0→n91_c0  by=xapp   ack rtt 0.035s
12:28:14  ADD n91_c0→n52_c0  by=gnb-xn (+2s, xn-reverse step4c)
```

**止血(46 分鐘後)**:
```
n52_c0→n91_c0  att=1.0/min succ=1.0 n=46     ← 深邊緣改走換手,不再掉線
n91_c0→n52_c0  att=1.0/min succ=1.0 n=46     ← 回程正常
dw4(深邊緣主角)RLF = 0
```

### 🔑 最有價值的一點:`windowsPresent 5 / windowsMissed 2`

稀疏 PCI 在部分窗**整列消失**,guard 的穩定度機制(5/7 = 71% ≥ 50%)照樣放行 ——
**「稀疏不是駁回理由」在資料層面被真正執行過**,不只是規則上的口號。

### 來源歸屬:讀欄位、不寫死(雙輪實證)

| 時刻 | `sourceCellNcgi` | guard 動作 |
|---|---|---|
| 12:24:52(舊場景) | `s28_c0` | ADD s28_c0→n91_c0 |
| 12:28:12(re-arm 後) | `n52_c0` | ADD n52_c0→n91_c0 |

同一 binary、場景一變欄位就變、歸屬跟著變。**UE 移動時受害 cell 會變**的情況已被實測覆蓋。

## 4. 殘餘 RLF 判定:環境地板,不修

RIC 觀察到 `n52_c0` RLF 停在 3.0/min 不衰減、`n51_c0` 收到 previousPci=122 的重建。追查:

```
近10分 RLF = 30,by ue_id = {dw1:10, dw2:10, dw3:10}   ← 全是走廊高速掃動 UE
dw4(深邊緣、Q3 主角)= 0
```

走廊 UE 以 640m/30s ≈ **21 m/s(76 km/h)** 跨 3 個 cell,A3 換手鏈來不及完成 → 掉線落在 n51。
**不是缺 n52↔n51 關係** —— 幾何上 s28 在兩者中間,正常路徑是 `n52→s28→n51` 兩跳。
若補這條關係,等於「為掩蓋速度造成的 RLF 而增生非必要關係」,正是卷面要避免的過度增生。
→ **判定為劇本移動速度造成的環境地板,GAP 分支保持關閉。**

## 5. 本題補的 sim 能力(皆為通用,非僅第3題)

1. **`nrtCapacity` = `{limit, used}`**(`node_info` + func6 indication)—— 排除容量因素;**第9題直接沿用**。
2. **量測回報門檻 `MEAS_REPORT_MIN_RSRP_DBM`**(對齊 TS 38.331 `reportConfig`)——
   sim 原本**把所有 cell 照報**(不真實),導致稀疏樣本情境做不出來。預設 -110(不影響既有題),本場景 -86。
3. **`sourceCellNcgi` / `bySourceCell`**(量測聚合來源歸屬)—— RIC 指出的真缺口:
   鄰區關係本就是 per source cell,聚合列少了來源,xApp 無從決定 `ADD` 的 `sourceCellId`。

## 6. ⚠️ 本題繞了 6 版,教訓記錄

| # | 問題 | 類別 |
|---|---|---|
| 1 | 手寫劇本缺 `traffic` 等欄位 → driver 不推位置 | **我的錯** → 一律以已驗證劇本為基底改寫 |
| 2 | n91 放 x=3000,**超出場景 ±500m** → RSRP 凍結、距離失效 | **我的錯** → 場景地面僅 1000×1000 |
| 3 | duration 7200s 測試中途到期 → UE 靜止「假性平靜」 | **我的錯** → 改 86400s |
| 4 | 深邊緣 UE **park** → 只 RLF 一次、重建後不再回來,訊號斷 | **我的錯** → 必須來回掃動才有循環 |
| 5 | 曾誤判「gap<0 / RLF 是環境做不到」 | **判斷錯** → 第4題同機制有做到,實為劇本設計問題 |
| 6 | 絕對稀疏 0.6/min | **真限制** → sim 每 tick 每 UE 都記錄,改用相對稀疏 |
| 7 | `gap<0`(serving 遠弱於鄰區) | **未達成** → 交付時明確要求 guard 不依賴此條件 |

**UE 換 cell 只有兩條路徑**(查證結果,行為正確):A3 換手(需 NRT 關係)、RLF→重建到最強 cell。
沒有「連線中偷偷改投最強 cell」的邏輯。

## 7. 結論

**「稀疏但穩定的未知 PCI → 讀 `sourceCellNcgi` 定受害 cell → 排除容量/MRO/既有故障 →
REPORTCGI ×3 一致 → ADD → 換手恢復、深邊緣 UE 不再掉線」整條由真的 RIC xApp 自動跑通,零程式碼修改。**

第3題達成。API 涵蓋:`REPORTCGI` + `ADD` + `nrtCapacity` / `sourceCellNcgi` 觀測欄位。
