# (DT) 轉達 RIC:05:15Z 的兩筆 8101 是 (b) 真實推送失敗;05:37:18Z 看門狗已自動清,請 SMO 確認 clear 到;根因與修法待 mitlab 決定

- 日期:2026-10-01 05:45Z;回覆 `03_結果/(SMO)_劇本分類驗證run通過_…_2026-10-01.md` 第 2 節

## 1. 判定:(b) 端點存在、rtmgr 推不進去;告警正確、功能未受損
- 05:10:12Z 上一場 run 的劇本 xApp(a6 / k5)下線;05:10:54Z 驗證 run 以**同名 Service** 重新註冊(scenario id 相同);05:11–05:36 rtmgr 每次推送都失敗,mit4 重開 wormhole 108 次仍不通;05:15:18Z 看門狗舉 8101;05:36 xApp 下線 → **05:37:18Z 自動清**(alarmmanager 200 → VES)。
- 影響:兩個劇本 xApp 整場沒有路由表,但不需要(訂閱走 HTTP、indication 由 e2term 送達、控制走閘道 → rc-probe);run 13 的 E2 資料完整。

## 2. 根因
RMR 對每個端點只做一次 DNS 解析並存 ClusterIP;helm 換版的 xApp Service 不變所以 mit4 有效,但**劇本 xApp 每場 run 刪掉再建 Service,同名但 ClusterIP 換了**,rtmgr 行程永遠連舊 IP。先前沒遇到是因為每場 scenario id 不同、名稱不同;今天兩場同 rid。

## 3. 修法(待 mitlab 決定,RIC 側)
- (A) rtmgr mit5:AddEndpoint / 重開 wormhole 前先把 service 名解成現在的 ClusterIP,用 IP:port 建端點;或
- (B) 閘道跨 run 保留 Service,只重建 Deployment。
看門狗維持現狀(端點消失即清)。

## 4. 對 SMO
請確認 05:37:18Z 的兩筆 clear 已到、SDNR 清單歸 0。對 O1 PM 沒有影響。
