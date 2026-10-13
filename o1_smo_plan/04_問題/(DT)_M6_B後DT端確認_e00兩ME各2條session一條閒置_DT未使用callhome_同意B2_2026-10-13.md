# (DT) M6:B 之後 DT 端確認 —— e00 兩個 ME 各 2 條 session(一條閒置);DT 沒有使用 callhome;DT 端同意 B2

- 日期:2026-10-13 16:56Z(DT 主機時鐘)
- 回覆:`03_結果/(SMO)_M6修法提案_…_2026-10-14.md` 的「B 結果與真正的根因」

## 1. e00 的 session(ietf-netconf-monitoring,16:56Z)

| ME | session | 登入 | RPC 數 |
|---|---|---|---|
| e00 CU(1830) | 8 | 16:43:48 | 95(使用中) |
| e00 CU(1830) | 9 | 16:43:48 | **2**(只有交握) |
| e00_du1(1831) | 4 | 16:43:48 | 15(使用中) |
| e00_du1(1831) | 5 | 16:43:48 | **2**(只有交握) |

- 兩條同一秒建立、其中一條建立後不再有 RPC,與 SMO「兩套 topology 實作各連一次」的判斷完全一致;e00_du1 也變成 2 條。
- 預期 17:43:48Z 起閒置那條會被 netopeer2 以 idle timeout 關閉(DT 會再看日誌確認)。

## 2. DT 沒有使用 callhome

- DT 的 adapter(含常駐 e00 與劇本 ME)netopeer2 **沒有任何 call-home 設定**(ietf-netconf-server running 中 0 筆);DT 一律走 SDNC → DT 的 SSH 連線。
- 編排服務與 docker-compose 也沒有引用 callhome / 30266。
- 所以關掉 SDNC 的 callhome 對 DT **沒有影響**。DT 端同意 B2(實際執行仍待 mitlab 核准)。

## 3. B2 之後 DT 端會做的驗證

- 讀 e00 兩個 ME 的 session 清單:各只剩 1 條;下一個整點起不再出現「session idle timeout elapsed」。
- 下一場劇本:pnfRegistration 自動掛載後,劇本 ME 也只有 1 條 session。
