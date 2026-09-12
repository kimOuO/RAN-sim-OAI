from rest_framework import serializers


class TickStateReadSerializer(serializers.Serializer):
    tick_count = serializers.IntegerField()
    sfn = serializers.IntegerField()
    slot = serializers.IntegerField()
    started_at_ms = serializers.IntegerField(allow_null=True)
    last_tick_ms = serializers.IntegerField()
    is_running = serializers.BooleanField()
    # Phase A — 時間軸三個欄位:wall (set_speed 改的) / sim_dt (固定) / 派生 speed
    wall_tick_ms = serializers.IntegerField(required=False)
    sim_dt_ms = serializers.IntegerField(required=False)
    sim_speed_x = serializers.FloatField(required=False)        # 設定值
    achieved_speed_x = serializers.FloatField(required=False)   # P0a — 實際達成(0=尚未量到)
