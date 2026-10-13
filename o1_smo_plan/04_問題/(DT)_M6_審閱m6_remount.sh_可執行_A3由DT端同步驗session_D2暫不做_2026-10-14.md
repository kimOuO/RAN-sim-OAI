# (DT) M6:已審閱 m6_remount.sh —— 可以執行;A3 時 DT 端同步驗 session;D2 暫不做

- 日期:2026-10-14
- 回覆:`03_結果/(SMO)_M6修法提案_A清重複session指令_D防重掛_待mitlab核准_2026-10-14.md`

## 1. 腳本審閱結果:可以執行(實際執行仍待 mitlab 核准)

| 檢查 | 結果 |
|---|---|
| 節點白名單 | 正確,只允許 ric-1 / ric-dt-71 / gnb_208_095_* |
| 連線計數 | 取 /proc/net/tcp 第 3 欄(遠端位址)且狀態 01(ESTABLISHED),比對 host:port,邏輯正確;ric-1 會先轉成 ClusterIP |
| 設定備份 | 先存檔(600)並確認可解析才 DELETE,失敗即中止,正確 |
| DELETE 後連線未歸零 | 仍會 PUT 回原設定,狀態不會比現在差,正確 |

小建議(不影響執行):
1. `read H P < <(hostport)` 在 case 之前執行:若某次 DELETE 成功但 PUT 失敗,SDNC 已沒有該 node,重跑腳本會在 hostport 失敗、無法再用 `run` 補 PUT。建議在文件或腳本加一個 `restore <node> <備份檔>`,不必手打 curl。
2. 帳密以 `curl -u` 傳,執行期間在 SMO 主機的 ps 看得到;腳本執行時間短,可接受,僅提醒。

## 2. A3(e00)時 DT 端同步驗證

- DT 會在 A3 前後讀 e00 CU netopeer2 的 session 清單(ietf-netconf-monitoring)與日誌:預期 DELETE 後 session 全關,PUT 後只剩 1 條、RPC 數持續增加;下一個整點不再出現「session idle timeout elapsed」。
- A3 時間:避開劇本即可,DT 端隨時配合;執行前請經 Remote Control 或此資料夾通知 DT。

## 3. D2(常駐 ME 重啟時不重送 pnfRegistration):暫不做

- 只解決 e00 重啟這一種情況,且 D1(控制器自我修復)完成後就不需要。DT 端先不改 adapter,待 D1 結果再議。
