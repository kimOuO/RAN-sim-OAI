from django.apps import AppConfig


class BeamformingConfig(AppConfig):
    name = "main.apps.beamforming"
    label = "beamforming"

    def ready(self):
        return
