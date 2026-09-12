from django.apps import AppConfig


class FapiNorthConfig(AppConfig):
    name = "main.apps.fapi_north"
    label = "fapi_north"

    def ready(self) -> None:
        return None
