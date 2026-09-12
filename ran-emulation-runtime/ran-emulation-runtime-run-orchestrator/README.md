# ran-emulation-runtime-run-orchestrator

模擬平台的執行編排系統:接受「起 / 停一個 scene_run」的請求、之後(P2)用 docker SDK spawn
per-run 容器、以及**run 級遙測封存**(KPM / RIC 命令 / 換手),供監控前端與回放使用。
設計:`new_plan/platform_restructure_plan.md` §1.1、§4.2、§10.4。

| app | 表 | 說明 |
|---|---|---|
| run_lifecycle | launch_request | start / stop 請求紀錄(P0 只記錄;P2 接 docker) |
| run_telemetry_archive | run_kpm_sample, run_control_event, run_handover_event | E2Adapter 每次 snapshot 後 POST 進來 |

`scene_run` 本體在 registry;此處只存 `f_scene_run_uuid` 字串(跨 repo,backend_rule §12-2)。

## API(全 POST)
`/api/v0.1/Run_orchestrator/{Module}/{Model}Controller/{create|update|delete}`、`{Model}Reader/read`
