"""URL: /api/v0.1/DU/PHY/<Component>/<Element>"""
from django.urls import path

from main.apps.phy_high.actors.phy_high_actor import PhyHighController

urlpatterns = [
    path(
        "PhyHighController/compute_modulation_throughput",
        PhyHighController.compute_modulation_throughput,
        name="phy_compute_throughput",
    ),
    path("PhyHighController/estimate_bler", PhyHighController.estimate_bler, name="phy_estimate_bler"),
]
