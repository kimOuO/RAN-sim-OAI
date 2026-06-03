from rest_framework import serializers

from main.utils.env_loader import default_served_plmn


class CellStateWriteSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    total_prb = serializers.IntegerField(default=106, min_value=1, max_value=275)
    freq_ghz = serializers.FloatField(default=3.5)
    bw_mhz = serializers.FloatField(default=40.0)
    # 對齊 globalE2node-ID PLMN — caller 沒帶就 env 衍生 (PLMN_MCC + PLMN_MNC).
    served_plmn = serializers.CharField(max_length=16, default=default_served_plmn)
    # 2026-05-16 P2.9: OAI 真實 nr_cellid 可選欄,沒帶 → SHA-1 hash fallback
    nr_cellid = serializers.IntegerField(required=False, allow_null=True, default=None)
    gnb_id = serializers.CharField(max_length=64, default="", allow_blank=True)
    is_active = serializers.BooleanField(default=True)


class CellStateListWriteSerializer(serializers.Serializer):
    cells = CellStateWriteSerializer(many=True)


class CellStateReadSerializer(serializers.Serializer):
    cell_uuid = serializers.CharField()
    cell_id = serializers.CharField()
    pci = serializers.IntegerField()
    total_prb = serializers.IntegerField()
    freq_ghz = serializers.FloatField()
    bw_mhz = serializers.FloatField()
    served_plmn = serializers.CharField()
    nr_cellid = serializers.IntegerField(allow_null=True, default=None)
    gnb_id = serializers.CharField(default="")
    is_active = serializers.BooleanField(default=True)
    cell_created_at = serializers.IntegerField()
    cell_updated_at = serializers.IntegerField()
