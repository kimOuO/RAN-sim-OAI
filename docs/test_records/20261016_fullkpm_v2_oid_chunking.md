# 2026-10-16 DT 完整 KPM 合規版(RAN function 7):OID 與分塊

## 原本(func 5,v1)不合規的兩點
1. **OID**:`1.3.6.1.4.1.53148.1.1.2.100`。53148 是 O-RAN 聯盟的 IANA 私有企業號,`.1.1.2.x` 是 O-RAN 分配
   正式 E2SM 的位置(RC = .3、CCC = .4),我們不能自行在其下分配,將來可能和正式編號衝突。ANR(`.1.1.2.6`)同樣問題,本次未改。
2. **分塊**:整份全量報告 zlib 壓縮後切成 6000 B 的塊,分散在多則 RIC_INDICATION(header 帶 part / parts)。
   單則 indication 無法獨立解讀,要收齊同 sn 的所有塊才能還原,不符 E2AP「每則 indication 自成一份報告」的語意。
   切塊原因:OSC e2term SCTP 接收 buffer 只有 8 KB。

## 新版(func 7,v2)
- **OID**:`2.25.100789996811842101158541215498991799117.1.1`。`2.25` 是 ITU-T X.667 / ISO/IEC 9834-8 的 UUID 弧,
  任何人以自己產生的 UUID 取得,免註冊且全域唯一;其下 `.1` = E2SM、`.1.1` = 完整 KPM、`.1.2` 預留給 ANR。
  查過 IANA PEN 清單(2026-10-15 版),本單位沒有自己的企業號;日後申請到可再換。
- **依內容切成自足報告**,每個 period 送 N+1 則:
  - 每個 cell 一則:cell 量測(含 UE、波束)、服務中 UE 的 ue_status、該 cell 的 PM 列、所屬 gNB 的 BBU 狀態。
  - 一則 node:cell 清單、未附著 UE、warnings。
  - 每則都可單獨 zlib 解壓、JSON 解讀,不需和其他則拼接;header 帶 `report_index / report_count` 讓 xApp 知道該期共幾則。
  - 單一 cell 壓縮後仍超過 6000 B 時依 UE 分頁(cell.ues 與 ue_status 同步切);第一頁帶完整 cell 屬性、PM、BBU,
    後續頁帶時間戳、gNB、cell 識別與該頁 UE,每頁仍可獨立解讀。
  - zlib 是本模型在 RAN Function Definition 中宣告的訊息編碼(與 E2SM-CCC 用 JSON 同類做法),不是傳輸層分塊。
- Header:`{format:"DTFULLKPM-v2", timestamp_ms, sn, report:"cell"|"node", gnb_id, cell_id, encoding:"zlib", report_index, report_count, ue_page, ue_pages}`
- Event trigger 仍沿用 KPM Format 1 的 reportingPeriod(下一步再改成本模型自己的格式)。

## 不影響現有功能
- func 5(v1)完全不變;func 7 與其並存,由環境變數 `E2SM_FULLKPM2_ENABLE` 控制是否在 E2 Setup 宣告,**預設關**
  (per-run 模板明確寫 `off`)。RIC 端 dt-fullkpm 改好訂 func 7 後再開;確認穩定後移除 func 5。
- e00 常駐場域的 adapter / CU 沒有重啟,仍是舊程式。

## 修改的檔案
- `RANsim-E2Adapter/.../codec/e2sm_fullkpm_codec.py`:v2 常數、`encode_fullkpm_v2_ran_function_description()`、`build_indication_payloads_v2()`
- `RANsim-E2Adapter/.../codec/e2ap_codec.py`:E2 Setup 宣告 FULLKPM2(gate)
- `RANsim-E2Adapter/.../sctp_link/sctp_loop.py`:func 7 訂閱走同一個 producer,依 func id 選 v1 / v2 編碼
- `RANsim-E2Adapter/.../actors/control_audit_actor.py`:func 名稱表加 7
- `RANsim-CU/.../e2/global_e2_node_id.py`:RAN function 清單加 7
- `run-orchestrator/.../per_run_template.json`:`E2SM_FULLKPM2_ENABLE=off`

## 驗證
- 新測試 `tests/unit_test/test_fullkpm_v2.py`(5 項):OID 不在 53148 下、每 cell 一則 + node 一則且內容對應正確、
  UE 不遺失不重複、大 cell 分頁後每則 ≤ 上限且可拼回 400 UE、v1 不變。E2 adapter 全部 unit test 36 / 36 通過。
- 以 e00 實際資料試編:v1 一則 1644 B;v2 兩則 cell 各約 1.4 KB(含 PM 1 列、BBU)+ node 135 B。
- 過程中發現 pm / bbu_status 以 `gnb-<id>` 為鍵、e2 / ue_status 用 `<id>`,已在 v2 對應。

## 待辦
- RIC:dt-fullkpm 改訂 func 7(已發訊息說明格式,待回覆)。
- 開啟後以一次短劇本確認 RIC 收到的每則都能獨立解讀。
- ANR(func 6)OID 同樣改到 `.1.2`;event trigger 改為本模型自有格式。
