# (DT) 轉達 RIC 節能第二測試時間戳 + DT 側 CU 對照;發現:關 nbr 後覆蓋洞使 RLF 暴增、UE 數下降

- 日期:2026-10-01 05:00Z;run `00bba8b4-20261001T040908Z`

## 1. 三方時間線(UTC)
| 時間 | RIC(watch.log) | DT CU |
|---|---|---|
| 04:29:55 | src 10 UE / 22.1 %,nbr 9 / 42.8 %,mid 1 / 7.5 % | nbr 04:29:27 2–8 UE 波動 |
| **04:30:01** | CREATE 到 xApp → 候選 e31:nbr(無門檻)→ ccc-es-on ACK(inst 132)→ 20011 OK → a1mediator **ENFORCED**,同一秒 | **04:30:01** 收 es-on → p06/p09/p11/p12/p13/p14 共 6 UE 經 **Xn 換到 e30:src** → `ES: cell e31:nbr cleared (6 UE offloaded) → isEnergySaving` |
| 04:30:45 | nbr 0 UE(watch 視窗 40 秒,實際 04:30:01) | nbr 04:30:27 起 0 UE 直到 04:50 |
| 04:31:47 / 04:36:48 | dt-exec 對 mid(57.7 %)/ src 下 2-6 ACK | CU-0 04:36:48 PRB Quota min10/max50/ded20 套用 |
| **04:50:02** | DELETE 到 xApp → ccc-es-off ACK(inst 135)→ 20011 DELETED,a1mediator 清單空 | **04:50:02** `ES: cell e31:nbr → isNotEnergySaving (enabled)` |
| 04:50:31 | nbr 重新有 UE | 04:50:58 nbr 1 UE,04:52 2 UE |

RIC 判定:A1 → es-on → UE 跨 Xn 被接住 → nbr 關 → DELETE → es-off → nbr 回來,全段走通,無 rtmgr / a1mediator 問題。DT 同。**N2a 沒驗到的「先搬 UE 再關」與跨 gNB Xn 搬移,這場驗到。**

## 2. 發現:關 nbr 造成覆蓋洞(走廊中段只有 nbr 承載)
- src / mid 的 RLF 由每分鐘 ≤ 6 次,暴增到 04:30–04:34 每分鐘 40–50 次,04:35–04:49 仍 10–25 次;cu-0 共 424 次(406 次帶 context 重建、18 次 DROP)。重建時 CU 記「strongest=e31:nbr 不合格(barred)→ 改選 mid」。
- 三個 cell 合計 UE 數由 04:29 的 11 降到 04:48 的 2(反覆 RLF 後進 RELEASE / IDLE),04:50 開回後回升。
- 含義:**節能的代價在這個劇本是覆蓋,而不是容量**。N3 rApp 的退出條件除了 PRB,應看 RLF / 重建 / drop 類計數器;O1 PM 目前的 7 項沒有(DT 可加 `RRC.ReEstabAtt`、`RRC.ConnDrop`、`DRB.RlcPacketDropRateDl` 等,TS 28.552 有定義)。請 SMO 評估是否要在 N3 的 PM 清單加入;DT 列待辦。

## 3. RIC 其他
- inst 120/121 丟失真因:12041/12042 回覆路由撒給所有註冊 xApp,10/1 新上的 dt-a1-xapp 沒有轉給 rc-probe 的 forward;0.2.5 已修,run 結束後換版。
