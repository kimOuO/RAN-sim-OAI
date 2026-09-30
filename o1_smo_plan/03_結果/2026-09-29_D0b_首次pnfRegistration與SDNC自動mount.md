# 結果:D0b —— DT 主機首次 pnfRegistration,SDNC 自動 mount 成功

日期:2026-09-29 07:23Z(台北 15:23)。執行:DT 端(使用者放行)。結論:**通過**。
ME 名稱定案:`gnb_208_095_000e00`(meid,與 RIC E2 node、PMS managedElementIds 同名)。

## 做了什麼
- 把 D0 那顆 `adapter-gnb:dt`(仍接官方假 gNB,資料是佔位值)改成:`ves.url=http://10.3.0.204:30417/eventListener/v7`、`pnf-registration=true`、`heartbeat-interval=30`、`node-id=gnb_208_095_000e00`、`location-name` 註明「D0b telnet fake data until D1」。
- 07:23:54Z 重建容器。

## 時間線
| UTC | 事件 | 證據 |
|---|---|---|
| 07:23:58.40 | adapter 送 pnfRegistration → VES 回 202 `Successfully send event` | adapter log |
| 07:23:58.79 | SDNC `onCreated Uri{gnb_208_095_000e00}`,加 keepalive facade | onap-sdnc-0 log |
| 07:23:59.09 | SDNC 警告 device 提供 hello 未宣告的 YANG(ietf-netconf-server、3gpp…),自動補為 required | 同上(無害,ric-1 也有) |
| 07:23:59.59 | **`connected - registering master mount point`**、`Netconf connector initialized successfully` | 同上 |
| 07:24:24 | heartbeat → 202 | adapter log |
| 之後 | adapter 容器內 830 埠有 2 條來自 10.3.0.204 的 ESTABLISHED | `/proc/net/tcp` |

從送出註冊到 SDNC 掛載完成 **1.2 秒**。

## 結論
- DT 主機 → SMO VES → Kafka → SDNR → 反連 DT 1830 這條 O1 註冊路徑全通,不需 call-home。
- SDNC 對本節點會與 `ric-1` 一樣顯示 `connection-status=connecting`(SDNC 顯示問題),以 log 的 connected 與 TCP 連線為準。
- 目前 mount 裡的內容是官方假 gNB 的佔位值(gNBId 1234、PLMN 001/01、兩個 NRCellCU),**不是 DT 的真資料**,D1 換成 facade 後才會正確。

## 待 SMO 端
- 在 ODLUX 看 `gnb_208_095_000e00`;用 RESTCONF 讀 `.../node=gnb_208_095_000e00/yang-ext:mount/_3gpp-common-managed-element:ManagedElement=gnb_208_095_000e00` 應看到 GNBCUCPFunction=0 與兩個 NRCellCU。
- 之後 D1 上線時 adapter 會重建,mount 會斷一下再重連,屬預期。
