from django.apps import AppConfig


class MacConfig(AppConfig):
    name = "main.apps.mac"
    label = "mac"

    def ready(self) -> None:
        return None
