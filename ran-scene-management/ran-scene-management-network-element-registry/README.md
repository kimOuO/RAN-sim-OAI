# ran-scene-management-network-element-registry

管理平台的網元登錄系統:場景 / 建築 / gNB / DU / Cell / RU / UE / 執行實例的**唯一權威資料庫**。
架構依 `Omnivers_platform/backend_rule.md`;設計依 `new_plan/platform_restructure_plan.md` §2。

| app | 表 |
|---|---|
| preset_catalog | material, antenna_preset, du_config_template |
| scene_layout | scene, building |
| radio_access_element | gnb, du, cell, ru, neighbor_seed |
| user_equipment | ue, ue_waypoint, ue_traffic, ue_active_window |
| simulation_run | scene_run, run_knob, run_instance |

## API(全 POST)
`/api/v0.1/Network_element_registry/{Module}/{Model}Controller/{create|update|delete}`
`/api/v0.1/Network_element_registry/{Module}/{Model}Reader/read`
read body:`{"<table>_uuid": …}` 單筆;`{"f_<parent>_uuid": …}` 或任一欄位 = 過濾列表;空 body = 全部。
