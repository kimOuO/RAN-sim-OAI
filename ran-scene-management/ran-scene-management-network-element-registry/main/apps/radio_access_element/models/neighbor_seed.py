"""neighbor_seed — 一個 table 一個檔案(backend_rule §5-1)。設計見 new_plan §2.3。"""
from django.db import models


class NeighborSeed(models.Model):
    id = models.AutoField(primary_key=True)
    neighbor_seed_uuid = models.CharField(max_length=255, unique=True, db_index=True)
    source_cell = models.ForeignKey("radio_access_element.Cell", on_delete=models.CASCADE, to_field="cell_uuid", db_column="f_source_cell_uuid", related_name="neighbor_seeds_out", db_index=True)
    target_cell = models.ForeignKey("radio_access_element.Cell", on_delete=models.CASCADE, to_field="cell_uuid", db_column="f_target_cell_uuid", related_name="neighbor_seeds_in", db_index=True)
    ho_blocklist = models.BooleanField(default=False)
    no_remove = models.BooleanField(default=False)
    xn_blocklist = models.BooleanField(default=False)
    neighbor_seed_created_at = models.DateTimeField()
    neighbor_seed_updated_at = models.DateTimeField()

    class Meta:
        app_label = "radio_access_element"
        db_table = "radio_access_element_neighbor_seed"
        ordering = ("id",)
