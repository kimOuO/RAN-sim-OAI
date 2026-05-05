"""依 env SIM_SCHEDULER 取得 scheduler instance(singleton)。"""
from __future__ import annotations

from main.apps.mac.services.optional.scheduler.max_throughput import MaxThroughputScheduler
from main.apps.mac.services.optional.scheduler.pf_scheduler import PfScheduler
from main.apps.mac.services.optional.scheduler.round_robin import RoundRobinScheduler
from main.utils.env_loader import get_str

_singleton = None


def get_scheduler():
    global _singleton
    if _singleton is not None:
        return _singleton
    name = get_str("SIM_SCHEDULER", "PF").upper()
    if name == "PF":
        _singleton = PfScheduler()
    elif name == "RR":
        _singleton = RoundRobinScheduler()
    elif name == "MAXTHROUGHPUT":
        _singleton = MaxThroughputScheduler()
    else:
        _singleton = PfScheduler()
    return _singleton


def reset_scheduler() -> None:
    global _singleton
    _singleton = None
