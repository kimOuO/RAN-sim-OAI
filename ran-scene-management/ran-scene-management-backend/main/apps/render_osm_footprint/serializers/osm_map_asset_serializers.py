from rest_framework import serializers

from main.apps.render_osm_footprint.models.osm_map_asset import OsmMapAsset


class OsmMapAssetReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = OsmMapAsset
        fields = "__all__"
