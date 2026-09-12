"""ASGI entrypoint."""
import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "main.settings.local")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
