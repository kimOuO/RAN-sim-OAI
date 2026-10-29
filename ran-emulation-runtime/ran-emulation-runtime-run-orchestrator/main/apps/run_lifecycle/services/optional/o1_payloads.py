"""Normalize O1 read responses. Only allowlisted fields leave the DT host.

In particular, VES pnfRegistration and fileLocation contain credentials. Never
return raw VES payloads, adapter configuration, or raw container logs to the UI.
"""
from __future__ import annotations

import json
import math
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import urlsplit, urlunsplit


def public_url(value: str) -> str:
    try:
        url = urlsplit(value)
        return urlunsplit((url.scheme, url.netloc.rsplit('@', 1)[-1], url.path, '', ''))
    except ValueError:
        return ''


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def epoch_ms(value) -> int | None:
    try:
        return int(datetime.fromisoformat(str(value).replace('Z', '+00:00')).timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return None


def xml_root(raw):
    # Both sysrepo and PM use namespaces; strip them once for the fixed queries.
    if b'<!DOCTYPE' in (raw.encode() if isinstance(raw, str) else raw).upper():
        raise ValueError('XML DTD is not supported')
    root = ET.fromstring(raw)
    for el in root.iter():
        el.tag = el.tag.rsplit('}', 1)[-1]
    return root


def cm_document(raw, me: str, gnb: str, unit: str, observed_at: str) -> dict:
    root = xml_root(raw)
    me_root = root if root.tag == 'ManagedElement' else root.find('.//ManagedElement')
    if me_root is None:
        raise ValueError('ManagedElement missing')
    # Reject a response for another ME rather than attaching it to this run.
    if me_root.findtext('id') != f'ManagedElement={me}':
        raise ValueError('ManagedElement mismatch')
    element = {'managed_element': me, 'gnb': gnb, 'unit_type': unit, 'source': 'o1',
               'observed_at': observed_at, 'vendor': me_root.findtext('attributes/vendorName'),
               'software_version': me_root.findtext('attributes/swVersion'), 'cells': [], 'jobs': [], 'alarms': []}
    for cell in me_root.findall('.//NRCellDU') + me_root.findall('.//NRCellCU'):
        attr = cell.find('attributes')
        if attr is None:
            continue
        row = {'dn': cell.findtext('id'), 'kind': cell.tag, 'local_cell_id': attr.findtext('cellLocalId')}
        for key in ('nRPCI', 'nRTAC', 'arfcnDL', 'arfcnUL', 'bSChannelBwDL', 'bSChannelBwUL',
                    'administrativeState', 'operationalState', 'cellState'):
            row[key] = attr.findtext(key)
        row['plmn'] = [f"{p.findtext('mcc', '')}/{p.findtext('mnc', '')}" for p in attr.findall('pLMNInfoList')]
        bwp = me_root.find('.//BWP/attributes/numberOfRBs')
        row['numberOfRBs'] = bwp.text if bwp is not None else None
        element['cells'].append(row)
    for job in me_root.findall('PerfMetricJob'):
        element['jobs'].append({'dn': job.findtext('id'),
                                'metrics': [e.text for e in job.findall('attributes/performanceMetrics')],
                                'granularity_sec': number(job.findtext('attributes/granularityPeriod')),
                                'reporting_sec': number(job.findtext('attributes/fileReportingPeriod'))})
    for alarm in me_root.findall('AlarmList/attributes/alarmRecords'):
        element['alarms'].append({key: alarm.findtext(key) for key in
                                  ('alarmId', 'objectInstance', 'perceivedSeverity', 'alarmType',
                                   'probableCause', 'specificProblem', 'alarmRaisedTime', 'alarmClearedTime')})
    return element


def pm_document(raw, filename: str, me: str, run_id: str = '') -> dict:
    root = xml_root(raw)
    element = root.find('.//managedElement')
    if element is None or f'ManagedElement={me}' not in element.get('localDn', '').split(','):
        raise ValueError('PM ManagedElement mismatch')
    if run_id and element.get('userLabel') != f'runId={run_id}':
        raise ValueError('PM execution mismatch')
    report = {'filename': PurePosixPath(filename).name, 'managed_element': me, 'source': 'o1_xml',
              'end_time': None, 'duration_sec': None, 'suspect': False, 'rows': [], 'http_status': None}
    for info in root.findall('.//measInfo'):
        gran = info.find('granPeriod')
        if gran is not None:
            report['end_time'] = gran.get('endTime')
            duration = re.fullmatch(r'PT(\d+)S', gran.get('duration', ''))
            report['duration_sec'] = int(duration[1]) if duration else None
        names = {n.get('p'): n.text for n in info.findall('measType')}
        for value in info.findall('measValue'):
            suspect = value.findtext('suspect', 'false').lower() == 'true'
            report['suspect'] = report['suspect'] or suspect
            report['rows'].append({'object': value.get('measObjLdn', ''), 'suspect': suspect,
                                   'metrics': {names[r.get('p')]: number(r.text) for r in value.findall('r') if r.get('p') in names}})
    return report


def ves_events(raw: str, since_ms: int = 0, run_id: str = '') -> list[dict]:
    """Read logged outgoing events plus their following HTTP response, without secrets."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', raw)
    decoder = json.JSONDecoder()
    events = {}
    for match in re.finditer(r'\{\s*"event"\s*:', text):
        try:
            obj, end = decoder.raw_decode(text, match.start())
            event = obj['event']
            header = event.get('commonEventHeader') or {}
            data = (event.get('stndDefinedFields') or {}).get('data') or {}
            at_ms = int(header.get('lastEpochMicrosec') or header.get('startEpochMicrosec') or 0) // 1000
            if at_ms < since_ms:
                continue
            kind = data.get('notificationType') or header.get('domain', '')
            extra = data.get('additionalInformation') or {}
            if run_id and isinstance(extra, dict) and extra.get('runId') and extra['runId'] != run_id:
                continue
            following = re.split(r'\{\s*"event"\s*:', text[end:end + 500], maxsplit=1)[0]
            response = re.search(r'response_code\s*=\s*(\d+)', following)
            row = {'id': str(header.get('eventId') or f"{header.get('sourceName')}:{kind}:{at_ms}"),
                   'at': datetime.fromtimestamp(at_ms / 1000, timezone.utc).isoformat(),
                   'at_ms': at_ms, 'kind': kind, 'managed_element': header.get('sourceName', ''),
                   'http_status': int(response[1]) if response else None}
            if kind == 'notifyFileReady':
                files = data.get('fileInfoList') or []
                row['filename'] = PurePosixPath(str(files[0].get('fileLocation', ''))).name if files else ''
            if kind in ('notifyNewAlarm', 'notifyClearedAlarm', 'notifyChangedAlarm'):
                row.update({key: data.get(key) for key in ('alarmId', 'objectInstance', 'perceivedSeverity',
                                                          'alarmType', 'probableCause', 'specificProblem')})
            events[(row['id'], at_ms)] = row
        except (ValueError, TypeError, KeyError, OverflowError, IndexError):
            continue
    return sorted(events.values(), key=lambda e: (e['at_ms'], e['id']))
