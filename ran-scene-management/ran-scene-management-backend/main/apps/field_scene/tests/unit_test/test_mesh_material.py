"""Material edits preserve individual buildings, geometry and shared source assets."""
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import Client, TestCase
from django.utils import timezone
from shapely.geometry import Polygon

from main.apps.field_scene.models.scene import Scene
from main.apps.field_scene.models.material import Material
from main.apps.simulation_run.models.scene_run import SceneRun
from main.apps.field_scene.services.optional.scene_geometry import mitsuba_shapes, mesh_material
from main.apps.field_scene.services.optional.scene_geometry.osm_mesh_parts import read_parts
from main.apps.render_osm_footprint.services.optional.osm_to_mitsuba import write_mitsuba

BASE = '/api/v0.1/Scene_management_backend/Field_scene'


class MeshMaterialTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.xml = self.root / 'source.xml'
        # Adjacent buildings share coordinates, but must remain separate objects.
        buildings = [{'poly': Polygon([(0, 0), (5, 0), (5, 5), (0, 5)]), 'base': 0, 'top': 8, 'material': 'concrete'},
                     {'poly': Polygon([(5, 0), (10, 0), (10, 5), (5, 5)]), 'base': 0, 'top': 8, 'material': 'concrete'}]
        write_mitsuba(buildings, self.xml, (-5, -5, 15, 15))
        self.addCleanup(patch.stopall)
        patch.object(mitsuba_shapes, 'ALLOWED_ROOTS', (self.root,)).start()
        patch.object(mesh_material, 'EDIT_ROOT', self.root / 'edits').start()
        now = timezone.now()
        self.scene = Scene.objects.create(scene_uuid='scene-material-test', name='Material test',
            geometry_source={'type': 'mitsuba_xml_path', 'path': str(self.xml), 'origin': 'osm'},
            scene_created_at=now, scene_updated_at=now)
        self.material = Material.objects.create(material_uuid='material-wood-test', key='wood', itu_id='itu_wood',
            material_created_at=now, material_updated_at=now)
        self.run = SceneRun.objects.create(scene_run_uuid='scene_run-material-test', scene=self.scene, cache_path='old-cache.npz',
            scene_run_created_at=now, scene_run_updated_at=now)
        self.client = Client()

    def post(self, action, body):
        return self.client.post(f'{BASE}/{action}', data=json.dumps(body), content_type='application/json')

    def meshes(self, scene=None):
        return self.post('SceneGeometryReader/meshes', {'scene_uuid': (scene or self.scene).scene_uuid}).json()['data']

    def edit(self, shape_id):
        return self.post('SceneGeometryController/set_material', {'scene_uuid': self.scene.scene_uuid,
            'shape_id': shape_id, 'material_uuid': self.material.material_uuid})

    def test_adjacent_buildings_are_separate_and_mesh_bytes_are_correct(self):
        shapes = self.meshes()
        buildings = [s for s in shapes if s['kind'] == 'building']
        self.assertEqual(len(buildings), 2)
        response = self.post('SceneGeometryReader/mesh_file', {'scene_uuid': self.scene.scene_uuid, 'shape_id': buildings[0]['shape_id']})
        payload = b''.join(response.streaming_content)
        path = self.root / 'returned.ply'; path.write_bytes(payload)
        vertices, faces, _ = read_parts(str(path))
        self.assertAlmostEqual(vertices[:, 0].max(), 5)
        self.assertEqual(len(faces), 10)  # Four walls plus two roof triangles.

    def test_one_building_changes_without_touching_geometry_or_source(self):
        before = self.meshes()
        original = self.xml.read_bytes()
        selected = before[0]['shape_id']
        response = self.edit(selected)
        self.assertEqual(response.status_code, 200, response.content)
        self.scene.refresh_from_db(); self.run.refresh_from_db()
        self.assertNotEqual(self.scene.geometry_source['path'], str(self.xml))
        self.assertEqual(self.xml.read_bytes(), original)
        self.assertEqual(self.run.cache_path, '')
        after = self.meshes()
        self.assertEqual([s['shape_id'] for s in before], [s['shape_id'] for s in after])
        self.assertEqual([s['geometry_key'] for s in before], [s['geometry_key'] for s in after])
        self.assertEqual(after[0]['material'], 'itu_wood')
        self.assertTrue(all(s['material'] == 'itu_concrete' for s in after[1:]))
        # A second edit preserves stable identifiers and leaves the first edit intact.
        self.assertEqual(self.edit(after[1]['shape_id']).status_code, 200)
        self.assertEqual([s['material'] for s in self.meshes()], ['itu_wood', 'itu_wood', 'itu_concrete'])

    def test_shared_source_in_another_scene_is_unchanged(self):
        now = timezone.now()
        other = Scene.objects.create(scene_uuid='scene-material-other', name='Other', geometry_source=self.scene.geometry_source,
            scene_created_at=now, scene_updated_at=now)
        self.assertEqual(self.edit(self.meshes()[0]['shape_id']).status_code, 200)
        self.assertTrue(all(s['material'] == 'itu_concrete' for s in self.meshes(other)))

    def test_rejects_running_scene_invalid_material_and_unknown_shape(self):
        self.run.status = 'running'; self.run.save()
        self.assertEqual(self.edit(self.meshes()[0]['shape_id']).status_code, 409)
        self.run.status = 'idle'; self.run.save()
        self.assertEqual(self.edit('missing').status_code, 404)
        response = self.post('SceneGeometryController/set_material', {'scene_uuid': self.scene.scene_uuid,
            'shape_id': self.meshes()[0]['shape_id'], 'material_uuid': 'missing'})
        self.assertEqual(response.status_code, 400)
        self.scene.refresh_from_db()
        self.assertEqual(self.scene.geometry_source['path'], str(self.xml))

    def test_model_path_cannot_escape_scene_roots(self):
        self.assertEqual(mitsuba_shapes.list_shapes('/etc/passwd'), [])
        self.assertEqual(self.edit('../../etc/passwd').status_code, 404)
