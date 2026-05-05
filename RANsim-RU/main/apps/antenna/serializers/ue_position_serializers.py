"""UePosition Read/Write — backend_rule §3-3。"""
from rest_framework import serializers

from main.apps.antenna.models.ue_position import UePosition
from main.apps.antenna.serializers.cell_serializers import _CellPositionSerializer


class UePositionWriteSerializer(serializers.Serializer):
    id = serializers.CharField(max_length=128)
    position = _CellPositionSerializer()
    velocity = _CellPositionSerializer(required=False)


class UePositionListWriteSerializer(serializers.Serializer):
    ues = UePositionWriteSerializer(many=True)


class UePositionReadSerializer(serializers.ModelSerializer):
    position = serializers.SerializerMethodField()
    velocity = serializers.SerializerMethodField()

    class Meta:
        model = UePosition
        fields = [
            "ue_position_uuid",
            "ue_id",
            "position",
            "velocity",
            "ue_position_updated_at",
        ]

    def get_position(self, obj):
        return [obj.position_x, obj.position_y, obj.position_z]

    def get_velocity(self, obj):
        return [obj.velocity_x, obj.velocity_y, obj.velocity_z]
