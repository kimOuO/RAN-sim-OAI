"""antenna_preset — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class AntennaPreset(models.Model):
    id = models.AutoField(primary_key=True)
    antenna_preset_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    name = models.CharField(max_length=128, unique=True)
    source = models.CharField(max_length=16, default='3gpp')
    pattern = models.CharField(max_length=16, default='tr38901')
    rows = models.IntegerField(default=1)
    cols = models.IntegerField(default=1)
    polarization = models.CharField(max_length=8, default='V')
    v_spacing = models.FloatField(default=0.5)
    h_spacing = models.FloatField(default=0.5)
    polarization_model = models.CharField(max_length=16, default='tr38901_2')
    max_gain_dbi = models.FloatField(default=8.0)

    # ── 三層天線模型(2026-09-16,見 new_plan/ru_antenna_mimo_plan.md)────────────
    # 舊欄位 rows/cols 語意不變 = **單一面板的元件排列**(TR 38.901 §7.3 的 M / N),
    # 以下新增的是「元件 → TXRU → CSI-RS 埠」兩層映射,以前被壓成 rows×cols 一個數字。
    #
    #   元件層 (Mg,Ng,M,N,P)  ──virtualization──▶  TRX 層 trx_count  ──埠映射──▶  埠層 csi_ports (N1,N2)
    #   TR 38.901 §7.3            TR 38.901 式 (7.3-1)                    TS 38.214 §5.2.2.2.1
    panels_mg = models.IntegerField(default=1)      # Mg:面板列數
    panels_ng = models.IntegerField(default=1)      # Ng:面板行數
    panel_v_spacing = models.FloatField(default=0.0)   # dg,V(λ);單面板時 0
    panel_h_spacing = models.FloatField(default=0.0)   # dg,H(λ)
    # 每個 TXRU 垂直帶幾片同極化元件(sub-array);1 = 一片元件一個 TXRU
    trx_v_group = models.IntegerField(default=1)
    # TXRU 總數;0 = 由 panels × rows/trx_v_group × cols × 極化數自動推算
    trx_count = models.IntegerField(default=0)
    # virtualization 的電子下傾(度,正 = 往下);權重用 TR 38.901 式 (7.3-1)
    electrical_tilt_deg = models.FloatField(default=0.0)
    # 對外 CSI-RS 埠數(TS 38.211 §7.4.1.5:1/2/4/8/12/16/24/32);0 = 等於 trx_count
    csi_ports = models.IntegerField(default=0)
    # TS 38.214 Type I 單面板的埠排列;埠數 = 2·N1·N2(雙極化)。0 = 自動推
    port_n1 = models.IntegerField(default=0)
    port_n2 = models.IntegerField(default=0)
    # O-RAN WG4 CUS-plane:'A' = precoding 在 O-DU;'B' = O-RU 自己做 beamforming
    ru_category = models.CharField(max_length=1, default='A')
    # Cat B 的 beamforming 方法:predefined / attribute / weight / channel_info
    bf_method = models.CharField(max_length=16, blank=True, default='')
    # GoB 大小(Cat B predefined-beam:方位向 × 仰角向的波束數);0 = 不產生 GoB
    gob_az_beams = models.IntegerField(default=0)
    gob_el_beams = models.IntegerField(default=0)

    notes = models.TextField(blank=True, default='')
    antenna_preset_created_at = models.DateTimeField()
    antenna_preset_updated_at = models.DateTimeField()

    class Meta:
        app_label = "equipment_preset"
        db_table = "preset_catalog_antenna_preset"
        ordering = ("id",)
