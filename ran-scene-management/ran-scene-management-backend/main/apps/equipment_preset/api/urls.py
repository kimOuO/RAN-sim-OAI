from django.urls import path
from main.apps.equipment_preset.actors.antenna_preset_actor import AntennaPresetController, AntennaPresetReader
from main.apps.equipment_preset.actors.du_config_template_actor import DuConfigTemplateController, DuConfigTemplateReader
from main.apps.equipment_preset.actors.gnb_config_template_actor import GnbConfigTemplateController, GnbConfigTemplateReader

urlpatterns = [
    path("AntennaPresetController/create", AntennaPresetController.create, name="antenna_preset_create"),
    path("AntennaPresetController/update", AntennaPresetController.update, name="antenna_preset_update"),
    path("AntennaPresetController/delete", AntennaPresetController.delete, name="antenna_preset_delete"),
    path("AntennaPresetReader/read", AntennaPresetReader.read, name="antenna_preset_read"),
    path("DuConfigTemplateController/create", DuConfigTemplateController.create, name="du_config_template_create"),
    path("DuConfigTemplateController/update", DuConfigTemplateController.update, name="du_config_template_update"),
    path("DuConfigTemplateController/delete", DuConfigTemplateController.delete, name="du_config_template_delete"),
    path("DuConfigTemplateReader/read", DuConfigTemplateReader.read, name="du_config_template_read"),
    path("GnbConfigTemplateController/create", GnbConfigTemplateController.create, name="gnb_config_template_create"),
    path("GnbConfigTemplateController/update", GnbConfigTemplateController.update, name="gnb_config_template_update"),
    path("GnbConfigTemplateController/delete", GnbConfigTemplateController.delete, name="gnb_config_template_delete"),
    path("GnbConfigTemplateReader/read", GnbConfigTemplateReader.read, name="gnb_config_template_read"),
]
