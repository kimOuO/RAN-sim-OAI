"""CU-CP app config — control plane (RRC, F1AP CU side, NGAP, E1AP)."""
from django.apps import AppConfig


class CuCpConfig(AppConfig):
    name = "main.apps.cu_cp"
    label = "cu_cp"
    verbose_name = "CU Control Plane"

    def ready(self) -> None:  # noqa: D401
        # Optional NGSetup-on-boot can hook here once HTTP_AMF_HOST is set.
        return None
