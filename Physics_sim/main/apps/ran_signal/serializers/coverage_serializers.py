"""Coverage Map API Serializer — 對齊外部平台 schema。

外部平台（前端視覺化 / 另一個 Django backend）期望格式：
  - `ts` : ISO 8601 字串（非 timestamp_ms）
  - `gnb_name` : 建築名稱（非 pci）
  - `rsrp_dbm` : 2D List[List[float | None]]，外層 = z 軸（北到南），內層 = x 軸（西到東）
  - null = 建築完全遮蔽 / RSRP < 閾值
"""
from rest_framework import serializers


# ─── Write ───────────────────────────────────────────────────

class GridSpecWriteSerializer(serializers.Serializer):
    x_range = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2,
        help_text="[x_min, x_max] 公尺",
    )
    x_step = serializers.FloatField(min_value=0.5, max_value=50.0)
    z_range = serializers.ListField(
        child=serializers.FloatField(), min_length=2, max_length=2,
        help_text="[z_min, z_max] 公尺",
    )
    z_step = serializers.FloatField(min_value=0.5, max_value=50.0)
    sample_height_m = serializers.FloatField(
        required=False, default=1.5, min_value=0.1, max_value=50.0,
        help_text="UE 高度 (公尺)",
    )

    def validate(self, attrs):
        x_lo, x_hi = attrs["x_range"]
        z_lo, z_hi = attrs["z_range"]
        if x_hi <= x_lo:
            raise serializers.ValidationError("x_range 順序錯: x_max <= x_min")
        if z_hi <= z_lo:
            raise serializers.ValidationError("z_range 順序錯: z_max <= z_min")

        # 粗估格數上限，避免 VRAM OOM
        n_cells = ((x_hi - x_lo) / attrs["x_step"] + 1) * ((z_hi - z_lo) / attrs["z_step"] + 1)
        if n_cells > 10000:
            raise serializers.ValidationError(
                f"grid 太大: {int(n_cells)} cells；上限 10000 (建議 step 加大或 range 縮小)"
            )
        return attrs


class CoverageMapRequestSerializer(serializers.Serializer):
    scene_id = serializers.CharField(max_length=128)
    grid = GridSpecWriteSerializer()
    include_sinr = serializers.BooleanField(required=False, default=True)
    max_depth = serializers.IntegerField(
        required=False, default=3, min_value=1, max_value=5,
        help_text="光追 bounce 次數；coverage map 建議 <=3 以免 VRAM 爆",
    )
    null_threshold_dbm = serializers.FloatField(
        required=False, default=-120.0, min_value=-200.0, max_value=-30.0,
        help_text="RSRP 低於此值改回 null（視為遮蔽 / 無訊號）",
    )


# ─── Read ───────────────────────────────────────────────────
# 注意：這部分完全對齊外部平台 spec，`data` 區塊形狀不可加包裝。
# Django wrapper (success/message/data) 是 ranp-sim 側規範，外部 parse .data 取資料。

class CoverageGridReadSerializer(serializers.Serializer):
    x_range = serializers.ListField(child=serializers.FloatField())
    x_step = serializers.FloatField()
    z_range = serializers.ListField(child=serializers.FloatField())
    z_step = serializers.FloatField()
    sample_height_m = serializers.FloatField()
    n_rows = serializers.IntegerField()   # = (z_max - z_min) / z_step + 1
    n_cols = serializers.IntegerField()   # = (x_max - x_min) / x_step + 1


class CoverageGnbReadSerializer(serializers.Serializer):
    gnb_name = serializers.CharField()
    pci = serializers.IntegerField()
    cell_id = serializers.CharField()
    frequency_ghz = serializers.FloatField()
    power_dbm = serializers.FloatField()
    # 2D list of float 或 None；外層 z，內層 x
    rsrp_dbm = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(allow_null=True),
        )
    )
    sinr_db = serializers.ListField(
        child=serializers.ListField(
            child=serializers.FloatField(allow_null=True),
        ),
        required=False,
    )


class CoverageMapResponseSerializer(serializers.Serializer):
    scene_id = serializers.CharField()
    ts = serializers.CharField(help_text="ISO 8601 UTC 時間戳")
    compute_ms = serializers.IntegerField()
    grid = CoverageGridReadSerializer()
    gnbs = CoverageGnbReadSerializer(many=True)
