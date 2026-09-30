# (DT) D0b:DT 主機第一筆 pnfRegistration 已送,SDNC 已自動 mount,請你們驗

日期:2026-09-29 07:23Z。來自 DT 端。

- ME / node-id:**`gnb_208_095_000e00`**(mitlab 定案:O1 的 ME 直接用 meid,與 RIC E2 node、PMS managedElementIds 同名)。
- NETCONF:`10.3.0.217:1830`,SSH,帳號 netconf(密碼在 pnfRegistration 的 additionalFields 內,與 OSC 慣例相同)。SFTP `10.3.0.217:1222`(PM 檔之後放這)。
- 我方看到:VES 202 → SDNC log 07:23:59.59 `connected - registering master mount point`、`Netconf connector initialized successfully`;adapter 容器內有 2 條來自 10.3.0.204 的 NETCONF 連線。從送出到掛好 1.2 秒。
- **注意:目前 mount 裡的內容是 OAI 官方假 gNB 的佔位值**(gNBId 1234、PLMN 001/01、GNBCUCPFunction=0 底下兩個 NRCellCU),不是 DT 真資料;D1(telnet 假面)上線後才會換成 DT 的 PCI/頻率/PLMN 208-95。到時 adapter 會重建,mount 會斷一下再重連。
- 心跳每 30 s 一筆到 VES(`heartbeat` domain)。

請你們:
1. ODLUX 看 `gnb_208_095_000e00`;RESTCONF 讀 `.../node=gnb_208_095_000e00/yang-ext:mount/_3gpp-common-managed-element:ManagedElement=gnb_208_095_000e00?content=nonconfig` 回報有沒有拿到樹。
2. 從 dfc pod 測 `10.3.0.217:1222` TCP 連通(S2),之後 PM 取檔用。
3. 若 SDNR 對這個節點也每小時斷一次,記下時刻,一併對 rekey 假說。
