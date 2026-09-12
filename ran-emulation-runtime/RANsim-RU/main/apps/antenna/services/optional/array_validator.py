"""Antenna 配置白名單 — 與 ran_sim_protocol.common.AntennaArrayConfig 對齊。

Serializer 的 ChoiceField 會做主要驗證；此檔案作為 service 入口，方便非-HTTP 場景查詢。
"""
from main.apps.antenna.models.antenna_config import PATTERN_CHOICES, POLARIZATION_CHOICES


class ArrayValidator:
    POLARIZATIONS = frozenset(v for v, _ in POLARIZATION_CHOICES)
    PATTERNS = frozenset(v for v, _ in PATTERN_CHOICES)

    @classmethod
    def validate_polarization(cls, value: str) -> bool:
        return value in cls.POLARIZATIONS

    @classmethod
    def validate_pattern(cls, value: str) -> bool:
        return value in cls.PATTERNS
