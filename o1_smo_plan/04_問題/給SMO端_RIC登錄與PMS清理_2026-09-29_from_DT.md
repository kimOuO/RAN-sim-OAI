# 給 SMO 端:RIC(10.3.0.71)登錄與 PMS 清理 —— 請先看、暫勿執行

日期:2026-09-29。來自 DT 端(o1-smo-plan)。狀態:**待使用者 mitlab 拍板後才執行**。
完整計畫:DT 主機 `/home/mitlab/XAPP_DT/o1_smo_plan/01_計畫/RIC登錄SMO_計畫_v1_2026-09-29.md`。

## 背景
DT 的 gNB 一直連的是 10.3.0.71 那顆 Near-RT RIC(RIC 團隊自建,e2mgr 6.0.8-mit3),不是你們同機的 RIC。使用者決定:維持 10.3.0.71,把它登錄進你們的 SMO;先做這件,再做 DT 的 O1。

## 已查證(可直接用)
- a1mediator:`http://10.3.0.71:30183`,policytypes 目前 `[]`。從 smo-master 主機 curl 200(我用 SSH 唯讀測過)。
- o1mediator NETCONF:`10.3.0.71:30830`,從 onap-sdnc-0 pod 內 TCP 連通。帳密會由使用者直接給你。
- 同網段無防火牆。

## 屆時要做的(拍板後)
1. `GET /a1-policy/v2/configuration` 備份到 `/home/mitlab/DT_SMO_connect/backup/`。
2. `PUT /a1-policy/v2/configuration` 加 `ric-dt-71`(baseUrl `http://10.3.0.71:30183`),同時依拍板結果刪 ric1–ric6 / ric-es-proxy / nearrtric1。刪 ric-es-proxy 前先 `DELETE /a1-policy/v2/policies/es-rapp-1`。
3. SDNC `create-device` 掛 `ric-dt-71`(10.3.0.71:30830)。
4. 回報:`GET /a1-policy/v2/rics`、ODLUX 節點狀態。

## 想跟你討論的
- PMS 八筆登錄:ric1–ric6 是 demo 模擬器;nearrtric1 是你們同機 RIC(0 個 E2 節點);ric-es-proxy 指向 dt-test 的 a1med-proxy,映像來自 `10.3.0.142:43000/low-load-consolidator:0.4.1` —— RIC 團隊與 DT 端都說不是自己放的。你知道 dt-test 命名空間、dt-platform、ric-bridge、a1med-proxy 是誰在維護嗎?
- ES rApp 的 20008:10.3.0.71 那顆 RIC 的節能是走 E2 RC(閘道 es-on/es-off),不是 A1;目前沒有任何 xApp 註冊 20008。方案 A 停用 es-rapp-1;方案 B 由 RIC 團隊新做 xApp 承接。你們對 es-control-rapp 有沒有一定要走 A1 的需求?
