# SCTP Self-ABORT 排查 + 修復紀錄 (2026-05-27)

## TL;DR

`KpmRouter dispatcher` 無法分類 IM/CCO/ES,看似「KPM 沒到 RIC」。
debug 過 **2 小時+**,走偏了 PPID byte order / ASN.1 spec 版本 / stale subscription 三條歧路,
真因是 **host 早上 reboot 後沒跑 `host_setup_sctp.sh`**,iptables/sysctl 被清空,
SCTP multi-homing 把 docker0 IP 廣告出去 → RIC heartbeat 路由錯誤 → 自動 ABORT 整條 association。

**修法 = 一行**:
```bash
sudo bash /home/mitlab/XAPP_DT/RANsim-E2Adapter/shell/host_setup_sctp.sh
docker restart ransim-e2adapter
```

## 症狀

```
SCTP connect    OK
E2 Setup        OK (successfulOutcome accepted=[2,3])
SUB_REQ 收到    OK
SUB_RESP 送出   OK (33 bytes)
RIC_INDICATION  送 2~4 個
1~4 秒後        "Connection reset by peer" (errno 104)
進 5min backoff,下次重連又同樣 cycle
```

## 我方 vs RIC team 視角不一致

| 視角 | 看到 |
|---|---|
| 我方 e2adapter log | `SCTP recv failed: [Errno 104] Connection reset by peer` |
| RIC e2t log | `epoll error events 8 on fd 21, RAN NAME : gnb_208_095_000e00` (對端 close) |
| RIC submgr | `ErrorSource='E2Node' ErrorCause=' '` (空字串) |
| RIC SCTP stats | `SctpAborteds = 3 / SctpShutdowns = 24` |

雙方都說「對方關的」,沒人 admit 是自己 ABORT。

## 走偏的三條歧路

### 歧路 1 — PPID byte order
**證據**: pcap 抓到我方送 PPID `0x46000000`、RIC 送 `0x46`
**修法**: `_send_sctp` 加 `socket.htonl(ppid)`
**結果**: SCTP 維持時間從 1 秒 → 4 秒,**部分有幫助但不是根因**
**保留**: 修正應該保留(實際 wire byte 確實該轉)

### 歧路 2 — ASN.1 spec 版本不對 (v1 vs v3)
**懷疑**: 我方 pycrate spec OID `1.3.6.1.4.1.53148.1.2.1.0` 看起來像 v1,RIC e2t image 是 v3 (m-release)
**驗證**: RIC team 手動 byte-level decode 我方 SUB_RESP outer framing,**確認 v1/v2/v3 共通**
**結論**: spec 版本不是問題

### 歧路 3 — RIC stale subscription state
**懷疑**: rtmgr 還有舊 subId=15 路由,跟新 subId 衝突
**驗證**: RIC team 重啟 submgr/rtmgr,instance_id 重置成 1,SCTP 還是斷
**結論**: stale state 不是根因

## 真正根因 (1 句話)

**Host 1:19 小時前 reboot 後沒跑 `host_setup_sctp.sh`,iptables 被清掉,
docker0 介面 (172.17.0.1) 被 SCTP multi-homing 廣告給 RIC,
RIC 對 172.17.0.1 送 heartbeat 走自己 lo → 失敗 → ABORT。**

## 證據鏈

### 1. host uptime 跟 sysctl 對應

```bash
$ uptime
12:33:42 up  1:19   ← reboot 過

$ sysctl net.sctp.addip_enable
net.sctp.addip_enable = 0   ← 應該是 1

$ sysctl net.sctp.path_max_retrans
net.sctp.path_max_retrans = ?  ← 沒設成 99999
```

### 2. SCTP assoc LADDRS 證實 multi-homed

```bash
$ docker exec ransim-e2adapter cat /proc/net/sctp/assocs
LADDRS: 10.3.0.217 172.17.0.1 10.0.0.18  <-> *10.3.0.71
         ↑ 主路徑      ↑ docker0       ↑ 另一個 docker 網
```

雖然 e2adapter env 設了 `SCTP_BIND_IP=10.3.0.217`,Linux SCTP kernel
**還是把 host 上所有 IP 廣告為 secondary path**。

### 3. host 上其他 docker bridge 多到爆

```
docker0      172.17.0.1   ← RIC host 一定也有(common)
br-1cc4xx    172.18.0.1
br-9a11xx    172.19.0.1
br-c111xx    172.21.0.1
br-0f21xx    172.20.0.1
```

任何一個 IP 跟 RIC host 那邊衝突,RIC heartbeat 就會 loop。

### 4. 為什麼 5-10 ~ 5-21 那段時間 work

