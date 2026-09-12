# ran-scene-management-building-geometry-ingest

管理平台的建築幾何匯入系統。把兩種來源變成 **Sionna 可用的 Mitsuba 場景 + registry 的 `building` 列**:

| app | 來源 | 管線(自 Omniverse backend 複製,2026-09-12 P1-4;Omniverse 側原樣保留) |
|---|---|---|
| scan_mesh_ingest | 掃描 GLB | `glb_reader`(不含 USD)→ `scan_material_classifier`(幾何+色彩規則分 itu_* 材質)→ `scan_segmentation` → `glb_to_mitsuba` |
| osm_footprint_ingest | OSM bbox / 地名 | `nominatim_client`(地名→bbox)→ `overpass_client`(抓 OSM)→ `osm_to_mitsuba`(擠出建築、Mitsuba + footprints) |

**沒有 USD / pxr 依賴**;產物落在 `SCANNED_ASSETS_DIR`(compose 掛 `scanned-building-assets/`)。
`attach_to_scene` 呼叫 registry `Scene_layout/BuildingController/create` 把幾何掛進 scene(跨 repo,只傳 uuid)。

## API(全 POST)
- `Scan_mesh_ingest/ScanMeshImporter/import_glb`(multipart:file,name,recenter?,material_mode?)
- `Scan_mesh_ingest/ScanAssetReader/read`、`ScanAssetController/delete|attach_to_scene`
- `Osm_footprint_ingest/OsmFootprintImporter/geocode|generate`
- `Osm_footprint_ingest/OsmMapAssetReader/read`、`OsmMapAssetController/delete|attach_to_scene`
