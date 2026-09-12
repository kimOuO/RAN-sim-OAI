# ran-emulation-runtime-run-monitor-frontend

模擬平台監控前端(Next.js App Router,TypeScript strict)。**零控制,只讀**(決策 §10.5)。
資料來源:registry(run / 場景)、run-orchestrator(`run_kpm_sample` / `run_handover_event` / `run_control_event` / `launch_request`)、DU `TickController/read`(達成倍速)、E2Adapter `AdapterStatusReader`。

| 路由 | 內容 |
|---|---|
| `/runs` | 所有 run:狀態、場景、倍速(設定→達成)、封存視窗數 |
| `/runs/[id]` | 單 run dashboard:Full KPM(per-cell,可展 per-UE)/ RIC 命令 / cell 狀態 / E2 面 / 換手・RLF |
| `/compare` | 2–4 個 run 同指標並排(sim-time 對齊) |
| `/runs/[id]/playback` | 逐視窗回放(slider) |
| `/runs/[id]/events` | 事件流(HO / RLF / RIC 命令 / 起停) |
