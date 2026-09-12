from rest_framework import serializers


class HarqProcessReadSerializer(serializers.Serializer):
    harq_uuid = serializers.CharField()
    f_ue_mac_uuid = serializers.CharField()
    harq_pid = serializers.IntegerField()
    direction = serializers.CharField()
    state = serializers.CharField()
    retx_count = serializers.IntegerField()
    last_tbs_bytes = serializers.IntegerField()
    harq_updated_at = serializers.IntegerField()


class HarqProcessQuerySerializer(serializers.Serializer):
    ue_id = serializers.CharField(required=False, allow_null=True)
