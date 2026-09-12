from django.apps import AppConfig


class AntennaConfig(AppConfig):
    name = "main.apps.antenna"
    label = "antenna"

    def ready(self):
        return
