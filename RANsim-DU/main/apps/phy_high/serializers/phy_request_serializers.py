from rest_framework import serializers


class ThroughputRequestSerializer(serializers.Serializer):
    mcs = serializers.IntegerField(min_value=0, max_value=27)
    n_rb = serializers.IntegerField(min_value=1, max_value=275)
    layers = serializers.IntegerField(default=1, min_value=1, max_value=4)


class BlerRequestSerializer(serializers.Serializer):
    sinr_db = serializers.FloatField()
    mcs = serializers.IntegerField(min_value=0, max_value=27)


class PrecodingRequestSerializer(serializers.Serializer):
    ue_id = serializers.CharField()
    pmi = serializers.IntegerField(min_value=0)
    rank = serializers.IntegerField(min_value=1, max_value=4, default=1)
