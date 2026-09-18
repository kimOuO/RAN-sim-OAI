from django.urls import path

from main.apps.render_osm_footprint.actors.osm_map_asset_actor import OsmFootprintImporter, OsmMapAssetController, OsmMapAssetReader, OsmMapEditor

urlpatterns = [
    path("OsmFootprintImporter/geocode", OsmFootprintImporter.geocode, name="osm_geocode"),
    path("OsmFootprintImporter/generate", OsmFootprintImporter.generate, name="osm_generate"),
    path("OsmMapEditor/preview", OsmMapEditor.preview, name="osm_editor_preview"),
    path("OsmMapEditor/build_scene", OsmMapEditor.build_scene, name="osm_editor_build_scene"),
    path("OsmMapAssetReader/read", OsmMapAssetReader.read, name="osm_asset_read"),
    path("OsmMapAssetController/delete", OsmMapAssetController.delete, name="osm_asset_delete"),
    path("OsmMapAssetController/attach_to_scene", OsmMapAssetController.attach_to_scene, name="osm_asset_attach"),
]
