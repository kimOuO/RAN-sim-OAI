# ranp-sim

**NVIDIA Sionna RT 驅動的 5G RAN Digital Twin 計算後端**

Per-tick 收 UE 位置 → Ray tracing 算 site-specific 通道 → 輸出 E2-like JSON 指標給 FlexRIC / Omniverse UI。

架構符合 `backend_rule.md` 的 Backend Architecture Specification 2.0 (Iron Rules) 鐵則。

---

## 快速啟動

### 先決條件
- NVIDIA GPU driver ≥ 525
- Docker ≥ 20.10
- NVIDIA Container Toolkit
- `../scene_config.json` 存在（主專案根目錄）

### 第一次啟動

```bash
cd ranp-sim

# 1. 初始化（複製 .env.sample → .env，轉 scene_config.json → Mitsuba XML）
./shell/init_project.sh

# 2. 啟動容器（開發 mode：程式碼掛載進去，改 code 立即生效）
docker compose up -d

# 3. 驗證健康狀態
curl -X POST http://localhost:8000/api/v0.1/RanpSim/RanSignal/HealthChecker/read \
     -H "Content-Type: application/json" -d '{}'
```

### 日常使用

```bash
docker compose up -d      # 啟動
docker compose logs -f    # 看 log
docker compose restart    # 重啟
docker compose down       # 停
```

---

## 目錄導覽

- `main/` — Django 核心（settings / utils / apps）
- `main/apps/ran_signal/` — 唯一的 app
  - `actors/` — HTTP entry，Request Chain 最終 callable
  - `serializers/` — DRF Write/Read 序列化器
  - `services/business/sionna_operations.py` — Business Service（控 compute tick 狀態）
  - `services/optional/ran_calculation/` — Sionna engine + E2 formatter + MCS table
- `tools/scene_to_mitsuba.py` — scene_config.json → Mitsuba XML 轉換工具
- `scenes/` — Mitsuba XML 輸出目錄
- `requirements/` — base / local / production / test
- `docs/ARCHITECTURE.md` — 架構總覽（給團隊）
- `docs/INPUT_SPEC.md` — 輸入/輸出規格（給外部平台呼叫者）
- `backend_rule.md` — 後端鐵則規範（所有 PR 必須符合）

---

## Request Chain

```
Client
  → main/urls.py
  → main/apps/ran_signal/api/urls.py
  → Actor.function
  → Serializer (驗證)
  → Business Service (sionna_operations)
  → Optional Service (ran_calculation)
  → 回傳
```

## API 端點（全 POST）

| URL | Actor | 用途 |
|---|---|---|
| `/api/v0.1/RanpSim/RanSignal/ComputeRunner/compute` | ComputeActor.compute | per-tick 主計算 |
| `/api/v0.1/RanpSim/RanSignal/ConfigManager/read` | ConfigActor.read | 查目前配置 |
| `/api/v0.1/RanpSim/RanSignal/ConfigManager/reload` | ConfigActor.reload | 重載 scene_config.json |
| `/api/v0.1/RanpSim/RanSignal/HealthChecker/read` | HealthActor.read | 健康狀態 |

完整規格見 `docs/INPUT_SPEC.md`。

---

## 執行測試

```bash
docker compose exec ranp-sim pytest main/apps/ran_signal/tests/
```

不需 GPU 的測試（serializer / MCS table）都能跑；Sionna engine 整合測試需要 `--gpus all`。
