"""GlobalE2node-ID read response serializer."""
from __future__ import annotations

from rest_framework import serializers


class _PlmnIdSerializer(serializers.Serializer):
    mcc = serializers.CharField()
    mnc = serializers.CharField()
    mnc_digit_count = serializers.IntegerField()   # 2 or 3，給 adapter 編 PLMN BCD 用


class _GnbIdSerializer(serializers.Serializer):
    value_hex = serializers.CharField()
    value_int = serializers.IntegerField()
    bit_length = serializers.IntegerField()


class _GlobalE2NodeIdSerializer(serializers.Serializer):
    plmn_id = _PlmnIdSerializer()
    gnb_id = _GnbIdSerializer()


class _RanFunctionSerializer(serializers.Serializer):
    ran_function_id = serializers.IntegerField()
    ran_function_oid = serializers.CharField()
    ran_function_revision = serializers.IntegerField()
    service_model = serializers.CharField()
    version = serializers.CharField()


class _SNssaiSerializer(serializers.Serializer):
    sst = serializers.IntegerField()
    sd = serializers.CharField(required=False, allow_blank=True)


class _ComponentCellSerializer(serializers.Serializer):
    cell_id = serializers.CharField()
    nr_cell_id = serializers.CharField()
    # 2026-05-16 P2.6: 露出 explicit nr_cellid (OAI 真實 36-bit 整數);null → e2adapter SHA-1 hash fallback
    nr_cellid = serializers.IntegerField(allow_null=True, required=False, default=None)
    pci = serializers.IntegerField()
    tac = serializers.IntegerField()
    served_plmn = serializers.CharField()
    # 2026-05-16 P3.3: S-NSSAI 空殼接口
    s_nssai = _SNssaiSerializer(required=False)
    is_active = serializers.BooleanField()


class _ComponentSerializer(serializers.Serializer):
    interface_type = serializers.CharField()      # "f1" | "ng" | "e1"
    gnb_du_id = serializers.IntegerField(required=False)
    du_name = serializers.CharField(required=False, allow_blank=True)
    cells = _ComponentCellSerializer(many=True)


class E2NodeIdReadSerializer(serializers.Serializer):
    """Read response — 給 e2-adapter 在 E2 Setup Request 階段拿。"""

    global_e2_node_id = _GlobalE2NodeIdSerializer()
    ran_functions = _RanFunctionSerializer(many=True)
    components = _ComponentSerializer(many=True, required=False)
    expected_ran_name = serializers.CharField()
