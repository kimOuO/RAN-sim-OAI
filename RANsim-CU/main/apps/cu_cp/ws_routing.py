"""WebSocket URL routing for cu_cp app."""
from django.urls import path

from main.apps.cu_cp.ws_consumers import E2IndicationConsumer


websocket_urlpatterns = [
    # E2 Indication push channel — xApp 訂閱後在此收 indication
    path("ws/v0.1/CU/E2/indication", E2IndicationConsumer.as_asgi()),
]
