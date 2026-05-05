from django.urls import path

from main.apps.phy_low.actors.ru_state_actor import RuStateReader

urlpatterns = [
    path("RuStateReader/read", RuStateReader.read, name="ru_state_read"),
]
