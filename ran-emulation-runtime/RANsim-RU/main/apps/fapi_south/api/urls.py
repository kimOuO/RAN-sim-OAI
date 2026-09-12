"""Routes for /api/v0.1/RU/FAPI/..."""
from django.urls import path

from main.apps.fapi_south.actors.fapi_router import FapiRouter

urlpatterns = [
    path("FapiRouter/dl_tti_request", FapiRouter.dl_tti_request, name="fapi_dl_tti_request"),
    path("FapiRouter/ul_tti_request", FapiRouter.ul_tti_request, name="fapi_ul_tti_request"),
]
