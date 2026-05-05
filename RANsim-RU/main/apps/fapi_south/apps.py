from django.apps import AppConfig


class FapiSouthConfig(AppConfig):
    name = "main.apps.fapi_south"
    label = "fapi_south"

    def ready(self):
        return
