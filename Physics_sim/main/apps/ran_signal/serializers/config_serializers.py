"""Config API 的序列化器（read / reload / push_scene / reset_to_default）。"""
from rest_framework import serializers


# ─── Read（所有 config 查詢用）────────────────────────────────────

class ConfigReadSerializer(serializers.Serializer):
    scene_id = serializers.CharField()
    loaded_at_ms = serializers.IntegerField()
    gnb_count = serializers.IntegerField()
    ue_count = serializers.IntegerField()
    gnbs = serializers.ListField(child=serializers.DictField())
    ues = serializers.ListField(child=serializers.DictField())
    source = serializers.CharField(required=False, default="default")
    # 若目前是 runtime_push 且有 TTL，告訴 client 什麼時候回預設
    ttl_expires_at_ms = serializers.IntegerField(required=False, allow_null=True, default=None)
    previous_scene_id = serializers.CharField(required=False, allow_null=True, default=None)


class ConfigReloadRequestSerializer(serializers.Serializer):
    # 目前 reload 不需參數；保留空 serializer 以符合鐵則請求鏈格式
    pass


# ─── Push scene (runtime override) ───────────────────────────────

GEOMETRY_SOURCE_TYPES = ("buildings_json",)
OVERRIDE_MODES = ("full", "ran_only", "geometry_only")
ALLOWED_MATERIALS = ("concrete", "glass", "metal", "brick", "wood")


class BuildingWriteSerializer(serializers.Serializer):
    """單一建築 box：位置 + 尺寸 + 材質。"""
    name = serializers.CharField(max_length=128, required=False, allow_blank=True, default="")
    position = serializers.ListField(
        child=serializers.FloatField(), min_length=3, max_length=3,
        help_text="[x, y, z]，公尺，y=0 表示建築底在地面",
    )
    size = serializers.ListField(
        child=serializers.FloatField(min_value=0.01), min_length=3, max_length=3,
        help_text="[width_x, height_y, depth_z]，公尺",
    )
    material = serializers.ChoiceField(
        choices=ALLOWED_MATERIALS, required=False, default="concrete",
        help_text="ITU-R P.2040-3 材質；其他值會 fallback 到 concrete",
    )


class GroundWriteSerializer(serializers.Serializer):
    """地面平板（可選；不傳用預設 250x250）。"""
    position = serializers.ListField(
        child=serializers.FloatField(), min_length=3, max_length=3,
        required=False, default=[0.0, 0.0, 0.0],
    )
    size = serializers.ListField(
        child=serializers.FloatField(min_value=1.0), min_length=2, max_length=2,
        required=False, default=[250.0, 250.0],
    )


class GeometrySourceWriteSerializer(serializers.Serializer):
    """現在唯一支援：buildings_json（建築 box 列表）。"""
    type = serializers.ChoiceField(choices=GEOMETRY_SOURCE_TYPES)
    buildings = BuildingWriteSerializer(many=True)
    ground = GroundWriteSerializer(required=False, allow_null=True)

    def validate_buildings(self, value):
        if len(value) == 0:
            raise serializers.ValidationError("buildings[] 至少要有 1 棟（否則不需要 override geometry）")
        if len(value) > 500:
            raise serializers.ValidationError("buildings[] 上限 500 棟（效能考量）")
        return value


class GnbWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    cell_id = serializers.CharField(max_length=64)
    position = serializers.ListField(
        child=serializers.FloatField(), min_length=3, max_length=3,
    )
    frequency_ghz = serializers.FloatField(min_value=0.4, max_value=100.0)
    power_dbm = serializers.FloatField(min_value=-30.0, max_value=60.0)
    bandwidth_mhz = serializers.FloatField(min_value=1.0, max_value=400.0)


class UeWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    qos_5qi = serializers.IntegerField(required=False, default=9, min_value=1, max_value=255)
    role = serializers.IntegerField(required=False, default=1, min_value=0, max_value=100)


