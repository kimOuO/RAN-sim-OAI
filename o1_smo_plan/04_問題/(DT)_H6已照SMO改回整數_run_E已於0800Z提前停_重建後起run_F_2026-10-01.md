# (DT) H6 已照 SMO 選項 (b) 改回整數;run E 已於 08:00:00Z 提前停;重建後起 run F 驗 H2 / H4 / H5

- 日期:2026-10-01 08:02Z;回覆 `03_結果/(SMO)_緊急_H6請先改回整數_…_2026-10-01.md`
- 收到 SMO 07:56Z 的分析(同 shard 內 integer 對 float / string 衝突 → 整筆點被拒,最長 7 天)。**run E(07:52–08:00Z)已送了 7 分鐘實數**,請 SMO 回報那段 e30 / e31 / e32 入庫實況;DT 08:00:00Z 已提前停 run E 止損。
- 改法:adapter 內部維持 double 計算,輸出四捨五入整數 kbit/s(`%.0f`);PM 檔其餘不變。整數為合法 real 值,規範符合度不受影響;N5 pmlog 改 float 時再協調送小數。
- H2 / H4 / H5 依 SMO 查證不受影響,維持。
- 映像重建中,約 08:06Z 起 **run F**(seed 18,15 分鐘),runId 另檔通知;請 SMO 在 run F 驗:dfc 取新檔名、InfluxDB 入庫(含 `DRB.UEThpDl` 仍為 integer)、告警配對、設備資訊。
