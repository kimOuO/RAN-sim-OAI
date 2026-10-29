"""Verify execution isolation, genuine XML values, missing data and secret filtering."""
import io
import json
import tarfile
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from django.test import override_settings

from main.apps.run_lifecycle.services.optional.o1_payloads import cm_document, pm_document, ves_events
from main.apps.run_lifecycle.services.optional import o1_observation as obs


ME = 'gnb_208_095_000e50_du1'
RUN = 'scene_run-05773c085d2f44c68b5c98c2b75b3514'
TAG = 'b75b3514-20261015T062208Z'
CM = f'''<ManagedElement xmlns="urn:3gpp:sa5:_3gpp-common-managed-element"><id>ManagedElement={ME}</id>
<PerfMetricJob><id>job1</id><attributes><performanceMetrics>RRU.PrbTotDl</performanceMetrics>
<granularityPeriod>900</granularityPeriod><fileReportingPeriod>900</fileReportingPeriod></attributes></PerfMetricJob>
<AlarmList><attributes><alarmRecords><alarmId>loss</alarmId><perceivedSeverity>MAJOR</perceivedSeverity></alarmRecords></attributes></AlarmList>
<GNBDUFunction><BWP><attributes><numberOfRBs>106</numberOfRBs></attributes></BWP>
<NRCellDU><id>cell0</id><attributes><cellLocalId>0</cellLocalId><nRPCI>0</nRPCI><nRTAC>1</nRTAC>
<administrativeState>UNLOCKED</administrativeState><operationalState>ENABLED</operationalState>
<cellState>ACTIVE</cellState></attributes></NRCellDU></GNBDUFunction></ManagedElement>'''
PM = f'''<measCollecFile xmlns="urn:3gpp:sa5:32.435#measCollec"><measData>
<managedElement localDn="SubNetwork=test,ManagedElement={ME}" userLabel="runId={TAG}"/>
<measInfo><granPeriod duration="PT900S" endTime="2026-10-15T06:30:00Z"/>
<measType p="1">RRU.PrbTotDl</measType><measValue measObjLdn="GNBDUFunction=1,NRCellDU=0">
<r p="1">12.5</r><suspect>true</suspect></measValue></measInfo></measData></measCollecFile>'''


def ves(kind='notifyFileReady', timestamp=1792045800000000, response=202, run_id=TAG):
    data = {'notificationType': kind, 'fileInfoList': [{'fileLocation': 'sftp://user:secret@host/ftp/pm.xml'}],
            'additionalInformation': {'runId': run_id}, 'perceivedSeverity': 'MAJOR', 'alarmId': 'loss'}
    event = {'event': {'commonEventHeader': {'eventId': kind, 'lastEpochMicrosec': timestamp, 'sourceName': ME},
                       'stndDefinedFields': {'data': data}}}
    return json.dumps(event) + (f' response_code = {response}\n' if response else '\n')


class O1PayloadTest(TestCase):
    def test_cm_reads_pci_zero_and_alarm_state(self):
        d = cm_document(CM, ME, 'g1', 'DU', 'now')
        self.assertEqual(d['cells'][0]['nRPCI'], '0')
        self.assertEqual(d['cells'][0]['numberOfRBs'], '106')
        self.assertEqual(d['alarms'][0]['perceivedSeverity'], 'MAJOR')
        self.assertEqual(d['jobs'][0]['granularity_sec'], 900)
        with self.assertRaises(ValueError):
            cm_document(CM, 'other-me', 'g1', 'DU', 'now')

    def test_pm_preserves_suspect_and_rejects_other_executions(self):
        report = pm_document(PM, '/ftp/pm.xml', ME, TAG)
        self.assertEqual(report['filename'], 'pm.xml')
        self.assertEqual(report['rows'][0]['metrics']['RRU.PrbTotDl'], 12.5)
        self.assertTrue(report['suspect'])
        with self.assertRaises(ValueError):
            pm_document(PM, 'pm.xml', ME, 'different-run')
        with self.assertRaises(ValueError):
            pm_document('<!DOCTYPE x><x/>', 'pm.xml', ME)

    def test_ves_never_exposes_file_credentials(self):
        events = ves_events(ves())
        self.assertEqual(events[0]['filename'], 'pm.xml')
        self.assertEqual(events[0]['http_status'], 202)
        self.assertNotIn('secret', json.dumps(events))
        self.assertNotIn('sftp://', json.dumps(events))

    def test_missing_response_is_not_borrowed_from_next_event(self):
        events = ves_events(ves(response=None) + ves('notifyNewAlarm', response=500))
        self.assertIsNone(next(e for e in events if e['kind'] == 'notifyFileReady')['http_status'])
        self.assertEqual(next(e for e in events if e['kind'] == 'notifyNewAlarm')['http_status'], 500)

    def test_ves_filters_old_times_and_wrong_run(self):
        self.assertEqual(ves_events(ves(), since_ms=1792045800001), [])
        self.assertEqual(ves_events(ves('notifyNewAlarm'), run_id='different-run'), [])


