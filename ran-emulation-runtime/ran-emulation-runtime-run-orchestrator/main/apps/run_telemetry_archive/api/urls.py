from django.urls import path
from main.apps.run_telemetry_archive.actors.run_kpm_sample_actor import RunKpmSampleController, RunKpmSampleReader
from main.apps.run_telemetry_archive.actors.run_control_event_actor import RunControlEventController, RunControlEventReader
from main.apps.run_telemetry_archive.actors.run_handover_event_actor import RunHandoverEventController, RunHandoverEventReader

urlpatterns = [
    path("RunKpmSampleController/create", RunKpmSampleController.create, name="run_kpm_sample_create"),
    path("RunKpmSampleController/update", RunKpmSampleController.update, name="run_kpm_sample_update"),
    path("RunKpmSampleController/delete", RunKpmSampleController.delete, name="run_kpm_sample_delete"),
    path("RunKpmSampleReader/read", RunKpmSampleReader.read, name="run_kpm_sample_read"),
    path("RunControlEventController/create", RunControlEventController.create, name="run_control_event_create"),
    path("RunControlEventController/update", RunControlEventController.update, name="run_control_event_update"),
    path("RunControlEventController/delete", RunControlEventController.delete, name="run_control_event_delete"),
    path("RunControlEventReader/read", RunControlEventReader.read, name="run_control_event_read"),
    path("RunHandoverEventController/create", RunHandoverEventController.create, name="run_handover_event_create"),
    path("RunHandoverEventController/update", RunHandoverEventController.update, name="run_handover_event_update"),
    path("RunHandoverEventController/delete", RunHandoverEventController.delete, name="run_handover_event_delete"),
    path("RunHandoverEventReader/read", RunHandoverEventReader.read, name="run_handover_event_read"),
]
