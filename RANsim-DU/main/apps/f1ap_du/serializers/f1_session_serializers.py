from rest_framework import serializers


class F1SessionReadSerializer(serializers.Serializer):
    f1_uuid = serializers.CharField()
    gnb_du_id = serializers.IntegerField()
    cu_host = serializers.CharField()
    cu_port = serializers.IntegerField()
    transaction_id = serializers.IntegerField()
    state = serializers.CharField()
    last_setup_at = serializers.IntegerField(allow_null=True)
    f1_session_updated_at = serializers.IntegerField()
