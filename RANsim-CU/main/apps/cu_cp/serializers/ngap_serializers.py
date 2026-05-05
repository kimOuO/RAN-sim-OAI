"""NGAP serializers — InitialUEMessage / InitialContextSetup."""
from __future__ import annotations

from rest_framework import serializers


class _PduSessionResourceSerializer(serializers.Serializer):
    pdu_session_id = serializers.IntegerField()
    qos_flow_5qi = serializers.ListField(child=serializers.IntegerField(), default=list)
    s_nssai = serializers.CharField(default="01:000000")


class InitialUeMessageWriteSerializer(serializers.Serializer):
    ran_ue_ngap_id = serializers.IntegerField()
    nas_pdu_b64 = serializers.CharField()
    selected_plmn = serializers.CharField(default="00101")


class InitialContextSetupWriteSerializer(serializers.Serializer):
    ran_ue_ngap_id = serializers.IntegerField()
    amf_ue_ngap_id = serializers.IntegerField()
    pdu_session_resources = _PduSessionResourceSerializer(many=True, default=list)


class DownlinkNasTransportWriteSerializer(serializers.Serializer):
    ran_ue_ngap_id = serializers.IntegerField()
    amf_ue_ngap_id = serializers.IntegerField()
    nas_pdu_b64 = serializers.CharField()
