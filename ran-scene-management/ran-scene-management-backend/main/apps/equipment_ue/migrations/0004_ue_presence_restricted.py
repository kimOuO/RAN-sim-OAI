from django.db import migrations, models


def preserve_imported_slices(apps, schema_editor):
    Ue = apps.get_model('equipment_ue', 'Ue')
    Window = apps.get_model('equipment_ue', 'UeActiveWindow')
    # Imported slices historically use empty windows to mean absent. Preserve
    # that interpretation, while manually placed UEs default to unrestricted.
    scene_ids = Ue.objects.filter(
        ue_uuid__in=Window.objects.values_list('ue_id', flat=True),
    ).exclude(scene__legacy_scenario_id='').values_list('scene_id', flat=True)
    Ue.objects.filter(scene_id__in=list(scene_ids)).update(presence_restricted=True)


class Migration(migrations.Migration):
    dependencies = [('equipment_ue', '0003_alter_ue_antenna_preset_alter_ue_scene_and_more')]
    operations = [
        migrations.AddField(model_name='ue', name='presence_restricted', field=models.BooleanField(default=False)),
        migrations.RunPython(preserve_imported_slices, migrations.RunPython.noop),
    ]
