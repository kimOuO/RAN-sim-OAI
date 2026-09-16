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
