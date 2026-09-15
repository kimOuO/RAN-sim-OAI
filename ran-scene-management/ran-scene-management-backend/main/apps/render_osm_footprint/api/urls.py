from django.urls import path

from main.apps.render_osm_footprint.actors.osm_map_asset_actor import OsmFootprintImporter, OsmMapAssetController, OsmMapAssetReader

urlpatterns = [
    path("OsmFootprintImporter/geocode", OsmFootprintImporter.geocode, name="osm_geocode"),
    path("OsmFootprintImporter/generate", OsmFootprintImporter.generate, name="osm_generate"),
    path("OsmMapAssetReader/read", OsmMapAssetReader.read, name="osm_asset_read"),
    path("OsmMapAssetController/delete", OsmMapAssetController.delete, name="osm_asset_delete"),
    path("OsmMapAssetController/attach_to_scene", OsmMapAssetController.attach_to_scene, name="osm_asset_attach"),
]