class PushSceneRequestSerializer(serializers.Serializer):
    scene_id = serializers.CharField(max_length=128)
    override_mode = serializers.ChoiceField(
        choices=OVERRIDE_MODES, required=False, default="full",
    )
    geometry_source = GeometrySourceWriteSerializer(required=False, allow_null=True)
    gnbs = GnbWriteSerializer(many=True, required=False, allow_null=True)
    ues = UeWriteSerializer(many=True, required=False, allow_null=True)
    ttl_seconds = serializers.IntegerField(
        required=False, allow_null=True, default=None, min_value=1, max_value=86400,
        help_text="可選；多少秒後自動回預設（安全網）",
    )

    def validate(self, attrs):
        mode = attrs.get("override_mode", "full")
        has_geo = bool(attrs.get("geometry_source"))
        has_gnbs = bool(attrs.get("gnbs"))
        if mode in ("full", "geometry_only") and not has_geo:
            raise serializers.ValidationError(
                f"override_mode={mode} 需要 geometry_source"
            )
        if mode in ("full", "ran_only") and not has_gnbs:
            raise serializers.ValidationError(
                f"override_mode={mode} 需要 gnbs[]"
            )
        return attrs


# ─── Push scene Response ─────────────────────────────────────────

class PushSceneResponseSerializer(serializers.Serializer):
    scene_id = serializers.CharField()
    previous_scene_id = serializers.CharField(allow_null=True)
    loaded_at_ms = serializers.IntegerField()
    override_mode = serializers.CharField()
    source = serializers.CharField()
    ttl_expires_at_ms = serializers.IntegerField(allow_null=True)
    sionna_rebuild_ms = serializers.IntegerField()
    gnb_count = serializers.IntegerField()
    ue_count = serializers.IntegerField()
    geometry_source_type = serializers.CharField(allow_null=True)


# ─── Scene Gateway (frontend init) ───────────────────────────────

class SceneAntennaConfigSerializer(serializers.Serializer):
    """全域天線設定（scene 共用），由 Sionna PlanarArray 套用。"""
    gnb_antenna_pattern = serializers.ChoiceField(
        choices=["tr38901", "iso", "dipole", "hw_dipole", "vh_dipole"],
        required=False, default="tr38901",
    )
    gnb_polarization = serializers.ChoiceField(
        choices=["V", "H", "VH", "cross"], required=False, default="V",
    )
    ue_antenna_pattern = serializers.ChoiceField(
        choices=["tr38901", "iso", "dipole", "hw_dipole", "vh_dipole"],
        required=False, default="dipole",
    )
    ue_polarization = serializers.ChoiceField(
        choices=["V", "H", "VH", "cross"], required=False, default="V",
    )
    gnb_array_rows = serializers.IntegerField(required=False, default=1, min_value=1, max_value=16)
    gnb_array_cols = serializers.IntegerField(required=False, default=1, min_value=1, max_value=16)
    ue_array_rows = serializers.IntegerField(required=False, default=1, min_value=1, max_value=4)
    ue_array_cols = serializers.IntegerField(required=False, default=1, min_value=1, max_value=4)


class SceneGatewayInitSerializer(serializers.Serializer):
    """前端初始化場景 → RAN-sim + Omniverse。

    若未提供 geometry_source 和 gnbs，由 Actor 從 Omniver-RAN DB 自動讀取（DB-only mode）。
    """
    scene_id = serializers.CharField(max_length=128)
    geometry_source = GeometrySourceWriteSerializer(required=False, allow_null=True)
    gnbs = GnbWriteSerializer(many=True, required=False, allow_null=True)
    ues = UeWriteSerializer(many=True, required=False, allow_null=True)
    scene_antenna_config = SceneAntennaConfigSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        # 允許 DB-only 模式：兩個都不提供，由 Actor fallback 填充
        return attrs


class SceneGatewayInitResponseSerializer(serializers.Serializer):
    """回傳 session_uuid + 場景確認。"""
    scene_id = serializers.CharField()
    session_uuid = serializers.CharField()
    gnb_count = serializers.IntegerField()
    ue_count = serializers.IntegerField()
    sionna_rebuild_ms = serializers.IntegerField()
