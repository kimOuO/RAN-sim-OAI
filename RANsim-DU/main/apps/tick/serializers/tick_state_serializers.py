from rest_framework import serializers


class TickStateReadSerializer(serializers.Serializer):
    tick_count = serializers.IntegerField()
    sfn = serializers.IntegerField()
    slot = serializers.IntegerField()
    started_at_ms = serializers.IntegerField(allow_null=True)
    last_tick_ms = serializers.IntegerField()
    is_running = serializers.BooleanField()
