from django.urls import path

from main.apps.physics_client.actors.physics_health_actor import PhysicsHealth

urlpatterns = [
    path("PhysicsHealth/read", PhysicsHealth.read, name="physics_health_read"),
]
