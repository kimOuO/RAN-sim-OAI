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
    bandwidth_mhz = models.FloatField(default=100.0)
    # 每 cell 的 TX 功率，Dashboard 由 update_cells 推。預設 43 dBm = macro 20 W 的典型值；
    # 跟 ran_sim_protocol.rsrp_model.DEFAULT_SCENE_LOSS_DB=36 搭配在 path_gain=0dB 時
    # 得到 +7 dBm，與舊 pipeline 43+14-50=+7 等價，避免 schema 變動引入計算偏移。
    # 改 Dashboard 端 power_dbm 會在 ≤1 tick 內反映到 RU 算出的 RSRP。
    power_dbm = models.FloatField(default=43.0)

    cell_created_at = models.DateTimeField()
    cell_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_cell"
        ordering = ["pci"]
