from rest_framework import serializers

from main.apps.render_scan_mesh.models.scan_asset import ScanAsset


class ScanAssetReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScanAsset
        fields = "__all__"
