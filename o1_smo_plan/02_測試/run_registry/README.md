# run 對照表(runId ↔ 劇本 ↔ ME ↔ 起訖時間)

日期:2026-10-01。狀態:已上線;2026-09-30T16:08Z 起的 run 由編排服務自動記錄,之前的由通知檔補回。

## 為什麼需要

SMO 的 PM(InfluxDB `pm-logg-bucket`)與告警只帶 ME 名稱,沒有劇本或 run 編號;ME 名稱又會被不同 run、不同劇本重用(區塊釋出後再分配)。SMO 的控制器只記每個 ME「目前」的 run,run 結束就清掉。要以劇本為單位收資料,需要一份長期保存的對照,把「劇本」換成一組「ME + 時間區間」。

## 資料

位置:`ran-emulation-runtime/run_logs/`(容器內 `PER_RUN_LOG_DIR`)。

| 檔 | 來源 | 內容 |
|---|---|---|
| `_o1_run_registry.jsonl` | 編排服務 `o1_spawner.py`,每次啟動 / 停止各寫一行 | 見下 |
| `_o1_run_registry.backfill.jsonl` | `run_registry.py backfill`,從 `<rid>/o1/notify_added_*` / `notify_removed_*` 補回 | 同格式,多一個 `"source": "backfill"` |

```json
{"ts": "2026-09-30T16:08:21Z", "event": "start", "runId": "00bba8b4-20260930T160819Z", "rid": "00bba8b4",
 "scene_run_uuid": "scene_run-…", "scenarioId": "corridor24_16_24",
 "mes": [{"gnb": "src", "cucp": "gnb_208_095_000e30", "du": "gnb_208_095_000e30_du1", "netconf_cucp": 1926, "netconf_du": 1927}, …]}
{"ts": "…", "event": "stop", "runId": "00bba8b4-20260930T160819Z", "rid": "00bba8b4", "scenarioId": "corridor24_16_24", "reason": "normal"}
```

- `runId` 與送給 SMO 的 `pnfRegistration` / `notifyMOIDeletion` 相同。
- `reason`:`normal`(正常收工)、`auto_restart`(自動重啟的「停」,隨後會有一筆新的 start)、`inferred`(沒有 stop 紀錄,由下一次 start 的時間推定)。

## 查詢

```
python3 run_registry.py list [--scenario corridor24_16_24] [--since 2026-09-30T00:00:00Z] [--md]
python3 run_registry.py windows --scenario corridor24_16_24      # CSV:每個 ME 的時間區間
python3 run_registry.py flux --scenario corridor24_16_24         # 每次執行的 InfluxDB Flux 查詢(DU ME)
python3 run_registry.py backfill                                 # 重新補回舊 run(整份重寫,可重跑)
```

## 限制

- 補回的 run(2026-09-29 到 09-30T13:26Z,共 12 次):`runId` 是用通知檔的時間合成的,**與當時送給 SMO 的值不同**(當時是 `00bba8b4`、`00bba8b4-…091215Z` 等,或根本沒帶);劇本名稱由 `rid` 對應(`c9ad0776` = `corridor24_00_08`、`00bba8b4` = `corridor24_16_24`);時間是通知檔的時間,與容器實際起停差幾秒。
- 只記有起 O1 容器的 run(`O1_SMO_ENABLE=on`)。
- PM 檔每 900 秒一份、時間戳是週期結束時間;run 頭尾的不完整週期帶 suspect,不會進 InfluxDB。所以一場 run 在 InfluxDB 的資料比 run 的起訖短。
- 這是 DT 端的紀錄。SMO 的資料本身仍不帶劇本資訊(待辦 A3)。
