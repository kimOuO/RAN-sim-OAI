"""E2 full KPM read endpoint — 欄位架構對齊 docs/E2_data_example.md 的完整 snapshot。"""
from __future__ import annotations

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.cu_cp.services.optional.e2.full_kpm_reporter import FullKpmReporter
from main.utils.response import success_response


class E2FullReporterActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        return success_response(FullKpmReporter.collect(), "OK")
