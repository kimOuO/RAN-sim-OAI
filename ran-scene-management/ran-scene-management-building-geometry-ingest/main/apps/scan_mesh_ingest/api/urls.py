from django.urls import path

from main.apps.scan_mesh_ingest.actors.scan_asset_actor import ScanAssetController, ScanAssetReader, ScanMeshImporter

urlpatterns = [
    path("ScanMeshImporter/import_glb", ScanMeshImporter.import_glb, name="scan_import_glb"),
    path("ScanAssetReader/read", ScanAssetReader.read, name="scan_asset_read"),
    path("ScanAssetController/delete", ScanAssetController.delete, name="scan_asset_delete"),
    path("ScanAssetController/attach_to_scene", ScanAssetController.attach_to_scene, name="scan_asset_attach"),
]
