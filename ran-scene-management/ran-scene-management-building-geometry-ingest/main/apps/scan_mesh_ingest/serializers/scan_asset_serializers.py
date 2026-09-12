from rest_framework import serializers

from main.apps.scan_mesh_ingest.models.scan_asset import ScanAsset


class ScanAssetReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanAsset
        fields = "__all__"
