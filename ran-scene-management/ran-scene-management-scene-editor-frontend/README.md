# ran-scene-management-scene-editor-frontend

管理平台前端(Next.js App Router,TypeScript strict,react-three-fiber)。規範:`Omnivers_platform/frontend_rule.md`;設計:`new_plan/platform_restructure_plan.md` §3、§9.2。
**只做場景編輯與啟動;監控在 `ran-emulation-runtime-run-monitor-frontend`。** 舊 Dashboard 保留於 `../ran-scene-management-legacy-dashboard`(ANR 工作仍用它)。

| 路由 | 用途 |
|---|---|
| `/scenes` | 場景列表(卡片、active runs、Start / Stop / Precompute) |
| `/scenes/[id]` | 3D 編輯器:物件樹 / 畫布(gNB 群組、cell 可拖、UE 軌跡、建築)/ 屬性面板 |
| `/presets` | 資源庫:天線 preset、材質、DU 模板 |
| `/imports` | 劇本 JSON / GLB / OSM 匯入 |

資料存取一律 `hooks/feature/*` → `services/api/*` → `services/clients/registryClient.ts`(全 POST,對齊 backend_rule §7)。
