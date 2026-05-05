"""E2 KPM read endpoint — xApp / RIC consumes this."""
from __future__ import annotations

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.services.optional.e2.kpm_reporter import KpmReporter
from main.utils.response import success_response


class E2KpmReporterActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        return success_response(KpmReporter.collect(), "kpm snapshot")
