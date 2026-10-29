from unittest import TestCase
from unittest.mock import Mock, patch
from main.apps.run_lifecycle.services.optional.o1_observation import read_o1
from main.apps.run_lifecycle.services.optional.health_monitor import dependency_issue


class O1ObservationTest(TestCase):
    def test_inventory_is_run_scoped_and_omits_credentials(self):
        adapter = Mock(name='adapter')
        adapter.name, adapter.status = 'o1adapter-test', 'running'
        adapter.labels = {'ransim.role': 'o1adapter', 'ransim.gnb': 'g1'}
        adapter.attrs = {'Config': {'Env': ['O1_NODE_ID=me1', 'O1_NETCONF_PORT=1990', 'SECRET=do-not-expose',
                                          'O1_VES_URL=http://user:do-not-expose@host/events?token=do-not-expose']}, 'State': {}}
        with patch('main.apps.run_lifecycle.services.optional.o1_observation.docker.from_env') as factory:
            client = factory.return_value
            client.containers.list.return_value = [adapter]
            data = read_o1('run-test')
            client.containers.list.assert_called_once_with(all=True, filters={'label': 'ransim.scene_run_uuid=run-test'})
        self.assertEqual(data['containers'][0]['managed_element'], 'me1')
        self.assertNotIn('do-not-expose', str(data))
        self.assertFalse(data['smo_receipt_verified'])

    def test_stopped_ru_clock_is_unhealthy_even_if_http_is_alive(self):
        self.assertIn('時鐘', dependency_issue('ru', {'clock': {'running': False}}))
        self.assertEqual(dependency_issue('ru', {'clock': {'running': True}}), '')
