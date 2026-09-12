"""E1AP Router (CU-UP side, split-mode entry)."""
from __future__ import annotations

import json

from django.db import transaction
from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_up.serializers.e1ap_serializers import BearerContextSetupWriteSerializer
from main.apps.cu_up.services.optional.e1ap.e1ap_handler import E1apHandler
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response

logger = get_logger(__name__)


class E1ApRouterActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    @transaction.atomic
    def bearer_context_setup(request: HttpRequest):
        try:
            body = json.loads(request.body)
        except json.JSONDecodeError as exc:
            return error_response("invalid JSON", str(exc), status=400)

        serializer = BearerContextSetupWriteSerializer(data=body)
        if not serializer.is_valid():
            return error_response("validation failed", serializer.errors, status=400)

        result = E1apHandler.bearer_context_setup(serializer.validated_data)
        return success_response(result, "bearer context setup")
