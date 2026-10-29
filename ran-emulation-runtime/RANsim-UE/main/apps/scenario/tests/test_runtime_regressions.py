from unittest import TestCase
from unittest.mock import Mock, patch

from main.apps.scenario.services.scenario_loader import ScenarioSpec, UeScenarioRow, fetch_by_run
from main.apps.scenario.services.scenario_driver import ScenarioDriver
from main.apps.scenario.services.ue_attach import UeAttachService


class RuntimeRegressionTest(TestCase):
    def test_idle_cu_session_replaces_connected_snapshot_without_losing_trajectory(self):
        from main.apps.ue_lifecycle.services.manager import UeLifecycleManager
        from main.apps.ue_lifecycle.services.ue_thread import UeThread, UeThreadState, UeContextSnapshot
        m = UeLifecycleManager()
        t = UeThread('ue11')
        t.update_snapshot(UeContextSnapshot('ue11', serving_cell='gnb1_c0', rrc_state='CONNECTED'))
        t.transition_to(UeThreadState.RUNNING)
        t.position = (3, 1.5, 7)
        m._threads['ue11'] = t
        with patch('main.apps.ue_lifecycle.services.manager.cu_client.list_sessions',
                   return_value=[{'ue_id': 'ue11', 'rrc_state': 'IDLE', 'serving_cell': ''}]):
            m._sync_from_cu()
        self.assertIs(m._threads['ue11'], t)
        self.assertEqual(t.position, (3, 1.5, 7))
        self.assertEqual(t.status()['rrc_state'], 'IDLE')
        self.assertEqual(t.state, UeThreadState.STANDBY)

    def test_prepare_external_dus_does_not_advance_ru_clock(self):
        from main.apps.ue_lifecycle.services import du_client
        with patch.object(du_client.ran_endpoints, 'external_clock', return_value=True), \
             patch.object(du_client, '_all_dus', return_value=True) as prepare, \
             patch.object(du_client, '_ru_clock') as ru:
            self.assertTrue(du_client.prepare_tick())
        prepare.assert_called_once_with('/api/v0.1/DU/Tick/TickController/start')
        ru.assert_not_called()

    def spec(self):
        return ScenarioSpec(scenario_id='test', scene_id='test', duration_sec=600, tick_ms=500,
                            ues=[UeScenarioRow('timed', [[0, 0, 1.5, 0]]), UeScenarioRow('ue11', [[0, 1, 1.5, 0]]),
                                 UeScenarioRow('absent', [[0, 2, 1.5, 0]])], traffic=[],
                            active_windows={'timed': [[0, 600]], 'absent': []})

    def test_manual_ue_is_attached_alongside_timed_ue(self):
        with patch('main.apps.scenario.services.scenario_driver.UeAttachService.attach_all', return_value={'failed': []}) as attach, \
             patch('main.apps.ue_lifecycle.services.manager.get_manager'):
            ScenarioDriver(self.spec())._setup_rlc_entities()
        self.assertEqual([u['name'] for u in attach.call_args.args[0]], ['timed', 'ue11'])

    def test_stopped_clock_does_not_advance_or_finish_on_wall_time(self):
        d = ScenarioDriver(self.spec())
        d.state.update(running=True, started_at_ms=1)
        with patch.object(d, '_du_scene_sec', return_value=14.5), \
             patch('main.apps.ue_lifecycle.services.du_client.get_clock_status', return_value={'running': False}), \
             patch('main.apps.ue_lifecycle.services.manager.get_manager') as mgr:
            mgr.return_value.snapshot.return_value = {'threads': []}
            self.assertEqual(d.live_state()['elapsed_sim_sec'], 14.5)
            with patch.object(d, '_du_scene_sec', return_value=0):
                st = d.live_state()
                self.assertEqual(st['elapsed_sim_sec'], 14.5)
                self.assertFalse(st['finished'])
                self.assertEqual(st['phase'], 'stalled')

    def test_registry_cache_key_uses_scene_uuid_and_explicit_absence_survives(self):
        tree = {'scene': {'scene_uuid': 'scene-123', 'name': 'test'}, 'run': {'duration_sec': 600, 'sim_dt_ms': 500},
                'gnbs': [], 'buildings': [], 'ues': [
                    {'name': 'timed', 'waypoints': [[0, 0, 1.5, 0]], 'active_windows': [[0, 600]]},
                    {'name': 'ue11', 'waypoints': [[0, 1, 1.5, 0]], 'active_windows': [], 'presence_restricted': False,
                     'traffic': [{'pattern': 'cbr', 'rate_mbps': 2, 'schedule': None}]},
                    {'name': 'absent', 'waypoints': [[0, 2, 1.5, 0]], 'active_windows': [], 'presence_restricted': True}]}
        response = Mock(); response.json.return_value = {'success': True, 'data': tree}
        with patch('main.apps.scenario.services.scenario_loader.requests.post', return_value=response), \
             patch('main.apps.scenario.services.scenario_loader.REGISTRY_URL', 'http://registry'):
            spec = fetch_by_run('run-test')
        self.assertEqual(spec.cache_scenario_id, 'scene-123')
        self.assertNotIn('ue11', spec.active_windows)
        self.assertEqual(spec.active_windows['absent'], [])
        self.assertTrue(spec.auto_select_initial)
        self.assertEqual(spec.traffic[0].profile, [[0.0, 2000.0, 0.0]])

    def test_initial_cell_uses_measurement_instead_of_first_cell(self):
        with patch('main.apps.scenario.services.ue_attach.ran_endpoints.topology', return_value=Mock()), \
             patch('main.apps.ue_lifecycle.services.cell_selection.select_cell', return_value=('gnb2_c1', -80)), \
             patch('main.apps.scenario.services.ue_attach.cu_client.rrc_attach', return_value=True) as attach:
            result = UeAttachService.attach_all([{'name': 'ue11', 'auto_select': True, 'position': [1, 1.5, 2]}], default_serving_cell='gnb1_c0')
        self.assertEqual(result['attached'], 1)
        attach.assert_called_once_with('ue11', 'gnb2_c1')

    def test_visual_failure_does_not_repeat_network_attach(self):
        from main.apps.ue_lifecycle.services.manager import UeLifecycleManager
        m = UeLifecycleManager()
        m.set_active_windows({'ue11': [[0, 600]]})
        m._scenario_elapsed_ms = Mock(return_value=0)
        m._apply_presence = Mock(return_value=True)
        store = Mock(); store.get.return_value = {'waypoints': [{'t_ms': 0, 'x': 1, 'y': 1.5, 'z': 2}]}
        with patch('main.apps.ue_lifecycle.services.manager.kit_client.set_ue_visible', return_value=False):
            m._sync_visibility(store, 10000)
            m._sync_visibility(store, 14000)
        m._apply_presence.assert_called_once_with('ue11', True)
        self.assertTrue(m._last_visible['ue11'])


