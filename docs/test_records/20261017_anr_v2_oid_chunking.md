# 2026-10-17 E2SM-ANR 合規版(RAN function 8):OID、分塊、能力宣告

## 原本(func 6,v1)的問題
1. **OID**:`1.3.6.1.4.1.53148.1.1.2.6`,落在 O-RAN 聯盟企業號底下,O-RAN 正式 E2SM 的分配位置,不是我們能用的空間。
2. **分塊**:整份 ANR 觀測 zlib 後切成 6000 B 的塊,散在多則 RIC_INDICATION,單則無法獨立解讀(目前劇本規模都只有 1 塊,
   cell / 鄰區一多就會觸發)。
3. **能力宣告不完整**:RAN Function Definition 只宣告 SON control,沒有宣告它實際提供的兩種 indication
   (action 0 週期觀測、action 2 關係變更)。
4. **header 時間戳一律 0**(順帶發現):CU 改送 v10 格式後,觀測裡只有 ISO 字串 `timestamp`,沒有 `timestamp_ms`,
   v1 header 讀不到就填 0。xApp 若用 header 時間戳會全錯;本次未改 v1(避免影響現行 dt-anr),v2 已修。

## 新版(func 8,v2)
- **OID**:`2.25.100789996811842101158541215498991799117.1.2`(與完整 KPM v2 同一 UUID 弧,`.1.2` = ANR)。
- **能力宣告**:report style 1(週期觀測,action 0)、report style 2(鄰區關係變更,action 2)、control style 1(SON 觸發 ADD / REMOVE / FLAG)。
- **週期觀測(action 0)**:每期 N + 1 則,每則可單獨解壓、解讀:
  - 每個 serving cell 一則:該 cell 的組態(含 A3 參數)、以它為 source 的鄰區關係 / 關係變更事件 / 旗標事件、
    cell 級 KPM(`指標.NCGI` 鍵)、逐關係 KPM、該 cell 的 NRT 用量(limit + used)。
  - 一則 node:cell 清單、頻率關係、NRT 上限與 usedByCell 總表、ANR 開關、量測聚合、CGI 取樣、CCC 事件,
    以及 source 不在 serving cell 清單裡的殘留條目(換劇本後的舊 cell 等)—— 一筆不丟。
- **關係變更(action 2,事件驅動)**:與上一輪的 (source, target) → version 比較,每個有變更的 source cell 送一則:
  該 cell 目前完整關係表 + 變更標示(added / removed / versionBumped)。沒有變更不送。
- **分頁**:單則壓縮後超過 6000 B 時,所有清單欄位同步切成 n 段;第一頁帶完整非清單欄位,後續頁帶識別欄位與該段條目。
- **header**:`{format:"DT-ANR-v2", timestamp(ISO), timestamp_ms, sceneSimMs, sn, action, report:"cell"|"node"|"change", cell,
  encoding:"zlib", report_index, report_count, page, pages}`;同一期(或同一次變更)的各則共用 sn 與時間戳。
- **控制**:func 8 的 RIC Control 走與 func 6 相同的處理;ACK / Failure 帶回請求的 function id。
- **事件觸發**仍沿用 KPM Format 1 的 reportingPeriod(與完整 KPM v2 一起另案改)。

## 不影響現有功能
- func 6(v1)完全不變;func 8 由 `E2SM_ANR2_ENABLE` 控制宣告,**預設關**(per-run 模板明確寫 off)。
- 劇本級開關:run knob `anr_v2`(宣告 func 8)、`anr_v2_dump`(func 8 每則原始位元組寫到 `E2Adapter/logs/anr2_dump_*.jsonl`,驗證用)。
- adapter 對 func 8 每則記一行 `ANR2_IND`(給 RIC 對「收齊」)。

## 修改的檔案
- `RANsim-E2Adapter/.../codec/e2sm_anr_codec.py`:v2 常數、RFD、`build_anr_v2_payloads()`、`build_anr_v2_change_payloads()`、`relation_versions()`
- `RANsim-E2Adapter/.../codec/e2ap_codec.py`:E2 Setup 宣告 ANR2(gate)
- `RANsim-E2Adapter/.../sctp_link/sctp_loop.py`:func 8 訂閱 / 控制分流;兩個 producer 依 function id 選 v1 / v2;`ANR2_IND` 記錄與 dump
- `RANsim-E2Adapter/.../actors/control_audit_actor.py`:名稱表加 8
- `RANsim-CU/.../e2/global_e2_node_id.py`:RAN function 清單加 8
- `run-orchestrator/.../per_run_template.json`、`launch_request_actor.py`:`E2SM_ANR2_ENABLE=off`、knob `anr_v2` / `anr_v2_dump`

## 驗證
- 新測試 `tests/unit_test/test_anr_v2.py`(6 項):OID / RFD;每 cell 一則 + node 且內容歸屬正確;關係、事件、旗標、逐關係 KPM、
  cell 級 KPM 一筆不遺失(含殘留 source);大 cell 分頁後每則 ≤ 上限且可拼回 400 筆;關係變更依 source cell 正確標示新增 / 移除 / 版本;v1 不變。
  E2 adapter 全部 unit test 42 / 42 通過;orchestrator run_lifecycle 27 / 27。
- 以 e00 實際資料試編:v1 一則 762 B(header timestamp_ms = 0);v2 兩則 cell 各 575 B + node 370 B,timestamp_ms 正確。

## 待辦
- RIC:dt-anr 改訂 func 8(已發訊息說明格式)。
- 與完整 KPM v2 一樣以 B 案驗證(func 6 與 func 8 並存對照,含 action 2 變更推播與 SON control 的 ACK)。

## 追加:事件觸發改為合規版(func 7 與 func 8,2026-10-17)
- 自訂 E2SM 不再借用 E2SM-KPM 的 ASN.1 EventTriggerDefinition,改為本模型自有 JSON:
  `{"eventTriggerFormat": 1, "reportingPeriodMs": <100–3,600,000>}`(Event Trigger Style 1「Periodic」)。
- 兩個 v2 的 RAN Function Definition 新增 `listOfSupportedEventTriggerStyles`,各 report style 以 `ricEventTriggerStyleType: 1` 引用。
- 不合規的事件觸發回 E2AP **RICsubscriptionFailure**(新增 `encode_ric_subscription_failure()`),以前是默默用 1000 ms:
  - 空 / 不是 JSON 且非允許的舊格式 → `protocol: abstract-syntax-error-falsely-constructed-message`
  - `eventTriggerFormat ≠ 1`、週期超出範圍或型別錯 → `protocol: semantic-error`
- 遷移期仍接受 E2SM-KPM Format 1(RIC 現行 xApp 送的格式)並記警告;`E2SM_V2_LEGACY_TRIGGER=off` 後只收 JSON。
- func 5 / 6(v1)不變。
- 測試:`tests/unit_test/test_v2_event_trigger.py`(6 項);E2 adapter 全部 48 / 48。
- 給 RIC 的 func 8 樣本:`10_13_plan/04_測試結果/data/anr_v2_samples/anr_v2_samples.json`。
