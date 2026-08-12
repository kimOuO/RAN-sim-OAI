# ANR 驗測 Case #4:過期關係(Stale/Aging Relation)— sim 重現 + REMOVE

> 目標:重現 `ANR情境_v8.docx`「過期關係」— NRT 裡有一條**長期沒被用過**的鄰區關係
> (對端 cell 已退役/UE 不再造訪),xApp 依「age 大 + 累計 HO=0」判定過期 → **REMOVE**;
> 命中**保護條目**(no_remove)則 **REJECTED_PROTECTED**(改由 SMO 決策)。
> 日期:2026-08-12。狀態:**✅ sim 端重現 + 過期信號可觀測 + REMOVE/保護邏輯就緒**。

---

## 1. 問題(Problem)

NRT 關係只增不減會累積**過期條目**:對端 cell 退役、或拓樸變動後 UE 不再走該路徑,
關係卻留著 → 佔表、誤導 SON、拖慢決策。ANR 要能**辨識過期並安全移除**,但對**保護條目**
(標記不可刪,如骨幹 X2/關鍵鄰區)要拒絕移除、上報 SMO。

## 2. 劇本 `anr_stale_relation` + seed

- `main_c0`(pci10)/`keep_c0`(pci40)兩 cell,su0-4 連續震盪穿越 → `main_c0↔keep_c0`
  產生**健康 HO(att>0)** 當對照。
- 驗測腳本 seed 三條 `main_c0` 出發的關係:

| 關係 | created | att | 標記 | 預期 |
|---|---|---|---|---|
| `main_c0→keep_c0` | 新 | >0 | — | 健康,保留 |
| `main_c0→ghost_c0` | 2 小時前 | 0 | is_remove_allowed=True | **過期 → 可移除** |
| `main_c0→prot_c0` | 2 小時前 | 0 | **no_remove=True** | 過期但**保護 → 拒絕** |

## 3. 過期信號(func6 `e2NodeInformation.neighbourCellRelations`)

每條關係新增 **`relationAgeSec`**(now − created_at)給 xApp 判齡。實測(2026-08-12):

```
keep_c0   age=93s    hoValidated=True   att=0.7/min  noRemove=False   ← 健康
ghost_c0  age=7293s  hoValidated=False  att=0        noRemove=False   ← 過期,可移除
prot_c0   age=7293s  hoValidated=False  att=0        noRemove=True    ← 過期,保護
```

**判定式**:`relationAgeSec > 門檻(如 1800s)` 且 該關係 `perNeighbourRelation` 累計 HO att=0
→ 過期。`flags.noRemove==true` → 不送 REMOVE(或送了會被拒)。

## 4. RIC xApp 待做(閉環)

| 步驟 | 動作 |
|---|---|
| ① 觀測 | 讀 func6 `e2NodeInformation.neighbourCellRelations` + `kpmIndication.perNeighbourRelation` |
| ② 診斷 | age > 門檻 且 累計 HO att=0 → 過期候選;跳過 `flags.noRemove==true` |
| ③ 移除 | `SONTRIG_ANR_REMOVE(main_c0, ghost_c0, reason="aging")` |
| ④ 驗證 | 後續 indication:ghost_c0 關係消失(version 記 relationChangeEvents=REMOVE) |
| 保護 | 對 prot_c0 送 REMOVE → outcome `REJECTED_PROTECTED`(is_remove_allowed=False 或 no_remove=True)→ 上報 SMO |

REMOVE 落地:`anr_control_actor.apply_son_trigger` —— 命中 `is_remove_allowed=False` 或 `no_remove=True`
回 `REJECTED_PROTECTED`,否則刪關係。

## 5. 命令(REMOVE,ran_func=6,JSON,不用訂閱直接送)

```json
Control Header:  {"controlHeaderFormat":{"ricStyleType":1}}
Control Message: {"controlMessageFormat":{"sonTriggerRequest":{
  "requestType":"REMOVE","sourceCellId":"main_c0","targetCgi":"ghost_c0","reason":"aging"}}}
```

## 6. 結論(sim 端)

過期關係在 sim 端**可重現、可觀測**(`relationAgeSec` + att=0),REMOVE 與保護拒絕邏輯就緒,
交 RIC 建 aging guard 即可跑「發現過期 → REMOVE → 驗證消失 / 保護拒絕」閉環。
API 涵蓋:`REMOVE`(含保護條目拒絕)。
