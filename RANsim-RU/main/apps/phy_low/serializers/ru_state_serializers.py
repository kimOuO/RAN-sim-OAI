from rest_framework import serializers

from main.apps.phy_low.models.ru_state import RuState


class RuStateReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = RuState
        fields = [
            "ru_state_uuid",
            "sfn_counter",
            "slot_counter",
            "numerology",
            "fft_size",
            "cp_type",
            "last_tick_at",
            "ru_state_updated_at",
        ]
