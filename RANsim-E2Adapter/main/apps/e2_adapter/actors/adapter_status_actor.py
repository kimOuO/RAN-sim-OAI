"""Adapter status read actor.

URL: POST /api/v0.1/E2Adapter/Status/AdapterStatusReader/read

Combines snapshots from:
  - models.connection_state (SCTP link + E2 Setup state)
  - services.optional.codec.asn1_loader (schemas loaded?)
  - services.optional.sim_bridge.sim_http_client (last sim call)
  - services.optional.sctp_link.sctp_loop (configured target)
"""
from __future__ import annotations

from django.http import HttpRequest
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from main.apps.e2_adapter.models.connection_state import get_registry
from main.apps.e2_adapter.serializers.adapter_status_serializers import AdapterStatusReadSerializer
from main.apps.e2_adapter.services.business.memory_state_operations import MemoryStateBusinessService
from main.apps.e2_adapter.services.optional.codec import e2_subscription_codec, e2ap_codec, e2sm_kpm_codec
from main.apps.e2_adapter.services.optional.codec.asn1_loader import schemas_status
from main.apps.e2_adapter.services.optional.sctp_link.sctp_loop import is_enabled, link_target
from main.apps.e2_adapter.services.optional.sim_bridge.sim_http_client import get_state_snapshot as bridge_snapshot
from main.utils.logger import get_logger
from main.utils.response import error_response, success_response


def _run_codec_selftests() -> dict:
    """Run all 3 codec round-trip tests; aggregate result for /Status/read."""
    out = {
        "e2_setup_request_ok": False,
        "e2_setup_request_size": 0,
        "kpm_indication_ok": False,
        "kpm_indication_size": 0,
        "subscription_decode_ok": False,
        "subscription_decoded_metrics": [],
        "last_error": "",
    }
    try:
        r1 = e2ap_codec.selftest_e2_setup_round_trip()
        out["e2_setup_request_ok"] = bool(r1.get("encoded_size", 0) > 0)
        out["e2_setup_request_size"] = int(r1.get("encoded_size", 0))
    except Exception as exc:
        out["last_error"] = f"e2_setup: {exc!r}"
        return out
    try:
        r2 = e2sm_kpm_codec.selftest_kpm_indication_round_trip()
        out["kpm_indication_ok"] = bool(r2.get("encoded_message_size", 0) > 0)
        out["kpm_indication_size"] = int(r2.get("encoded_message_size", 0))
    except Exception as exc:
        out["last_error"] = f"kpm_indication: {exc!r}"
        return out
    try:
        r3 = e2_subscription_codec.selftest_subscription_decode_round_trip()
        sim_payload = r3.get("decoded_sim_payload", {})
        out["subscription_decode_ok"] = bool(r3.get("encoded_size", 0) > 0)
        out["subscription_decoded_metrics"] = sim_payload.get(
            "action_definition", {}
        ).get("metrics", [])
    except Exception as exc:
        out["last_error"] = f"subscription: {exc!r}"
        return out
    return out

logger = get_logger(__name__)


class AdapterStatusActor:
    @staticmethod
    @csrf_exempt
    @require_http_methods(["POST"])
    def read(request: HttpRequest):
        try:
            # Step 1: snapshot all sources（Actor 編排，不直接從 model 拿）
            registry = get_registry()
            conn = MemoryStateBusinessService.read_state(registry)

            host, port = link_target()
            payload = {
                "sctp_link": {
                    "enabled": is_enabled(),
                    "target_host": host,
                    "target_port": port,
                    "connected": conn.sctp_connected,
                    "last_connect_at_ms": conn.last_connect_at_ms,
                    "last_disconnect_at_ms": conn.last_disconnect_at_ms,
                    "last_error": conn.last_error,
                    "pdu_sent_count": conn.pdu_sent_count,
                    "pdu_recv_count": conn.pdu_recv_count,
                },
                "e2_setup": {
                    "completed": conn.e2_setup_completed,
                    "accepted_ran_function_ids": conn.accepted_ran_function_ids,
                    "rejected_ran_function_ids": conn.rejected_ran_function_ids,
                },
                "schemas": schemas_status(),
                "sim_bridge": bridge_snapshot(),
                "codec_selftest": _run_codec_selftests(),
            }

            # Step 2: format response
            output = AdapterStatusReadSerializer(payload).data
            return success_response(output)
        except Exception as exc:  # pragma: no cover
            logger.exception("Status/read failed")
            return error_response("internal error", str(exc), status=500)
