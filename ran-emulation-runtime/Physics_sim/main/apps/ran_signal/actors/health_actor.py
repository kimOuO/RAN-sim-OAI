"""HealthActor — 給 docker healthcheck 和外部監控。"""
from rest_framework.decorators import api_view

from main.apps.ran_signal.services.business.sionna_operations import SionnaBusinessService
from main.utils.response import success_response


class HealthActor:
    @staticmethod
    @api_view(["POST"])  # 鐵則 7-2
    def read(request):
        status = SionnaBusinessService.health_status()
        return success_response(status, "OK")
