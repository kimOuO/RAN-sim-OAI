# XAPP_DT — 5G NR RAN Digital Twin

分裂式 **5G NR RAN 數位孿生**:把 OAI/O-RAN 的 **CU / DU / RU / UE** 拆成獨立 Django HTTP 微服務,加 **Sionna RT 光追物理層**、**Omniverse 3D**、以及 **HTTP↔SCTP/ASN.1 翻譯器(E2Adapter)** 對接真實 RIC。目的:讓 **xApp 先在 DT 驗證 handover / PRB 控制決策,再部署到實體 RAN**。

架構總覽 → [`docs/architecture/dt_ran_architecture.md`](docs/architecture/dt_ran_architecture.md)
運作流程 → [`docs/workflow.md`](docs/workflow.md)

---

## 服務總覽

| 服務 | 埠 | 角色 | 文件 |
|---|---|---|---|
| RANsim-CU | 8101 | gNB-CU:RRC/F1AP/NGAP/E2/A3 HO | [`RANsim-CU/doc`](RANsim-CU/doc/README.md) |
| RANsim-DU | 8102 | gNB-DU ★真實來源★:MAC/RLC/PF 排程/PM/Tick | [`RANsim-DU/doc`](RANsim-DU/doc/README.md) |
| RANsim-RU | 8103 | O-RU:天線/Beamform/SINR/channel cache | [`RANsim-RU/doc`](RANsim-RU/doc/README.md) |
| RANsim-UE | 8105 | UE 群 + 劇本執行器 | [`RANsim-UE/doc`](RANsim-UE/doc/README.md) |
| RANsim-E2Adapter | 8201 | gNB E2 termination(HTTP↔SCTP/ASN.1) | [`RANsim-E2Adapter/doc`](RANsim-E2Adapter/doc/README.md) |
| Physics_sim | 8104 | Sionna RT 光追 + 劇本/場景倉庫(physics_db) | [`Physics_sim/doc`](Physics_sim/doc/README.md) |
| Omniverse backend / Kit | 8001 / 8080 | 3D 場景 + 歷史 + 劇本倉庫 | `Omnivers_platform/` |
| Dashboard | 3010 | 控制 + 監控前端(Next.js) | `Physics_sim/Dashboard/` |
| Postgres | 5433 | cu_db / du_db / ru_db / physics_db | — |

外部 RIC 經 E2Adapter 以 SCTP(PPID=70)對接。

---

## 快速啟動

```bash
docker compose up -d          # 拉起全部服務(需 NVIDIA GPU 給 Physics)
docker compose ps             # 確認健康
```

部署/設定檔在 [`deploy/`](deploy/)(`postgres-init.sql` 建 4 個 DB、`scene_config.json` 平台共享場景)。

### 跑一場劇本
1. 上傳劇本(見 [`docs/scenarios/`](docs/scenarios/) 的 JSON schema)。
2. (cached 模式)`POST :8104/api/v0.1/Physics/Precompute/run`。
3. 起 sim:`POST :8105/api/v0.1/UE/Sim/SimController/start` body `{"source":"scenario","scenario_id":"cco_20min","speed_x":2,"sim_dt_ms":250}`。
4. Dashboard `:3010/logs` 看 KPM / RC / PRB quota;`SimController/stop` 停。

完整流程 → [`docs/workflow.md`](docs/workflow.md)。

---

## 文件地圖

| 主題 | 位置 |
|---|---|
| 架構(圖 + 模組↔OAI) | [`docs/architecture/`](docs/architecture/) |
| 運作流程 | [`docs/workflow.md`](docs/workflow.md) |
| 劇本(JSON + generator + template) | [`docs/scenarios/`](docs/scenarios/) |
| xApp 意圖合約(IM/CCO/ES) | [`docs/intents-interface.md`](docs/intents-interface.md) |
| RC 觀察 API | [`docs/api/rc_observation_api.md`](docs/api/rc_observation_api.md) |
| 各系統深入(用途/模組/API) | 各服務的 `doc/README.md`(見上表) |
