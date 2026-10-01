# (DT) mitlab 決定:rtmgr 修法採 (A);N3 rApp 修正版**同意部署**(dry-run)

- 日期:2026-10-01 05:55Z
1. rtmgr:採 (A) mit5(建端點前先解析當前 ClusterIP),已通知 RIC;閘道不改。
2. **N3 rApp 修正版(時段對齊、新命名解析、跨 run 狀態、UE 流失加 4 UE 基準):mitlab 同意部署,模式維持 dry-run。** 請 SMO 執行 `deploy.sh dry-run`,部署後把版本與時間寫在 `03_結果/`。切 live 前仍須另外請 mitlab 核准。
3. T2(在 DT 的 run 上跑 dry-run):DT 下一場 run 時會通知;T3 的「先低負載再升高」劇本 DT 之後提草案。
