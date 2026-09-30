# 問 RIC 團隊:RIC(10.3.0.71)登錄進 SMO 所需資訊

日期:2026-09-29。狀態:**已送出,待回覆**。管道:SendMessage → `anr_xapps [fc5f0e]`(Remote Control,送達成功,對方需核准才會讀)。
我方探測:10.3.0.71 開 22、6443、30830、32080;10000 不通;32080 對 `/A1-P/v2/policytypes` 回 404。

1. RIC 部署形式、主機 IP。
2. a1mediator 對外 URL;`GET /A1-P/v2/policytypes` 現況(20008?)。
3. o1mediator NETCONF 埠(30830?)與帳密。
4. 為 DT 多場景在 RIC 上做過的調整(e2mgr/e2term、rtmgr、xApp 訂閱白名單、a1mediator/policy type、a1med-proxy 是否你們放的)。
5. 目前 E2 節點清單與 xApp。
6. 10.3.0.204 ↔ RIC-B 連通(a1mediator、o1mediator;反向 30094)。
7. PMS 八筆登錄哪些留/刪;20008 由哪個 xApp 註冊。
