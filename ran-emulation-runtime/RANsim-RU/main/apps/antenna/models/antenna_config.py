"""AntennaConfig — RU 唯一一張陣列配置表。

backend_rule §1-2 / §5-1：每個 table 一個檔案。
合法值對齊 ran_sim_protocol.common.AntennaArrayConfig。

對 OAI: PlanarArray (legacy sionna_engine.py:91-108) 的描述層落點。
"""
from django.db import models


POLARIZATION_CHOICES = (
    ("V", "vertical"),
    ("H", "horizontal"),
    ("VH", "dual-VH"),
    ("cross", "cross-polarized"),
)

PATTERN_CHOICES = (
    ("tr38901", "3GPP TR 38.901 sector"),
    ("dipole", "dipole"),
    ("iso", "isotropic"),
    ("hw_dipole", "halfwave-dipole"),
    ("vh_dipole", "VH dipole"),
)


class AntennaConfig(models.Model):
    id = models.AutoField(primary_key=True)
    antenna_config_uuid = models.CharField(max_length=255, unique=True, db_index=True)

    rows = models.PositiveIntegerField()
    cols = models.PositiveIntegerField()
    polarization = models.CharField(max_length=16, choices=POLARIZATION_CHOICES)
    pattern = models.CharField(max_length=32, choices=PATTERN_CHOICES)
    vertical_spacing = models.FloatField(default=0.5)
    horizontal_spacing = models.FloatField(default=0.5)

    antenna_config_created_at = models.DateTimeField()
    antenna_config_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_antenna_config"
        ordering = ["-antenna_config_updated_at"]
