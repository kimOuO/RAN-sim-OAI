from django.urls import path

from main.apps.phy_low.actors.clock_actor import LockstepClockController
from main.apps.phy_low.actors.ru_state_actor import RuStateReader

urlpatterns = [
    path("RuStateReader/read", RuStateReader.read, name="ru_state_read"),
    path("LockstepClock/start", LockstepClockController.start, name="ru_clock_start"),
    path("LockstepClock/stop", LockstepClockController.stop, name="ru_clock_stop"),
    path("LockstepClock/set_speed", LockstepClockController.set_speed, name="ru_clock_set_speed"),
    path("LockstepClock/align_scene", LockstepClockController.align_scene, name="ru_clock_align_scene"),
    path("LockstepClock/read", LockstepClockController.read, name="ru_clock_read"),
]
