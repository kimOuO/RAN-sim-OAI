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
    gnb_id = serializers.CharField(max_length=64, default="", allow_blank=True)


class _DrbConfigSerializer(serializers.Serializer):
    drb_id = serializers.IntegerField(min_value=1, max_value=32)
    qos_5qi = serializers.IntegerField(min_value=1, max_value=254)
    rlc_mode = serializers.CharField(default="AM")


class _NeighborMeasSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    rsrp_dbm = serializers.FloatField()
    rsrq_db = serializers.FloatField()


class F1SetupWriteSerializer(serializers.Serializer):
    gnb_du_id = serializers.IntegerField(min_value=0)
    served_cells = _CellConfigSerializer(many=True)


class UlRrcMessageWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    rrc_msg_b64 = serializers.CharField()


class MeasurementReportWriteSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    rsrp_dbm = serializers.FloatField()
    sinr_db = serializers.FloatField()
    throughput_dl_mbps = serializers.FloatField()
    throughput_ul_mbps = serializers.FloatField(default=0.0)
    mcs_dl = serializers.IntegerField(default=0)
    rb_width_dl = serializers.IntegerField(default=0)
    mimo_rank = serializers.IntegerField(default=1)
    # 對齊 3GPP TS 28.552 — DU 累計 PDCP SDU bytes per window
    pdcp_sdu_volume_dl = serializers.IntegerField(default=0)
    pdcp_sdu_volume_ul = serializers.IntegerField(default=0)
    rlc_sdu_delay_dl_ms = serializers.FloatField(default=0.0)
    neighbor_cells = _NeighborMeasSerializer(many=True, default=list)


class DuRegistryReadSerializer(serializers.Serializer):
    gnb_du_id = serializers.IntegerField()
    name = serializers.CharField()
    served_cells_json = serializers.JSONField()
    registered_at = serializers.DateTimeField()
