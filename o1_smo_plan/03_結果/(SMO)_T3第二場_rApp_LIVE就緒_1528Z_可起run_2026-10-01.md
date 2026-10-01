# (SMO) T3 第二場:rApp **LIVE 就緒**(15:28:02Z),DT 可以起 run

- 日期:2026-10-01 15:28Z
- 回覆:`04_問題/已回覆/(DT)_RIC已修好C18_請SMO切LIVE_DT隨即起T3第二場_2026-10-01.md`
- 依據:mitlab 12:57Z 預先核准(只限 T3 重跑這一場);policy 內容不變

| 項目 | 內容 |
|---|---|
| 切 LIVE | **15:28:02Z**,SMO 執行 `deploy.sh live`;DME 工作 201、PMS service `smo-n3-es-rapp` 201 |
| 版本 | `rapp_logic.py` 18affb511cc3(跟第一場相同,沒有修改) |
| 切換前檢查 | `ric-dt-71` AVAILABLE、有 type 30001;PMS 和 RIC-A 都沒有 30001 的 policy;corridor 的 ME 都還沒上線 |

- 根因收到:dt-preproc 撞號 → observation 沒有 PRB → xApp `policy-wait dl-prb-unknown`。修正後,這場同時也是驗證「有 `dlPrbUsage` 時會送 es-on」(mitlab 預先核准的條件之一),SMO 會以 O1 的 e32 `operationalState` 變成 DISABLED 為準。
- SMO 會照第一場的方式記錄(`SMO_OSC/dep/n3-es-rapp/t3/`);結束後切回 dry-run。
- **請 DT 起 run,並通知 runId。**
