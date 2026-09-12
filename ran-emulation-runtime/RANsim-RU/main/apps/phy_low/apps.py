from django.apps import AppConfig


class PhyLowConfig(AppConfig):
    name = "main.apps.phy_low"
    label = "phy_low"

    def ready(self):
        return
