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
    # ── 三層天線模型(2026-09-16):rows/cols 語意不變 = 單面板元件排列 M/N ──
    # 元件層 (Mg,Ng,M,N,P) ──W_virt(TR 38.901 式 7.3-1)──▶ TRX 層 ──合併──▶ CSI-RS 埠層 (N1,N2)
    panels_mg = models.PositiveIntegerField(default=1)
    panels_ng = models.PositiveIntegerField(default=1)
    panel_v_spacing = models.FloatField(default=0.0)         # 面板中心間距 d_g,V(λ);0 = 緊鄰(TR 38.901 §7.3)
    panel_h_spacing = models.FloatField(default=0.0)         # d_g,H
    trx_v_group = models.PositiveIntegerField(default=1)     # 每 TXRU 垂直帶幾片同極化元件
    trx_count = models.PositiveIntegerField(default=0)       # 0 = 自動推
    electrical_tilt_deg = models.FloatField(default=0.0)     # 正 = 往下
    csi_ports = models.PositiveIntegerField(default=0)       # 0 = 等於 trx_count
    port_n1 = models.PositiveIntegerField(default=0)         # TS 38.214 Type I
    port_n2 = models.PositiveIntegerField(default=0)
    ru_category = models.CharField(max_length=1, default='A')   # O-RAN WG4 CUS-plane
    bf_method = models.CharField(max_length=16, blank=True, default='')   # predefined / attribute / weight / channel_info
    gob_az_beams = models.PositiveIntegerField(default=0)   # GoB 方位波束數;0 = 取正交波束數(= N1)
    gob_el_beams = models.PositiveIntegerField(default=0)   # GoB 仰角波束數;0 = N2

    # UE 端陣列(P5;None = 用 env UE_ARRAY_* / 1×1)
    ue_rows = models.PositiveIntegerField(null=True, blank=True)
    ue_cols = models.PositiveIntegerField(null=True, blank=True)
    ue_pattern = models.CharField(max_length=32, null=True, blank=True)
    ue_polarization = models.CharField(max_length=16, null=True, blank=True)

    antenna_config_created_at = models.DateTimeField()
    antenna_config_updated_at = models.DateTimeField()

    class Meta:
        db_table = "ru_antenna_config"
        ordering = ["-antenna_config_updated_at"]
