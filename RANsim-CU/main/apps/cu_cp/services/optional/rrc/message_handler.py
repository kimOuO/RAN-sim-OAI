"""Simplified RRC message encode / decode — base64 JSON, NOT real ASN.1.

OAI ref: openair2/RRC/NR/MESSAGES/asn1_msg.c (do_RRCSetup, do_RRCReconfiguration).
Real OAI uses uper_encode; here we just JSON-serialise dataclass-like dicts so
HTTP transport works. The wire format is opaque to DU/UE — they read it back
with the same handler.
"""
from __future__ import annotations

import base64
import json
from typing import Any


class RrcMessageType:
    SETUP_REQUEST = "RRCSetupRequest"
    SETUP = "RRCSetup"
    SETUP_COMPLETE = "RRCSetupComplete"
    RECONFIGURATION = "RRCReconfiguration"
    RECONFIGURATION_COMPLETE = "RRCReconfigurationComplete"
    RELEASE = "RRCRelease"
    MEASUREMENT_REPORT = "MeasurementReport"
    SECURITY_MODE_COMMAND = "SecurityModeCommand"
    SECURITY_MODE_COMPLETE = "SecurityModeComplete"


class RrcMessageHandler:
    @staticmethod
    def encode(msg_type: str, payload: dict[str, Any] | None = None) -> str:
        body = {"type": msg_type, "payload": payload or {}}
        raw = json.dumps(body, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(raw).decode("ascii")

    @staticmethod
    def decode(b64: str) -> dict[str, Any]:
        try:
            raw = base64.b64decode(b64.encode("ascii"))
            return json.loads(raw.decode("utf-8"))
        except (ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"corrupt RRC b64 message: {exc}") from exc

    # Convenience builders -----------------------------------------------------

    @staticmethod
    def encode_rrc_setup(transaction_id: int, srbs: list[int] | None = None) -> str:
        return RrcMessageHandler.encode(
            RrcMessageType.SETUP,
            {"transaction_id": transaction_id, "srb_to_add": srbs or [1]},
        )

    @staticmethod
    def encode_rrc_reconfiguration(
        transaction_id: int, drbs: list[dict[str, Any]] | None = None,
    ) -> str:
        return RrcMessageHandler.encode(
            RrcMessageType.RECONFIGURATION,
            {"transaction_id": transaction_id, "drb_to_add_mod": drbs or []},
        )

    @staticmethod
    def encode_rrc_release(cause: str = "normal") -> str:
        return RrcMessageHandler.encode(RrcMessageType.RELEASE, {"cause": cause})
