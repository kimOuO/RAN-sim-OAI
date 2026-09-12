from django.apps import AppConfig


class TickConfig(AppConfig):
    name = "main.apps.tick"
    label = "tick"

    def ready(self) -> None:
        return None
