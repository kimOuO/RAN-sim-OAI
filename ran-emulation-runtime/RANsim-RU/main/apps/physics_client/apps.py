from django.apps import AppConfig


class PhysicsClientConfig(AppConfig):
    name = "main.apps.physics_client"
    label = "physics_client"

    def ready(self):
        return