**Host 沒 reboot**,iptables/sysctl 持續生效:
- iptables OUTPUT DROP sctp -d 172.17.0.0/16 → 阻止 docker0 路徑被選為 SCTP heartbeat
- iptables OUTPUT DROP sctp -d 10.0.0.0/24 等 → 阻止其他 docker network
- `path_max_retrans=99999` → 即使 heartbeat fail 也不會殺主 path

5-22 ~ 5-26 sim 沒跑,reboot 發生在那段時間後,5-27 重啟測試才爆雷。

## 修法

### `shell/host_setup_sctp.sh` 做的事

```bash
# 1. iptables 阻 SCTP 出站到 docker/k8s 內網 (避免 multi-homed loopback)
iptables -A OUTPUT -p sctp -d 172.17.0.0/16 -j DROP
iptables -A OUTPUT -p sctp -d 10.0.0.0/24 -j DROP
iptables -A OUTPUT -p sctp -d 10.244.0.0/16 -j DROP
iptables -A OUTPUT -p sctp -d 10.96.0.0/12 -j DROP

# 2. sysctl SCTP retrans 拉到 99999 (heartbeat fail 不殺主 path)
sysctl -w net.sctp.path_max_retrans=99999
sysctl -w net.sctp.association_max_retrans=99999

# 3. 寫進 /etc/sysctl.d/99-ransim-sctp.conf 持久化
```

**問題**: iptables 沒寫進 `/etc/iptables/rules.v4` → reboot 後消失。
要持久化 iptables 需要 `iptables-persistent` 套件或自寫 systemd unit。

## 修復前後對比

| 指標 | 修前 | 修後 |
|---|---|---|
| SCTP assoc 維持時間 | 1-4 秒 | **60+ 秒,持續** |
| RIC_INDICATION sent | 0-3 個 | **177 個並持續** |
| TX_QUEUE | 0 | **1216 bytes pending** |
| sub_id 存活 | 每次斷重建 | **單一 sub_id 持續存活** |
| Influx 真實 KPM | 沒有,RIC fake | **DU 端 rlc/prb/thp 真實值流入** |

## 給未來自己的 SOP

**任何時候出現「SCTP recv failed by peer + 1-4 秒就斷」的症狀**,**第一個動作**:

```bash
# 1. 先檢查 host uptime
uptime

# 2. 檢查 sysctl
sysctl net.sctp.path_max_retrans
# 預期 99999,如果是 default 5 就是被清掉了

# 3. 跑 setup script
sudo bash /home/mitlab/XAPP_DT/RANsim-E2Adapter/shell/host_setup_sctp.sh

# 4. restart e2adapter
docker restart ransim-e2adapter

# 5. 驗證 SCTP assoc 維持 30 秒以上
docker exec ransim-e2adapter cat /proc/net/sctp/assocs
sleep 30
docker exec ransim-e2adapter cat /proc/net/sctp/assocs
# 兩次都有 row 表示穩定
```

**不要再走** PPID / spec / stale subscription 那三條歧路。**先設 SCTP host setup**,99% 是這個。

## 對應 memory 條目

`memory/sctp_host_reboot_wipe.md` 寫過這個 pattern:
> Every host reboot wipes iptables + skips sysctl.d for net.sctp.*;
> e2adapter looks like RIC reject but is SctpAborteds — rerun host_setup_sctp.sh as sudo

下次踩坑前**先看 memory**。

## 永久修法建議

| 短期 | 已做 — `host_setup_sctp.sh` 在 reboot 後手動跑 |
| 中期 | 寫 systemd unit / cron `@reboot` 自動跑 `host_setup_sctp.sh` |
| 中期 | 用 `iptables-persistent` 把 rule 寫進 `/etc/iptables/rules.v4` |
| 長期 | e2adapter code 改用 `sctp_bindx(SCTP_BINDX_ADD_ADDR)` 強制 single-homed,不依賴 iptables workaround |

## 副產物 (今天順帶修的 bug)

1. **`_send_sctp` 加 `socket.htonl(ppid)`** — wire byte order 正確化(雖然不是根因,但對的)
2. **`_handle_sub_req` 加 `SUB_RESP hex` log** — 之後 debug RIC team 可以手動 decode 比對
3. **`_indication_producer_loop` 加 LIFECYCLE.start / exit log** — 看 producer 為何 exit
4. **KpmRouter `pdcp_kbit *= 8`** — bytes → kbit 單位轉換修正
5. **CU 新增 `SessionController/release_all`** — Stop Sim 連 CU UE state 一起清
6. **RANsim-UE `sim_orchestrator.start_sim` auto-stop** — 切劇本不會 409

這些都應該保留(都是正確修法,只是當時誤以為是斷線根因)。