class O1MonitoringTest(TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.settings = override_settings(PER_RUN_LOG_DIR=self.tmp.name)
        self.settings.enable()
        self.addCleanup(self.settings.disable)
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name) / RUN[-8:] / 'o1'
        self.directory.mkdir(parents=True)

    def registry(self, tag=TAG, at='2026-10-15T06:22:08Z'):
        row = {'event': 'start', 'scene_run_uuid': RUN, 'runId': tag, 'ts': at,
               'mes': [{'gnb': 'g1', 'cucp': 'missing-cu', 'du': ME}]}
        (self.directory.parent.parent / '_o1_run_registry.jsonl').write_text(json.dumps(row) + '\n')

    @patch.object(obs.docker, 'from_env')
    def test_stopped_run_recovers_events_without_claiming_current_state(self, factory):
        factory.return_value.containers.list.return_value = []
        self.registry()
        (self.directory.parent / 'o1adapter-du-0.log').write_text(ves())
        data = obs.read_o1(RUN, include_trend=False)
        self.assertEqual(len(data['pm']['files']), 1)
        self.assertEqual(data['pm']['files'][0]['rows'], [])
        self.assertIsNone(data['pm']['files'][0]['suspect'])
        self.assertFalse(data['fm']['current_verified'])
        self.assertFalse(data['smo_receipt_verified'])

    @patch.object(obs.docker, 'from_env')
    def test_new_execution_does_not_use_previous_snapshot_or_logs(self, factory):
        factory.return_value.containers.list.return_value = []
        self.registry()
        obs._save(self.directory, TAG, {'scene_run_uuid': RUN, 'elements': [{'managed_element': ME}], 'files': [], 'events': []})
        (self.directory.parent / 'o1adapter-du-0.log').write_text(ves())
        data = obs.read_o1(RUN, {'run': {'started_at': '2026-10-15T07:00:00Z'}}, include_trend=False)
        self.assertEqual(data['cm']['source'], 'scene')
        self.assertEqual(data['pm']['files'], [])
        self.assertEqual(data['notifications'], [])

    @patch.object(obs.docker, 'from_env')
    def test_runtime_exports_and_snapshot_survive_container_removal(self, factory):
        self.registry()
        adapter = Mock()
        adapter.name, adapter.status = 'o1adapter-du-b75b3514-0', 'running'
        adapter.labels = {'ransim.role': 'o1adapter', 'ransim.gnb': 'g1'}
        adapter.attrs = {'Config': {'Env': [f'O1_NODE_ID={ME}', f'O1_RUN_ID={TAG}', 'O1_UNIT_TYPE=DU', 'PASSWORD=secret']}}
        adapter.logs.return_value = ves('notifyNewAlarm').encode()
        adapter.exec_run.return_value = SimpleNamespace(exit_code=0, output=CM.encode())
        payload = io.BytesIO()
        with tarfile.open(fileobj=payload, mode='w') as archive:
            info = tarfile.TarInfo('ftp/pm.xml'); info.size = len(PM.encode())
            archive.addfile(info, io.BytesIO(PM.encode()))
        adapter.get_archive.return_value = ([payload.getvalue()], {})
        factory.return_value.containers.list.return_value = [adapter]
        data = obs.read_o1(RUN, include_trend=False)
        self.assertEqual(data['cm']['source'], 'o1')
        self.assertEqual(len(data['fm']['active']), 1)
        self.assertFalse(data['fm']['current_verified'])  # Expected CU adapter is missing.
        self.assertEqual(data['pm']['files'][0]['source'], 'o1_xml')
        self.assertNotIn('secret', json.dumps(data))
        factory.return_value.containers.list.return_value = []
        old = obs.read_o1(RUN, include_trend=False)
        self.assertEqual(old['cm']['source'], 'snapshot')
        self.assertEqual(old['containers'][0]['status'], 'removed')
        self.assertTrue(old['pm']['files'][0]['rows'])
        self.assertFalse(old['fm']['current_verified'])

    @patch.object(obs.docker, 'from_env', side_effect=RuntimeError('daemon unavailable'))
    def test_docker_failure_keeps_scene_fallback_and_unknown_fm(self, factory):
        data = obs.read_o1(RUN, include_trend=False)
        self.assertTrue(data['warnings'])
        self.assertFalse(data['fm']['current_verified'])

    def test_rejects_path_traversal(self):
        with self.assertRaises(ValueError):
            obs.read_o1('../../etc/passwd', include_trend=False)

    @patch.object(obs.docker, 'from_env')
    def test_orchestrator_clear_is_retained_after_adapter_removal(self, factory):
        self.registry()
        factory.return_value.containers.list.return_value = []
        event = json.JSONDecoder().raw_decode(ves('notifyClearedAlarm'))[0]
        obs.record_delivery(RUN[-8:], TAG, event, 202)
        data = obs.read_o1(RUN, include_trend=False)
        self.assertEqual(data['fm']['events'][0]['kind'], 'notifyClearedAlarm')
        self.assertEqual(data['fm']['events'][0]['http_status'], 202)
        self.assertFalse(data['fm']['current_verified'])
