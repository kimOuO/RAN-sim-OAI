import json
from django.test import Client, TestCase

from main.apps.equipment_ue.models.ue import Ue
from main.apps.equipment_ue.models.ue_waypoint import UeWaypoint
from main.apps.field_scene.services.optional.scenario_import.scenario_v1 import import_scenario, export_scenario

BASE = '/api/v0.1/Scene_management_backend/Equipment_ue'


class PathAndPresenceTest(TestCase):
    def setUp(self):
        self.ids = import_scenario({'scenario_id': 'path-presence-test', 'duration_sec': 600, 'tick_ms': 500,
            'ues': [{'name': 'manual', 'positions': [[0, 1, 1.5, 2]]},
                    {'name': 'absent', 'positions': [[0, 2, 1.5, 3]], 'active': []},
                    {'name': 'timed', 'positions': [[0, 3, 1.5, 4]], 'active': [[0, 600]]}]})
        self.ue = Ue.objects.get(scene_id=self.ids['scene_uuid'], name='manual')

    def post(self, points):
        return Client().post(f'{BASE}/UeWaypointController/replace',
            data=json.dumps({'f_ue_uuid': self.ue.ue_uuid, 'waypoints': points}), content_type='application/json')

    def test_path_readback_and_other_ues_are_preserved(self):
        points = [[0, 1, 1.5, 2], [30, 10, 1.5, 20]]
        self.assertEqual(self.post(points).status_code, 200)
        self.assertEqual(list(UeWaypoint.objects.filter(ue=self.ue).order_by('ord').values_list('t_sec', 'x', 'y', 'z')),
                         [tuple(p) for p in points])
        self.assertEqual(UeWaypoint.objects.exclude(ue=self.ue).count(), 2)

    def test_invalid_path_does_not_delete_existing_path(self):
        for points in ([], [[0, 1, 2, 3], [0, 9, 9, 9]], [[2, 1, 2, 3]], [[0, float('inf'), 2, 3]]):
            self.assertEqual(self.post(points).status_code, 400)
            self.assertEqual(list(UeWaypoint.objects.filter(ue=self.ue).values_list('x', 'z')), [(1, 2)])

    def test_unrestricted_and_explicit_absence_roundtrip(self):
        self.assertFalse(self.ue.presence_restricted)
        self.assertTrue(Ue.objects.get(scene_id=self.ids['scene_uuid'], name='absent').presence_restricted)
        ues = {u['name']: u for u in export_scenario(self.ids['scene_uuid'])['ues']}
        self.assertNotIn('active', ues['manual'])
        self.assertEqual(ues['absent']['active'], [])
        self.assertEqual(ues['timed']['active'], [[0, 600]])
