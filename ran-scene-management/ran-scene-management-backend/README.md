# ran-scene-management-backend

管理平台唯一的後端(2026-09-16 由 network-element-registry 改名,並併入 building-geometry-ingest)。
URL = `/api/v0.1/Scene_management_backend/{App}/{Component}/{Element}`,全 POST(backend_rule §7)。

## App 分類(main/apps/,平鋪,以前綴分類)

| 分類 | app | 內容 |
|---|---|---|
| 場域 | `field_scene` | scene、building、material(ITU 材質)、劇本匯入/匯出、舊劇本相容端點 `RAN/Scenario/*` |
| 設備 | `equipment_ran` | gnb、du、cell、ru、neighbor_seed |
| 設備 | `equipment_ue` | ue、ue_waypoint、ue_active_window、ue_traffic(流量) |
| 設備 | `equipment_preset` | antenna_preset、gnb_config_template、du_config_template |
| 3D 渲染/轉換 | `render_scan_mesh` | 掃描 GLB → 材質分類 → Mitsuba(自 ingest 併入) |
| 3D 渲染/轉換 | `render_osm_footprint` | 地名/bbox → OSM 建築 → Mitsuba(自 ingest 併入) |
| 執行 | `simulation_run` | scene_run、run_instance、run_knob |

資料表名(db_table)保留改名前的字首(如 `scene_layout_scene`、`preset_catalog_material`),改名只動 Django 狀態,不搬資料。
3D 匯入產物落在 `SCANNED_ASSETS_DIR`(compose 掛 `scanned-building-assets/` 到 `/app/assets`)。

## API(全 POST)
`/api/v0.1/Scene_management_backend/{Module}/{Model}Controller/{create|update|delete}`
`/api/v0.1/Scene_management_backend/{Module}/{Model}Reader/read`
read body:`{"<table>_uuid": …}` 單筆;`{"f_<parent>_uuid": …}` 或任一欄位 = 過濾列表;空 body = 全部。
