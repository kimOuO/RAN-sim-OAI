"""PhysicsHealth — Dashboard 透傳 Physics 鏈路狀態。"""
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.physics_client.services.optional.physics_http import health as physics_health
from main.utils.response import success_response


class PhysicsHealth:

    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request):
        return success_response(physics_health(), "physics health probe", 200)
