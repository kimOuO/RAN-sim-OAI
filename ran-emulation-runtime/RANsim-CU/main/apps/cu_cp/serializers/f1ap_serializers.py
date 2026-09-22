"""Serializers mirroring ran_sim_protocol.f1ap dataclass shape."""
from __future__ import annotations

from rest_framework import serializers

from main.utils.env_loader import default_served_plmn


class _CellConfigSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    frequency_ghz = serializers.FloatField()
    bandwidth_mhz = serializers.FloatField()
    # 對齊 globalE2node-ID PLMN — caller 沒帶就 env 衍生.
    served_plmn = serializers.CharField(max_length=16, default=default_served_plmn)
    # 2026-05-16 P2.9: F1 Setup 帶上 OAI 真實 nr_cellid;沒帶 → CU 走 SHA-1 hash fallback
    nr_cellid = serializers.IntegerField(required=False, allow_null=True, default=None)
    gnb_id = serializers.CharField(max_length=64, default="", allow_blank=True)
    # 2026-09-22: 每 cell 發射功率 (dBm) — 未宣告的話 DRF 會靜默丟掉,PEE.AvgPower 就永遠是 null。
    tx_power_dbm = serializers.FloatField(required=False, allow_null=True, default=None)


class _DrbConfigSerializer(serializers.Serializer):
    drb_id = serializers.IntegerField(min_value=1, max_value=32)
    qos_5qi = serializers.IntegerField(min_value=1, max_value=254)
    rlc_mode = serializers.CharField(default="AM")


class _NeighborMeasSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    rsrp_dbm = serializers.FloatField()
    rsrq_db = serializers.FloatField()
    # UE 真實看得到的兩個識別。DRF 會靜默丟掉沒宣告的欄位 ——
    # 2026-09-22 就是漏了這行,DU 有送、協定有欄位,卻整批存成 null。
    pci = serializers.IntegerField(required=False, allow_null=True, default=None)
    arfcn = serializers.IntegerField(required=False, allow_null=True, default=None)


class F1SetupWriteSerializer(serializers.Serializer):
    gnb_du_id = serializers.IntegerField(min_value=0)
    served_cells = _CellConfigSerializer(many=True)


class UlRrcMessageWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    rrc_msg_b64 = serializers.CharField()


class MeasurementReportWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    # null = 該視窗無量測樣本(見 f1ap.GnbDuMeasurementReport)
    rsrp_dbm = serializers.FloatField(required=False, allow_null=True, default=None)
    sinr_db = serializers.FloatField(required=False, allow_null=True, default=None)
    throughput_dl_mbps = serializers.FloatField()
    throughput_ul_mbps = serializers.FloatField(default=0.0)
    mcs_dl = serializers.IntegerField(default=0)
    rb_width_dl = serializers.IntegerField(default=0)
    mimo_rank = serializers.IntegerField(default=1)
    # 對齊 3GPP TS 28.552 — DU 累計 PDCP SDU bytes per window
    pdcp_sdu_volume_dl = serializers.IntegerField(default=0)
    pdcp_sdu_volume_ul = serializers.IntegerField(default=0)
    rlc_sdu_delay_dl_ms = serializers.FloatField(default=0.0)
    qos_5qi = serializers.IntegerField(default=9)   # 2026-08-12(D):per-5QI 分桶
    neighbor_cells = _NeighborMeasSerializer(many=True, default=list)
    # P6 / P5-4 上行與多層(舊 DU 不帶)
    mcs_ul = serializers.IntegerField(default=0)
    rb_width_ul = serializers.IntegerField(default=0)
    ul_sinr_db = serializers.FloatField(required=False, allow_null=True, default=None)
    sinr_layers_db = serializers.ListField(child=serializers.FloatField(), default=list)
    beam_id = serializers.IntegerField(required=False, allow_null=True, default=None)
    # 2026-09-21:PM 視窗序號(舊 DU 不帶 → None,歸檔退回依秒分組)
    window_seq = serializers.IntegerField(required=False, allow_null=True, default=None)
    # 2026-09-22:劇本時鐘。serializer 沒宣告的欄位 DRF 會靜默丟掉 ——
    # DU 有送、協定有欄位,卻因為漏了這一行而整批存成 null(實測 23189 筆全空)。
    scene_sim_ms = serializers.IntegerField(required=False, allow_null=True, default=None)
    # 服務 cell 的 RSRQ(TS 38.215)。舊 DU 不帶 → None。
    rsrq_db = serializers.FloatField(required=False, allow_null=True, default=None)
    cqi = serializers.FloatField(required=False, allow_null=True, default=None)
    beam_rsrp_top = serializers.ListField(required=False, default=list)


class DuRegistryReadSerializer(serializers.Serializer):
    gnb_du_id = serializers.IntegerField()
    name = serializers.CharField()
    served_cells_json = serializers.JSONField()
    registered_at = serializers.DateTimeField()
