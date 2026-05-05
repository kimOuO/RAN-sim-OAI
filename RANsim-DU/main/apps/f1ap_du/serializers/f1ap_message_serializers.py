"""對應 ran_sim_protocol.f1ap dataclass 的 DRF serializer。"""
from rest_framework import serializers


class _DrbConfigSerializer(serializers.Serializer):
    drb_id = serializers.IntegerField()
    qos_5qi = serializers.IntegerField()
    rlc_mode = serializers.ChoiceField(choices=["AM", "UM", "TM"], default="AM")


class UeContextSetupSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    drbs = _DrbConfigSerializer(many=True, required=False, default=[])
    rrc_message_b64 = serializers.CharField(required=False, allow_blank=True, default="")


class UeContextReleaseSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    cause = serializers.CharField(default="normal")


class DlRrcMessageTransferSerializer(serializers.Serializer):
    ue_id = serializers.CharField(max_length=64)
    rrc_msg_b64 = serializers.CharField()


class F1SetupResponseSerializer(serializers.Serializer):
    transaction_id = serializers.IntegerField()
    accepted = serializers.BooleanField(default=True)


class UlRrcInjectSerializer(serializers.Serializer):
    """UE simulator → DU 注入 UL RRC PDU(b64 編碼)。"""
    ue_id = serializers.CharField(max_length=64)
    rrc_msg_b64 = serializers.CharField(min_length=1)
    is_initial = serializers.BooleanField(required=False, default=False)
