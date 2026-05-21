"""e2_adapter routes — direct binding from {Component}/{Element} to Actor.method.

URL pattern: POST /api/v0.1/E2Adapter/{Module}/{Component}/{Element}
"""
from django.urls import path

from main.apps.e2_adapter.actors.adapter_status_actor import AdapterStatusActor
from main.apps.e2_adapter.actors.event_log_actor import EventLogActor
from main.apps.e2_adapter.actors.kpm_snapshot_actor import (
    KpmHistoryActor, KpmRecentActor, KpmSnapshotActor,
)
from main.apps.e2_adapter.actors.kpm_speed_actor import KpmSpeedActor

urlpatterns = [
    path("Status/AdapterStatusReader/read", AdapterStatusActor.read, name="adapter_status_read"),
    path("EventLog/EventLogReader/read", EventLogActor.read, name="event_log_read"),
    path("KpmSnapshot/SnapshotReader/read", KpmSnapshotActor.read, name="kpm_snapshot_read"),
    path("KpmSnapshot/RecentReader/read", KpmRecentActor.read, name="kpm_recent_read"),
    path("KpmSnapshot/HistoryReader/read", KpmHistoryActor.read, name="kpm_history_read"),
    # Sim-speed knob — Dashboard 同步加速時呼這個讓 SCTP poll 也加速。
    path("KpmSpeed/SpeedController/set",  KpmSpeedActor.set,  name="kpm_speed_set"),
    path("KpmSpeed/SpeedController/read", KpmSpeedActor.read, name="kpm_speed_read"),
]
