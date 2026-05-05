from rest_framework import serializers


class UeMacStateReadSerializer(serializers.Serializer):
    ue_mac_uuid = serializers.CharField()
    ue_id = serializers.CharField()
    serving_cell_id = serializers.CharField()
    last_mcs_dl = serializers.IntegerField()
    last_mcs_ul = serializers.IntegerField()
    last_cqi = serializers.IntegerField()
    last_sinr_db = serializers.FloatField()
    last_pmi = serializers.IntegerField()
    last_rank = serializers.IntegerField()
    last_allocated_prb_dl = serializers.IntegerField()
    last_allocated_prb_ul = serializers.IntegerField()
    ue_mac_created_at = serializers.IntegerField()
    ue_mac_updated_at = serializers.IntegerField()


class UeMacStateQuerySerializer(serializers.Serializer):
    ue_id = serializers.CharField(required=False, allow_null=True)
