from rest_framework import serializers


class CellStateWriteSerializer(serializers.Serializer):
    cell_id = serializers.CharField(max_length=64)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    total_prb = serializers.IntegerField(default=273, min_value=1, max_value=275)
    freq_ghz = serializers.FloatField(default=3.5)
    bw_mhz = serializers.FloatField(default=100.0)
    served_plmn = serializers.CharField(max_length=16, default="00101")


class CellStateReadSerializer(serializers.Serializer):
    cell_uuid = serializers.CharField()
    cell_id = serializers.CharField()
    pci = serializers.IntegerField()
    total_prb = serializers.IntegerField()
    freq_ghz = serializers.FloatField()
    bw_mhz = serializers.FloatField()
    served_plmn = serializers.CharField()
    cell_created_at = serializers.IntegerField()
    cell_updated_at = serializers.IntegerField()
