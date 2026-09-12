"""FAPI dataclass codec(直接用 ran_sim_protocol)。"""
from __future__ import annotations

from typing import Any

from ran_sim_protocol import from_dict, to_dict
from ran_sim_protocol.fapi import (
    CqiIndication,
    CrcIndication,
    DlTtiRequest,
    UlTtiRequest,
)


def encode_dl_tti(msg: DlTtiRequest) -> dict[str, Any]:
    return to_dict(msg)


def encode_ul_tti(msg: UlTtiRequest) -> dict[str, Any]:
    return to_dict(msg)


def decode_cqi(data: dict[str, Any]) -> CqiIndication:
    return from_dict(CqiIndication, data)


def decode_crc(data: dict[str, Any]) -> CrcIndication:
    return from_dict(CrcIndication, data)
