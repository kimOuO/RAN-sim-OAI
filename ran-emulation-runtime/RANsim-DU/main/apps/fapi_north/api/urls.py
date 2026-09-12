"""URL: /api/v0.1/DU/FAPI/<Component>/<Element>"""
from django.urls import path

from main.apps.fapi_north.actors.fapi_router_actor import FapiRouterController

urlpatterns = [
    path("FapiRouter/cqi_indication", FapiRouterController.cqi_indication, name="fapi_cqi_ind"),
    path("FapiRouter/crc_indication", FapiRouterController.crc_indication, name="fapi_crc_ind"),
]
