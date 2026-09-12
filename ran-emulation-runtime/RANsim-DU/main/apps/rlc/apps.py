from django.apps import AppConfig


class RlcConfig(AppConfig):
    name = "main.apps.rlc"
    label = "rlc"

    def ready(self) -> None:
        return None
