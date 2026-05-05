"""dataclass ↔ dict 轉換 — 直接用 ran_sim_protocol 的 to_dict / from_dict。"""
from __future__ import annotations

from typing import Any

from ran_sim_protocol import from_dict, to_dict
from ran_sim_protocol.f1ap import (
    DlRrcMessageTransfer,
    F1Setup,
    F1SetupResponse,
    GnbDuMeasurementReport,
    UeContextRelease,
    UeContextSetup,
    UeContextSetupResponse,
    UlRrcMessageTransfer,
)


def encode_f1_setup(msg: F1Setup) -> dict[str, Any]:
    return to_dict(msg)


def decode_f1_setup_response(data: dict[str, Any]) -> F1SetupResponse:
    return from_dict(F1SetupResponse, data)


def decode_dl_rrc(data: dict[str, Any]) -> DlRrcMessageTransfer:
    return from_dict(DlRrcMessageTransfer, data)


def decode_ue_context_setup(data: dict[str, Any]) -> UeContextSetup:
    return from_dict(UeContextSetup, data)


def decode_ue_context_release(data: dict[str, Any]) -> UeContextRelease:
    return from_dict(UeContextRelease, data)


def encode_ul_rrc(msg: UlRrcMessageTransfer) -> dict[str, Any]:
    return to_dict(msg)


def encode_measurement_report(msg: GnbDuMeasurementReport) -> dict[str, Any]:
    return to_dict(msg)


def encode_ue_context_setup_response(msg: UeContextSetupResponse) -> dict[str, Any]:
    return to_dict(msg)
