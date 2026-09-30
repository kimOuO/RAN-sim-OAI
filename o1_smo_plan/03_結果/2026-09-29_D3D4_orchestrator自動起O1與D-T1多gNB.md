# 結果:D3/D4 —— run-orchestrator 自動起 O1;D-T1 多 gNB 測試

日期:2026-09-29 09:33Z 起。執行:DT 端(mitlab 放行)。狀態:**6 個新 ME 全部自動 mount(通過)**;PM 分流、單 DU 告警、收工清理 見下方補記。

## 實作(D3/D4)
- `adapter-gnb:dt` 映像加 `dt-entrypoint.sh`:有 `O1_NODE_ID` 等 env 就自產 `config.json`,並內建 DT 版三組模板;無 env 時沿用 bind mount(D1 相容)。
- orchestrator 新增 `main/apps/run_lifecycle/services/optional/o1_spawner.py`:每顆 gNB 起 `o1facade-<rid>-<i>`(host net,telnet 9000+2·slot / 9001+2·slot)、`o1adapter-cucp-<rid>-<i>`(830→1830+2·slot、22→1222+2·slot,ME=meid)、`o1adapter-du-<rid>-<i>`(1831+2·slot / 1223+2·slot,ME=`<meid>_du<gnb_du_id>`)。容器掛 `ransim.scene_run_uuid` 標籤 → `teardown()` 自動清;不進 health monitor;失敗不擋 run。
- `launch_request_actor.py`:start 在 `health_monitor.start_monitor` 前呼叫 `o1_spawner.spawn`;stop 在 `teardown` 前呼叫 `o1_spawner.on_stop`。通知檔寫到 `run_logs/<rid>/o1/notify_added|removed_<ts>.md`。
- 環境變數:`O1_SMO_ENABLE`(預設 on)、`O1_HOST_IP`、`O1_VES_URL`、`O1_PM_INTERVAL`(900)、`O1_FACADE_IMAGE`、`O1_ADAPTER_IMAGE`。
- 生效方式:orchestrator 為 bind mount + gunicorn 單 worker → `docker restart ran-run-orchestrator`。

## D-T1 執行
- 09:33:51Z 啟動 `corridor24_00_08`(區塊 1,3 gNB,18 UE,3600 s),run `scene_run-12ab0576…`(rid c9ad0776)。
- 09:34:06–08Z orchestrator 起 9 顆 O1 容器,全部 Up、adapter 0 錯誤、各 2 筆 VES 202(pnfRegistration + heartbeat)。
- SDNC:`gnb_208_095_000e10/_du1`、`000e11/_du1`、`000e12/_du2` 六個 ME 皆 `onCreated → connected - registering master mount point → Netconf connector initialized successfully`。埠 1862–1867 / 1254–1259。
- 通知檔 `notify_added_2026-09-29T093408Z.md` 自動產生,已轉到 SMO `04_問題/`。
- 注意:e12 的 DU ME 是 `_du2`(該 gNB 的 gNB-DU id 為 2),名稱由 topo 決定。

## D-T1 步驟 3:只停一顆 DU,告警只出現在該 gNB(通過,09:46–09:47Z)
- 第一次嘗試(09:35:38Z 停 `du-c9ad0776-2` 超過 120 s)踩到平台 health monitor 的**自動重啟**:09:37:44Z 判 unhealthy → 09:39:32Z stop → 09:39:51Z start,整場 run 含 9 顆 O1 容器全部重建(SDNC 看到 6 個 ME 重新 mount)。**教訓:DU 停機測試要 < 120 s。**
- 同時發現 facade「接受連線後立刻關閉」會讓 adapter 認為已連線而清掉告警 → facade 改為 watchdog:後端 HTTP 不可達就**關閉該身分的 listener**(adapter connect 被拒 → 告警),恢復再開。run 內 3 顆 facade 以新映像原地重建。
- 第二次(09:46:50Z 停 30 s):facade `[du] listener CLOSED` → e12 DU adapter `telnet disconnected` → 09:47:04Z **MAJOR**(VES 202);09:47:21Z 啟動 DU → 09:47:27Z listener OPEN → `telnet connected` → 09:47:31Z **NORMAL**(202)。**其餘 5 顆 adapter 0 告警**,CU-CP 身分不受影響。
- SMO 端驗證 `SEC_FAULT_OUTPUT` / SDNR / ODLUX 待回報。

## D-T1 收尾(10:03–10:10Z)
- SMO 端第六輪驗證:6 ME mount ✅、NRM 內容 ✅、E2 三顆都連 RIC-A ✅、PMS 已加 e10/e11/e12 ✅、**單 DU 告警隔離 ✅**、SDNC 每 mount <1 MiB(估 90 ME 仍在 2.1 GiB 內)。PM 依 ME 分流到 pmlog ✅ 但新 DU 因兩次重啟沒有完整 15 分鐘週期(檔案 suspect=true,pmlog 正確地跳過)→ 待第二場。
- 第二次自動重啟(09:49:39Z)原因:30 s 停 DU 後 DU tick 未恢復(`degraded DU tick 未運行`)→ health monitor 335 s 後重啟 → 6 adapter 在 teardown 中送出 MAJOR 但來不及 CLEAR → SDNR 留 6 筆。**10:05Z 由 DT 手動送 6 筆 CLEAR(202)**;`o1_spawner.on_stop` 已改為 teardown 前先送 CLEAR。
- 10:02:59Z 停 run(第一次排程用錯欄位 `run_id`,正確為 `scene_run_uuid`):9 顆 O1 容器清除、`notify_removed_…100300Z.md` 產生。
- 10:06:50Z 再起同場域(同 run id,ME 同名同埠)補驗 PM 完整週期,排 10:33Z 停。
- SMO 定案:PMS managedElementIds **保留**不刪(slot 重用)。PCI 重複(e00/e11 都 PCI 1)為不同場景,刻意。
- TEIV:SMO 同意由其建專用 KafkaUser 發佈(待 mitlab 核准),第一次只發常駐 e00 + RIC;`teiv_platform_e00_and_ric.json` 已交(11 entity / 14 rel;RIC PLMN、nearRtRicId 為假設值)。

## 第二場 run(10:06:50–10:33:00Z):PM 完整週期 + 新收工流程
- 無 DU 停機、無自動重啟;10:30:00Z 落第一個完整週期檔(10:15–10:30)。
- 10:33:00Z 停止:orchestrator `on_stop` 先送 6 筆 CLEAR(全部 202),再 teardown(容器 0 殘留),`notify_removed_…103300Z.md` 產生。SMO 驗證待回報。
