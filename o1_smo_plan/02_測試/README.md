# 測試

預計內容:
- `o1_telnet_facade/`:DT 假扮 OAI gNB 的 telnet 服務(`o1 stats` 等四指令)
- `samples/`:給 SMO 端先灌的 fileReady 事件與 TS 32.435 PM XML 樣本
- `scripts/`:連通測試(nc)、VES 送件(curl)、RESTCONF 查 mount 的腳本

## o1-adapter/(未入 git,見 .gitignore)
OAI 官方 o1-adapter 原始碼快照(gitlab.eurecom.fr/oai/o1-adapter,commit 2026-06-04「KPM management using NETCONF server」)。
建置:`cd o1-adapter && ./build-adapter.sh --adapter` → 映像 `adapter-gnb:latest`;假 gNB:`make`(見 Makefile 第 33 行)→ `oai-telnet-server:latest`。
我方改動只放在 `../o1-adapter-dt/`(模板、config、facade),不直接改這個目錄。

## D3/D4(2026-09-29)
orchestrator 自動起 O1:`ran-emulation-runtime-run-orchestrator/main/apps/run_lifecycle/services/optional/o1_spawner.py` + `launch_request_actor.py` 兩處 hook。adapter 改用 env 自產 config(`o1-adapter-dt/dt-entrypoint.sh`)。結果:`../03_結果/2026-09-29_D3D4_orchestrator自動起O1與D-T1多gNB.md`。
