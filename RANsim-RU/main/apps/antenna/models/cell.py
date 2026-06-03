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
