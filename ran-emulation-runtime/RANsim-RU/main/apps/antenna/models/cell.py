"""Cell — 每個 RU-served cell 一筆，含位置與方位。

對應 legacy sionna_engine.py:113-145（每 cell 一個 Transmitter，自己的 azimuth）。
"""
from django.db import models


class Cell(models.Model):
    id = models.AutoField(primary_key=True)
    cell_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    name = models.CharField(max_length=128, unique=True, db_index=True)
    pci = models.IntegerField(db_index=True)
    azimuth_deg = models.FloatField(default=0.0)
    tilt_deg = models.FloatField(default=0.0)   # 機械下傾,正 = 往下(P5,進 Sionna orientation)
    # B2(2026-09-16):RIC 可控的波束狀態。語意對齊 O-RAN WG1 §4.6:
    #   electrical_tilt_deg / active_beam_ids 屬 O1 / OFH M-plane 的慢迴路,
    #   max_layers 屬 E2 的快迴路。這裡都存在 cell 上,由 set_beam_control 端點改。
    electrical_tilt_deg = models.FloatField(default=0.0)       # 正 = 往下;疊在天線 preset 的預設值之上
    active_beam_ids = models.JSONField(default=list, blank=True)  # GoB 子集;空 = 全部可用
    max_layers = models.PositiveIntegerField(default=0)        # 0 = 用全域 RU_MAX_RANK
    # 2026-09-17(WG1 §4.6.3 其餘 O1 控制):
    trx_active_ratio = models.FloatField(default=1.0)          # 開著的 TXRU 比例(節能:64T→32T = 0.5)
    beam_taper = models.CharField(max_length=16, default="", blank=True)  # ""/hamming/taylor:加窗 → 波束變寬、旁瓣變低
    beam_power_offsets_db = models.JSONField(default=dict, blank=True)    # {beam_id: dB(≤0)},Cat B 每波束功率
    ul_load = models.FloatField(default=0.0)    # 上一 tick UL PRB 負載 0–1(DU 經 dl_tti 推來;P6 上行干擾用)
    gnb_id = models.CharField(max_length=64, db_index=True, default="")
    is_active = models.BooleanField(default=True, db_index=True)

    position_x = models.FloatField()
    position_y = models.FloatField()
    position_z = models.FloatField()

    frequency_ghz = models.FloatField(default=2.5)
    bandwidth_mhz = models.FloatField(default=40.0)
    # 預設 23 dBm — OAI rfsim 字面 PDSCH total=4 dBm 但 max_rxgain=114 dB 等效
    # 把 link budget 抬回。DT 沒 RX gain,改用 23 dBm 補,RSRP 落 OAI 實效範圍。
    power_dbm = models.FloatField(default=23.0)

    cell_created_at = models.DateTimeField()
    cell_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_cell"
        ordering = ["pci"]
