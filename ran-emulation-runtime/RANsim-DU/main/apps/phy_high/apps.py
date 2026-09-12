from django.apps import AppConfig


class PhyHighConfig(AppConfig):
    name = "main.apps.phy_high"
    label = "phy_high"

    def ready(self) -> None:
        return None
