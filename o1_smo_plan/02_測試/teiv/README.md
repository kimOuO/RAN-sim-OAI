# TEIV 拓樸匯入(給 SMO 的拓樸清單)

`gen_teiv_events.py`:從 DT orchestrator 的 `FieldReader/config|list` 產生 smo-teiv 0.3.0 匯入格式(CloudEvent,type `topology-inventory-ingestion.create|merge|delete`)。
物件:ManagedElement(=meid)、OCUCPFunction=0、ODUFunction=1、NRCellCU/NRCellDU/NRSectorCarrier=<local cell id>;關係:MANAGEDELEMENT_MANAGES_*、ODUFUNCTION_F1CLINK_OCUCPFUNCTION、*_PROVIDES_*、NRCELLDU_USES_NRSECTORCARRIER。
id 用 `urn:3gpp:dn:ManagedElement=<meid>,…`(與 O1 的 DN 一致,O1 的 GNBCUCPFunction/GNBDUFunction 在 TEIV 叫 OCUCPFunction/ODUFunction)。
發佈:topic `topology-inventory-ingestion`(Strimzi 9092 SASL/SCRAM,需 SMO 的 KafkaUser,例如 `ncmp-to-teiv-adapter-ku`)—— **由 SMO 端發佈**。
查詢:`http://topology-exposure.smo:8080/topology-inventory/v1/domains/RAN/entity-types/NRCellDU/entities`。

## 2026-09-29 修正(SMO 第七輪 §2.2)
- 方案 A:DU 側 id 在 `ManagedElement=<meid>_du<N>` 下,與 O1 DU ME 對齊;`--me-map` 可吃 orchestrator 的 `notify_added_*.md` 或 `me_map.json` 取得每 gNB 的 DU id。
- DU 側只放 O1 目前呈現的第一個 cell(NRCellDU=0);CU 側全部 cell。待 O1 DU 多 NRCellDU 後同步。
- RIC-A:`nearRtRicId` 699598(0xAACCE)、pLMNId 310/411(RIC 團隊確認 ric-dep 預設)。
- 2026-09-29 11:00:sourceIds 含 O1 DN(`GNBCUCPFunction` / `GNBDUFunction` 路徑);delete 事件帶 entity+relationship id;`make_run_teiv.sh <field_id> <rid> create|delete` 從 `run_logs/<rid>/o1/` 產檔。首次發佈結果:`../../03_結果/2026-09-29_TEIV首次發佈_常駐e00與RIC.md`。
- 2026-09-29 11:10:預設加 E2LINK(CU-CP 與 DU → `ric-dt-71`),`--ric-meid ""` 可關閉。run 事件處理順序見 `../../04_問題/(DT)_TEIV產生器補E2LINK_2026-09-29.md`。

## 2026-09-29 15:15 定案(C1 = 方案 A,TEIV 以官方 ncmp-to-teiv-adapter 為準)
- `gen_teiv_links.py`:只產 E2LINK(CU-CP、DU → ric-dt-71)與 F1CLINK,aSide 用 adapter 的 `urn:oran:smo:teiv:…GNBCUCPFunction/GNBDUFunction` id;create 一檔、delete 每條一檔(TEIV 0.3.0 多筆 delete 會卡死)。輸出在 `links/`。
- `gen_teiv_events.py` / `make_run_teiv.sh` 停用,保留備援。
