# (DT) 節能第二測試開始:run 已起;mitlab 決定「不設 dlPrbUsage」;04:30Z 下 policy、04:50Z 刪

- 日期:2026-10-01 04:12Z
- mitlab 決定(2026-10-01 04:05Z):**第二測試不設 `dlPrbUsage`**(只驗搬移與關閉,門檻已在 N2a 驗過);Alertmanager resolve_timeout **先不改**;vespamgr 加 `8101:` **不做**;N3 草案第 7 節四項 **照 SMO 建議**(A:DME/Kafka;門檻 30/70/5 分鐘;一般 Deployment;自動辨識劇本但需設定開啟)。
- 已同步通知 RIC(session `anr_xapps`)。

## run
| 項目 | 內容 |
|---|---|
| runId | `00bba8b4-20261001T040908Z`,`corridor24_16_24`,seed 11(與 N2a 相同),`anr_auto_add=true`,gNB PM **60 秒** |
| 起訖 | 04:08:55Z 起,3600 秒 → 約 **05:09Z** 自動停止(停止時 9 CLEAR + 6 notifyMOIDeletion) |
| ME | e30 src `gnb_208_095_000e30`/`_du1`;e31 nbr `gnb_208_095_000e31`/`_du1`;e32 mid `gnb_208_095_000e32`/`_du2` |
| NCI | src 59506688、nbr 59523072、mid 59539456(與 `example_ES2_nbr_with_exclusion.json` 一致) |

## 時程(UTC)
| 時間 | 動作 | 誰 |
|---|---|---|
| 04:12–04:28 | 檢查 ME 都連上、NCI 與 O1 一致、policy 檔過 schema(請拿掉 `dlPrbUsage`,或 RIC 若說缺欄位 schema 不過則填 100) | SMO |
| **04:30:00** | `PUT smo-es2-nbr-1`(type 30001,FORBID src+mid → 候選 nbr,esPercentage 30) | SMO |
| 04:30–04:50 | nbr 的 UE 經 Xn 搬到 src/mid 後關閉;觀察 `DRB.MaxActiveUeDl`、`RRU.PrbTotDl`:nbr 歸零、src/mid 上升 | 三方 |
| **04:50:00** | `DELETE smo-es2-nbr-1` → es-off → nbr 開回、UE 回流 | SMO |
| ~05:09 | run 自動停止 | DT |

DT 側會記:CU 的 ES 狀態機(toBeEnergySaving → 趕人 → isEnergySaving)、每個 UE 的 Xn 換手事件與時間、nbr 每分鐘 UE 數、dt-exec 有無對 src 下 2-6。
