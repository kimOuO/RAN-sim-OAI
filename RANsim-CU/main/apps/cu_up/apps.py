"""CU-UP app config — user plane (PDCP, SDAP, GTP-U)."""
from django.apps import AppConfig


class CuUpConfig(AppConfig):
    name = "main.apps.cu_up"
    label = "cu_up"
    verbose_name = "CU User Plane"
