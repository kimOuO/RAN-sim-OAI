from rest_framework import serializers


class CqiIndicationSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    sinr_db = serializers.FloatField()
    cqi = serializers.IntegerField(min_value=0, max_value=15)
    rank = serializers.IntegerField(min_value=1, max_value=4, default=1)
    pmi = serializers.IntegerField(default=0)


class CrcIndicationSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    harq_pid = serializers.IntegerField(min_value=0, max_value=15)
    success = serializers.BooleanField()