class UeLoopFlagTest(TestCase):
    """場景 UE 的 loop 要一路傳到 trajectory_store(2026-10-29 前劇本路徑一律 once)。"""

    def test_registry_loop_flag_reaches_spec(self):
        tree = {'scene': {'scene_uuid': 'scene-1', 'name': 't'}, 'run': {'duration_sec': 600, 'sim_dt_ms': 500},
                'gnbs': [], 'buildings': [], 'ues': [
                    {'name': 'walker', 'waypoints': [[0, 0, 1.5, 0], [60, 10, 1.5, 0]], 'loop': True},
                    {'name': 'still', 'waypoints': [[0, 1, 1.5, 0]]}]}
        response = Mock(); response.json.return_value = {'success': True, 'data': tree}
        with patch('main.apps.scenario.services.scenario_loader.requests.post', return_value=response), \
             patch('main.apps.scenario.services.scenario_loader.REGISTRY_URL', 'http://registry'):
            spec = fetch_by_run('run-test')
        self.assertEqual({u.name: u.loop for u in spec.ues}, {'walker': True, 'still': False})

    def test_push_waypoints_uses_loop_mode_only_when_set(self):
        path = [[0, 0, 1.5, 0], [60, 10, 1.5, 0]]
        spec = ScenarioSpec(scenario_id='t', scene_id='t', duration_sec=600, tick_ms=500,
                            ues=[UeScenarioRow('walker', path, loop=True), UeScenarioRow('once', path)],
                            traffic=[])
        store = Mock()
        with patch('main.apps.scenario.services.scenario_driver.get_traj_store', return_value=store):
            ScenarioDriver(spec)._push_waypoints_to_store()
        modes = {c.args[0]: c.kwargs['mode'] for c in store.set.call_args_list}
        self.assertEqual(modes, {'walker': 'loop', 'once': 'once'})
