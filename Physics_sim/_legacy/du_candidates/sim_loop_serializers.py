"""SimLoop API 的序列化器（setup / start / stop / status）。"""
from rest_framework import serializers


# ─── SimLoop Setup ───────────────────────────────────────────

class UeTrajectorySerializer(serializers.Serializer):
    """單個 UE 的軌跡配置。"""
    name = serializers.CharField(max_length=128)
    waypoints = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(), min_length=3, max_length=3
        ),
        min_length=2,
        help_text="至少 2 個 waypoint [x,y,z]",
    )
    speed_mps = serializers.FloatField(min_value=0, max_value=100.0, default=1.0)
    loop = serializers.BooleanField(required=False, default=True)


class SimLoopSetupRequestSerializer(serializers.Serializer):
    """設定 UE 軌跡。"""
    ues = UeTrajectorySerializer(many=True, required=False, allow_null=True, default=[])


class SimLoopSetupResponseSerializer(serializers.Serializer):
    """設定回應。"""
    ues_configured = serializers.IntegerField()
    total_duration_ms = serializers.FloatField()


# ─── SimLoop Start ───────────────────────────────────────────

class SimLoopStartResponseSerializer(serializers.Serializer):
    """啟動回應。"""
    status = serializers.CharField()
    session_uuid = serializers.CharField(required=False, allow_null=True)
    tick_count = serializers.IntegerField(required=False, default=0)
    message = serializers.CharField(required=False, allow_null=True)


# ─── SimLoop Stop ────────────────────────────────────────────

class SimLoopStopResponseSerializer(serializers.Serializer):
    """停止回應。"""
    status = serializers.CharField()
    session_uuid = serializers.CharField(required=False, allow_null=True)
    tick_count = serializers.IntegerField(required=False, default=0)
    elapsed_ms = serializers.FloatField(required=False, default=0)


# ─── SimLoop Status ──────────────────────────────────────────

class SimLoopStatusResponseSerializer(serializers.Serializer):
    """狀態查詢回應。"""
    is_running = serializers.BooleanField()
    session_uuid = serializers.CharField(required=False, allow_null=True)
    scene_id = serializers.CharField(required=False, allow_null=True)
    ue_count = serializers.IntegerField()
    tick_count = serializers.IntegerField()
    started_at_ms = serializers.IntegerField(required=False, allow_null=True)
    elapsed_ms = serializers.FloatField(required=False, default=0)
