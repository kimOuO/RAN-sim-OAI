---
name: omniverse_decouple_goal
description: "目標:RAN sim 要能在失去 Omniverse 時仍正常跑;劇本/場景應改存進 physics_db(目前空的),不再單點依賴 Omniverse ran_dt"
metadata: 
  node_type: memory
  type: project
  originSessionId: 44eb4981-d92e-4cd9-a931-ac9d47e32626
---

**目標(使用者要求,2026-07 提出)**:RAN sim 應該在 **Omniverse 掛掉時仍能正常跑**。目前不行 —— Omniverse(`omniver_backend:8001` + `ran_dt` DB)是**劇本 + 場景 + 歷史的單一真相 / 編排中樞**,是整個編排層的**單點故障**。

**現況(實查 2026-07-01)**:
- 連 Omniverse 的容器:**Dashboard / UE / Physics / CU**。不連的:**DU / RU / E2Adapter**。
- 劇本「管理/儲存」在 Omniverse `ScenarioController`(upload/list/read/delete → `Scenario.raw_json`);UE 的 `scenario` app 只是**執行者**(start/stop/status,起跑時去 Omniverse 拉 raw_json),UE **無 DB(0 migrations)**。
- 場景幾何(建築/gNB/UE)也存 Omniverse;Physics `SceneGateway/init` + `precompute/run_precompute.py` 從 Omniverse 拉場景/劇本建 Sionna 場景。
- 底層引擎(DU/RU/CU/E2Adapter + `cu_db/du_db/ru_db` + 記憶體)其實**不依賴 Omniverse**,tick loop/MAC/RLC/E2 都不打它;CU 對 Omniverse 的 push 是 fire-and-forget。

**方向**:把**場景 + 劇本存進 `physics_db`**(目前 **0 表、建了沒用**,見 [[cache_vs_live_nondeterminism_kpm]] 附近脈絡與 DB 盤點),讓 Physics(或某個引擎側服務)成為場景/劇本的來源,使核心 sim 能脫離 Omniverse 獨立跑。Omniverse 退回純「3D 視覺化 + 選配歷史」。

**Why**:Omniverse 定位是視覺化/資料中樞,不該是模擬的必要相依;失去它整條 /scenarios、/editor、precompute、歷史/playback/RC 觀察全斷。

**How to apply**:把「劇本/場景來源」抽象成介面(現在硬打 `OMNIVERSE_URL` 的 scenario_loader / scene_gateway / run_precompute),來源可切 Omniverse 或 physics_db;`physics_db` 補 Scenario/scene 表。這是**待辦評估**,尚未實作。

see [[scenario_source_omniverse_db]]、[[omniverse_db_schema]]、[[unified_sim_architecture]]
