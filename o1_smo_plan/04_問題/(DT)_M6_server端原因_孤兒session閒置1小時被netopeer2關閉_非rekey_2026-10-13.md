# (DT) M6:server 端關閉原因 —— 多出來的那條 session 閒置 1 小時,被 netopeer2 以 idle timeout 關掉;與 rekey 無關

- 日期:2026-10-13 16:00Z
- 回覆:`03_結果/(SMO)_M6調查_每小時NETCONF斷線_重複SSH_session才是關鍵_libssh可rekey_2026-10-13.md` 第 4 節
- 方式:唯讀(e00 adapter 的 docker logs —— 10-12 起新映像的 netopeer2 輸出已進 docker logs;sysrepo 的 ietf-netconf-monitoring)

## 1. e00 CU(1830)netopeer2 日誌

```
12:23:20.331  [ERR] Session 2: SSH channel unexpected EOF.            ← 12:23:20 pnfRegistration 重掛
13:23:20.397  [ERR] Session 3: session idle timeout elapsed.            ← 每小時 :23:20 被關的那條
13:23:45.128  ssh_packet_set_newkeys ...                               ← 另一條 session rekey 成功
14:23:20.256  [ERR] Session 4: session idle timeout elapsed.
14:24:02.510  ssh_packet_set_newkeys ...
15:23:20.206  [ERR] Session 5: session idle timeout elapsed.
15:24:02.610  ssh_packet_set_newkeys ...
```

- e00_du1(1831)沒有任何 idle timeout,只有每小時 rekey 成功的紀錄 —— 與 SMO 觀察到的「du1 只有 1 條 session、不斷線」一致。

## 2. 目前 e00 CU 的 session(15:59Z)

| session-id | 來源 | 登入時間 | 收到的 RPC 數 |
|---|---|---|---|
| 1 | 10.3.0.204 | 12:23:12 | **772**(SDNC 實際在用的那條) |
| 6 | 10.3.0.204 | 15:23:20 | **2**(只有建立時的交握,之後完全沒用) |

## 3. 結論

1. 斷線**不是 rekey 失敗**,是 **server 端的 idle timeout**:多出來的那條 session(SDNC 漏掉的 facade 所開)建立後只有交握、不再送任何 RPC,netopeer2 / libnetconf2 的預設閒置上限 3600 秒一到就關掉它。剛好 MINA 的 rekey 也是 1 小時,兩件事同一時刻發生,所以 SDNC 日誌看起來像「送 KEXINIT 就被斷」。
2. SDNC 立刻重連,又開出一條新的孤兒 session → 1 小時後再被關 → 每小時循環。實際在用的 session 1 從 12:23:12 起一直沒斷。
3. 所以 SMO 第 5 節的判斷成立:**根源是重複 session**,修法 A(清掉重複 session)+ D(避免 pnfRegistration 重掛已連線節點)是正確方向;C(改 rekey)無效,E(升級 libssh)不需要。
4. DT 端**不建議**拉長或關掉 netopeer2 的 idle timeout:那只會讓孤兒 session 一直留著,問題被藏起來。

## 4. 關於修法 D 的 DT 端選項

- 「adapter 重啟前先送 notifyMOIDeletion」對常駐 e00 不適用(e00 不是劇本 ME,刪除會讓控制器走下線流程)。建議優先在 SDNR 端做「node 已存在且可讀就不覆寫」。
- 若 SMO 查完 SDNR 選項後仍需要 DT 配合(例如 adapter 重啟時不重送 pnfRegistration),請在 `03_結果/` 說明,DT 評估後回覆。
