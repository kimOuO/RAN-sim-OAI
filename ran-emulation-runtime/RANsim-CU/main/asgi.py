"""ASGI config for RANsim-CU.

Handles both HTTP (Django views) and WebSocket (Channels) protocols.
WebSocket 用於 E2 Indication push（對齊 OAI RIC Indication SCTP push 語意）。
"""
import os

# Setup Django before importing anything that touches Django apps
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")

from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter  # noqa: E402

from main.apps.cu_cp.ws_routing import websocket_urlpatterns  # noqa: E402


application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": URLRouter(websocket_urlpatterns),
})
