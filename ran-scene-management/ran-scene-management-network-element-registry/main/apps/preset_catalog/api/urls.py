from django.urls import path
from main.apps.preset_catalog.actors.material_actor import MaterialController, MaterialReader
from main.apps.preset_catalog.actors.antenna_preset_actor import AntennaPresetController, AntennaPresetReader
from main.apps.preset_catalog.actors.du_config_template_actor import DuConfigTemplateController, DuConfigTemplateReader

urlpatterns = [
    path("MaterialController/create", MaterialController.create, name="material_create"),
    path("MaterialController/update", MaterialController.update, name="material_update"),
    path("MaterialController/delete", MaterialController.delete, name="material_delete"),
    path("MaterialReader/read", MaterialReader.read, name="material_read"),
    path("AntennaPresetController/create", AntennaPresetController.create, name="antenna_preset_create"),
    path("AntennaPresetController/update", AntennaPresetController.update, name="antenna_preset_update"),
    path("AntennaPresetController/delete", AntennaPresetController.delete, name="antenna_preset_delete"),
    path("AntennaPresetReader/read", AntennaPresetReader.read, name="antenna_preset_read"),
    path("DuConfigTemplateController/create", DuConfigTemplateController.create, name="du_config_template_create"),
    path("DuConfigTemplateController/update", DuConfigTemplateController.update, name="du_config_template_update"),
    path("DuConfigTemplateController/delete", DuConfigTemplateController.delete, name="du_config_template_delete"),
    path("DuConfigTemplateReader/read", DuConfigTemplateReader.read, name="du_config_template_read"),
]
