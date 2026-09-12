from rest_framework import serializers

from main.apps.osm_footprint_ingest.models.osm_map_asset import OsmMapAsset


class OsmMapAssetReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = OsmMapAsset
        fields = "__all__"
