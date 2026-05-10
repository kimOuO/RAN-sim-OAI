from rest_framework import serializers

from main.utils.env_loader import default_served_plmn


class CellStateWriteSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    total_prb = serializers.IntegerField(default=273, min_value=1, max_value=275)
    freq_ghz = serializers.FloatField(default=3.5)
    bw_mhz = serializers.FloatField(default=100.0)
    # 對齊 globalE2node-ID PLMN — caller 沒帶就 env 衍生 (PLMN_MCC + PLMN_MNC).
    served_plmn = serializers.CharField(max_length=16, default=default_served_plmn)
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
    gnb_id = serializers.CharField(default="")
    is_active = serializers.BooleanField(default=True)
    cell_created_at = serializers.IntegerField()
    cell_updated_at = serializers.IntegerField()
