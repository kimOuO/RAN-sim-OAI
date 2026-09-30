# (SMO 端提供)給 RIC 團隊:A1 閉環與 RIC 上報 SMO 的需求 —— 存檔

來源:SMO 端,2026-09-30,由使用者轉貼,DT 端轉達 RIC 團隊(session anr_xapps)。
- §1 A1 閉環:RIC 選 policy type(建議先測試用 30000,之後 20008 節能)、xApp 收 A1_POLICY_REQ/回 RESP、a1mediator 註冊 type、rtmgr 路由;SMO 端負責 a1med-proxy 轉 create_schema→policySchema 並改 PMS baseUrl(需 mitlab 核准)。
- §2 RIC 上報 SMO:vespamgr 指向 http://10.3.0.204:30417(v5/v7,noAuth),sourceName=ric-dt-71;告警經 alarmmanager;心跳 60 s;PM 選配。
- §3 選配:RIC 以 pnfRegistration 或 call-home 自動註冊 O1。
- 建議順序:§2 → §1 → §3。
- 註:mitlab 在 2026-09-29 曾決定「這一階段不做 20008 消費者與 VES 告警對接」;此文件為 SMO 端的下一階段提案,範圍是否開放待 mitlab。
