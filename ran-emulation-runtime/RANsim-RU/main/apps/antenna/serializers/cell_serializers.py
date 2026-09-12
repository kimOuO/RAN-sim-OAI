"""Cell Read/Write — backend_rule §3-3。

API 接受 list[Cell]；對應 update_cells endpoint。
"""
from rest_framework import serializers

from main.apps.antenna.models.cell import Cell


class _CellPositionSerializer(serializers.Serializer):
    """允許 position 用 [x,y,z] 或 {x,y,z} 兩種格式輸入。"""

    def to_internal_value(self, data):
        if isinstance(data, list) and len(data) == 3:
            return {"x": float(data[0]), "y": float(data[1]), "z": float(data[2])}
        if isinstance(data, dict) and {"x", "y", "z"} <= data.keys():
            return {"x": float(data["x"]), "y": float(data["y"]), "z": float(data["z"])}
        raise serializers.ValidationError("position must be [x,y,z] or {x,y,z}")


class CellWriteSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=128)
    pci = serializers.IntegerField(min_value=0, max_value=1007)
    azimuth_deg = serializers.FloatField(default=0.0)
    position = _CellPositionSerializer()
    frequency_ghz = serializers.FloatField(default=2.5)
    bandwidth_mhz = serializers.FloatField(default=40.0)
    gnb_id = serializers.CharField(max_length=64, default="", allow_blank=True)
    # 預設 23 dBm 對齊 OAI rfsim 實效 link budget(字面 4 + max_rxgain 補)。
    power_dbm = serializers.FloatField(default=23.0)


class CellListWriteSerializer(serializers.Serializer):
    cells = CellWriteSerializer(many=True)


class CellReadSerializer(serializers.ModelSerializer):
    position = serializers.SerializerMethodField()

    class Meta:
        model = Cell
        fields = [
            "cell_uuid",
            "name",
            "pci",
            "azimuth_deg",
            "position",
            "frequency_ghz",
            "bandwidth_mhz",
            "gnb_id",
            "power_dbm",
            "cell_updated_at",
        ]

    def get_position(self, obj: Cell):
        return [obj.position_x, obj.position_y, obj.position_z]
