"""RuStateReader — Dashboard 查 RU 當前狀態。"""
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.phy_low.models.ru_state import RuState
from main.apps.phy_low.serializers.ru_state_serializers import RuStateReadSerializer
from main.apps.phy_low.services.business.relational_db import SqlDbBusinessService
from main.apps.phy_low.services.common.timestamp_service import TimestampService
from main.apps.phy_low.services.common.uuid_service import UUIDService
from main.apps.phy_low.services.optional.ofdm_descriptor import describe_ofdm
from main.utils.response import success_response


def _ensure_state() -> RuState:
    """單例 RuState — 沒有就用 settings 預設建立。"""
    state = RuState.objects.first()
    if state is not None:
        return state

    now = TimestampService.get_current_timestamp()
    desc = describe_ofdm(settings.RU_NUMEROLOGY)
    return SqlDbBusinessService.upsert_entity(
        RuState,
        lookup={"id": 1},
        defaults={
            "ru_state_uuid": UUIDService.generate_uuid("ru_state", "singleton"),
            "sfn_counter": 0,
            "slot_counter": 0,
            "numerology": settings.RU_NUMEROLOGY,
            "fft_size": desc["fft_size"],
            "cp_type": desc["cp_type"],
            "ru_state_created_at": now,
            "ru_state_updated_at": now,
        },
    )


class RuStateReader:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        state = _ensure_state()
        data = RuStateReadSerializer(state).data
        data["ofdm"] = describe_ofdm(state.numerology)
        return success_response(data, "ru state", 200)
