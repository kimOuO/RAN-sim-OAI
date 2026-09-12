"""Django middleware: capture API call metadata into ring buffer."""
from __future__ import annotations
import time
from main.services_logs.ran_message_log import get_ring, make_entry

_SERVICE_LABEL = "RU"


class RanLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/api/v0.1/"):
            return self.get_response(request)
        # P4.3: req body 512 → 4096
        body_text = ""
        try:
            body_text = request.body.decode("utf-8", errors="ignore")[:4096]
        except Exception:
            pass
        t0 = time.perf_counter()
        response = self.get_response(request)
        duration_ms = int((time.perf_counter() - t0) * 1000)
        # P4.3: 抓 response body
        response_text = ""
        try:
            if hasattr(response, "content"):
                response_text = response.content.decode("utf-8", errors="ignore")[:4096]
        except Exception:
            pass
        try:
            entry = make_entry(
                service=_SERVICE_LABEL,
                path=request.path,
                method=request.method,
                status=response.status_code,
                duration_ms=duration_ms,
                body_text=body_text,
                response_text=response_text,
            )
            get_ring().append(entry)
        except Exception:
            pass
        return response
