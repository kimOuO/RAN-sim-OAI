"""Run-scoped O1 monitoring. Reads CM/FM from sysrepo and PM XML from SFTP files.

Only sanitized observations are retained; raw VES payloads contain credentials.
Container health and VES acceptance are never treated as SMO ingestion evidence.
"""
from __future__ import annotations

import io
import json
import re
import tarfile
import tempfile
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path

import docker
from django.conf import settings

from .o1_payloads import cm_document, epoch_ms, number, pm_document, public_url, ves_events


def _now():
    return datetime.now(timezone.utc).isoformat()


def _directory(run_uuid):
    if not re.fullmatch(r'[\w-]+', run_uuid, flags=re.ASCII):
        raise ValueError('Invalid run identifier')
    return Path(settings.PER_RUN_LOG_DIR) / run_uuid[-8:] / 'o1'


def _scope(run_uuid, tree, directory):
    run = (tree or {}).get('run') or {}
    since = epoch_ms(run.get('started_at')) or 0
    latest = {}
    registry = directory.parent.parent / '_o1_run_registry.jsonl'
    if registry.exists():
        with registry.open(encoding='utf-8') as records:
            for line in records:
                try:
                    rec = json.loads(line)
                    if rec.get('event') == 'start' and rec.get('scene_run_uuid') == run_uuid and (epoch_ms(rec.get('ts')) or 0) >= since:
                        latest = rec
                except (ValueError, TypeError):
                    continue
    return {'run_id': latest.get('runId', ''), 'started_at': run.get('started_at') or latest.get('ts'),
            'stopped_at': run.get('stopped_at'), 'scenario_id': latest.get('scenarioId', ''), 'mes': latest.get('mes', [])}


def _inventory(c):
    env = dict(e.split('=', 1) for e in (c.attrs.get('Config') or {}).get('Env', []) if '=' in e)
    state = c.attrs.get('State') or {}
    return {'name': c.name, 'role': c.labels.get('ransim.role', ''), 'status': c.status,
            'gnb': c.labels.get('ransim.gnb', ''), 'meid': c.labels.get('ransim.meid', ''),
            'managed_element': env.get('O1_NODE_ID', ''), 'unit_type': env.get('O1_UNIT_TYPE', ''),
            'host': env.get('O1_HOST', ''), 'netconf_port': env.get('O1_NETCONF_PORT', ''),
            'sftp_port': env.get('O1_SFTP_PORT', ''), 'ves_url': public_url(env.get('O1_VES_URL', '')),
            'pm_interval_sec': env.get('O1_PM_INTERVAL', ''), 'run_id': env.get('O1_RUN_ID', ''),
            'started_at': state.get('StartedAt'), 'restart_count': c.attrs.get('RestartCount', 0)}


def _adapter(c, row, since_ms, observed_at):
    result = {'cm': None, 'files': [], 'events': [], 'warnings': []}
    me = row['managed_element']
    try:
        result['events'] = ves_events(c.logs(tail=5000).decode('utf-8', 'replace'), since_ms, row['run_id'])
    except Exception:
        result['warnings'].append(f'{me}：VES 傳送紀錄暫時無法讀取')
    if row['status'] != 'running':
        return result
    try:
        response = c.exec_run(['timeout', '3', 'sysrepocfg', '--export', '--datastore=operational',
                               '--module=_3gpp-common-managed-element', '--format=xml'])
        if response.exit_code != 0:
            raise ValueError('sysrepo export failed')
        result['cm'] = cm_document(response.output, me, row['gnb'], row['unit_type'], observed_at)
    except Exception:
        result['warnings'].append(f'{me}：O1 組態與目前告警暫時無法讀取')
    try:
        chunks, _ = c.get_archive('/ftp')
        parts, size = [], 0
        for chunk in chunks:
            size += len(chunk)
            if size > 8 * 1024 * 1024:
                raise ValueError('PM archive size limit')
            parts.append(chunk)
        with tarfile.open(fileobj=io.BytesIO(b''.join(parts))) as archive:
            members = sorted((m for m in archive.getmembers() if m.isfile() and m.name.endswith('.xml') and m.size < 1024 * 1024), key=lambda m: m.name)[-96:]
            for member in members:
                try:
                    report = pm_document(archive.extractfile(member).read(), member.name, me, row['run_id'])
                    if (epoch_ms(report['end_time']) or 0) >= since_ms:
                        result['files'].append(report)
                except (ValueError, TypeError, ET.ParseError):
                    continue
    except Exception:
        result['warnings'].append(f'{me}：PM XML 檔案暫時無法讀取')
    return result


def _save(directory, run_id, data):
    if not run_id or not re.fullmatch(r'[\w-]+', run_id, flags=re.ASCII):
        return
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f'observation_{run_id}.json'
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=directory, delete=False) as f:
        json.dump(data, f, ensure_ascii=False)
        tmp = Path(f.name)
    tmp.replace(target)


def _scene_cm(tree):
    """Current scene fallback, explicitly separate from historical O1 observations."""
    if not tree:
        return []
    nodes = {n.get('node_id'): n for n in (tree.get('run') or {}).get('e2_nodes') or []}
    out = []
    for g in tree.get('gnbs') or []:
        me = nodes.get(g.get('name'), {}).get('meid') or g.get('name', '')
        for d in g.get('dus') or []:
            el = {'managed_element': f"{me}_du{d.get('gnb_du_id') or 1}", 'gnb': g.get('name', ''),
                  'unit_type': 'DU', 'source': 'scene', 'observed_at': None, 'vendor': None,
                  'software_version': None, 'cells': [], 'jobs': [], 'alarms': []}
            config = {**(d.get('config_template') or {}), **(d.get('config_override') or {})}
            for c in d.get('cells') or []:
                el['cells'].append({'dn': c.get('name'), 'kind': 'NRCellDU', 'local_cell_id': c.get('local_cell_id'),
                                    'nRPCI': c.get('pci'), 'nRTAC': c.get('tac'), 'arfcnDL': c.get('arfcn'),
                                    'bSChannelBwDL': c.get('bandwidth_mhz'), 'bSChannelBwUL': c.get('bandwidth_mhz'),
                                    'numberOfRBs': config.get('n_prb'), 'plmn': [f"{g.get('plmn_mcc', '')}/{g.get('plmn_mnc', '')}"],
                                    'administrativeState': None, 'operationalState': None, 'cellState': None})
            out.append(el)
    return out


def _dt_trend(run_uuid, since_ms):
    from main.apps.run_telemetry_archive.models.run_kpm_sample import RunKpmSample
    from main.apps.run_telemetry_archive.services.business.run_seq_filter import apply_run_seq
    qs = apply_run_seq(RunKpmSample.objects.filter(f_scene_run_uuid=run_uuid), RunKpmSample, run_uuid, None)
    if since_ms:
        qs = qs.filter(wall_time_ms__gte=since_ms)
    records = list(qs.order_by('-window_index').values('sim_time_ms', 'wall_time_ms', 'per_cell', 'per_ue')[:900])
    records.reverse()
    stride = max(1, (len(records) + 239) // 240)
    selected = records[::stride]
    if records and (not selected or selected[-1] is not records[-1]):
        selected.append(records[-1])
    trend = []
    for rec in selected:
        cells = {cell: {'cell_id': cell, 'connected_ues': 0, 'throughput_dl_mbps': 0.0, 'throughput_ul_mbps': 0.0,
                        'prb_pct_dl': number(val.get('prb_pct_dl'))} for cell, val in (rec['per_cell'] or {}).items()}
        for ue in (rec['per_ue'] or {}).values():
            cell = cells.get(ue.get('serving_cell'))
            if cell is None or ue.get('attached') is False:
                continue
            cell['connected_ues'] += 1
            for key in ('throughput_dl_mbps', 'throughput_ul_mbps'):
                cell[key] += number(ue.get(key)) or 0
        for cell_id, cell in cells.items():
            reported_count = number(rec['per_cell'][cell_id].get('connected_ues'))
            if reported_count is not None:
                cell['connected_ues'] = reported_count
        trend.append({'at_sim_ms': rec['sim_time_ms'], 'wall_time_ms': rec['wall_time_ms'], 'cells': list(cells.values())})
    return trend


def read_o1(scene_run_uuid: str, tree: dict | None = None, include_trend: bool = True) -> dict:
    directory = _directory(scene_run_uuid)
    observed_at = _now()
    scope = _scope(scene_run_uuid, tree, directory)
    since_ms = epoch_ms(scope['started_at']) or 0
    rows, details, warnings = [], [], []
    try:
        with closing(docker.from_env(timeout=5)) as client:
            containers = [c for c in client.containers.list(all=True, filters={'label': f'ransim.scene_run_uuid={scene_run_uuid}'})
                          if c.labels.get('ransim.role') in ('o1adapter', 'o1facade')]
            rows = [_inventory(c) for c in containers]
            adapters = [(c, r) for c, r in zip(containers, rows) if r['role'] == 'o1adapter']
            if adapters:
                scope['run_id'] = adapters[0][1]['run_id'] or scope['run_id']
                with ThreadPoolExecutor(max_workers=4) as pool:
                    details = list(pool.map(lambda pair: _adapter(*pair, since_ms, observed_at), adapters))
    except Exception:
        warnings.append('O1 服務狀態暫時無法讀取；以下保留可取得的歷史資料。')
    elements = [d['cm'] for d in details if d['cm']]
    files = [f for d in details for f in d['files']]
    events = [e for d in details for e in d['events']]
    warnings.extend(w for d in details for w in d['warnings'])
    captured_at, historical = (observed_at if elements else None), False
    run_id, saved = scope['run_id'], {}
    if run_id and re.fullmatch(r'[\w-]+', run_id, flags=re.ASCII):
        try:
            saved = json.loads((directory / f'observation_{run_id}.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
    if saved.get('scene_run_uuid') == scene_run_uuid:
        files = saved.get('files', []) + files
        events = saved.get('events', []) + events
        current_mes = {el['managed_element'] for el in elements}
        missing = [el for el in saved.get('elements', []) if el['managed_element'] not in current_mes]
        if missing:
            elements += missing
            captured_at = captured_at or saved.get('captured_at')
            historical = True
        if not rows:
            rows = [{**r, 'status': 'removed'} for r in saved.get('containers', [])]
    if not any(r['status'] == 'running' for r in rows):
        for path in directory.parent.glob('o1adapter-*.log'):
            if path.stat().st_mtime * 1000 < since_ms:
                continue
            with path.open('rb') as f:
                f.seek(max(0, path.stat().st_size - 2 * 1024 * 1024))
                events.extend(ves_events(f.read().decode('utf-8', 'replace'), since_ms, run_id))
    if run_id and re.fullmatch(r'[\w-]+', run_id, flags=re.ASCII):
        ledger = directory / f'delivery_{run_id}.jsonl'
        if ledger.exists():
            with ledger.open(encoding='utf-8') as records:
                for line in records:
                    try:
                        event = json.loads(line)
                        if event['at_ms'] >= since_ms:
                            events.append(event)
                    except (ValueError, TypeError, KeyError):
                        continue
    event_map = {(e['id'], e['at_ms']): e for e in events}
    events = sorted(event_map.values(), key=lambda e: (e['at_ms'], e['id']))[-2000:]
    file_map = {}
    for report in files:
        key = (report['managed_element'], report['filename'])
        previous = file_map.get(key, {})
        file_map[key] = {**previous, **report,
                         'http_status': report.get('http_status') if report.get('http_status') is not None else previous.get('http_status')}
    for event in events:
        if event['kind'] != 'notifyFileReady' or not event.get('filename'):
            continue
        report = file_map.setdefault((event['managed_element'], event['filename']),
                                    {'filename': event['filename'], 'managed_element': event['managed_element'],
                                     'source': 'ves_log', 'end_time': event['at'], 'duration_sec': None,
                                     'suspect': None, 'rows': []})
        report['http_status'] = event['http_status']
    files = sorted(file_map.values(), key=lambda f: (f.get('end_time') or '', f['filename']))[-384:]
    if details:
        try:
            _save(directory, run_id, {'scene_run_uuid': scene_run_uuid, 'captured_at': captured_at,
                                      'elements': elements, 'containers': rows, 'files': files, 'events': events})
        except OSError:
            warnings.append('O1 歷史快照暫時無法保存')
    live_elements = {d['cm']['managed_element'] for d in details if d['cm']}
    active = [{**a, 'managed_element': el['managed_element']} for el in elements if el['managed_element'] in live_elements
              for a in el['alarms'] if a.get('perceivedSeverity') not in (None, 'CLEARED', 'NORMAL')]
    alarm_events = [e for e in events if e['kind'] in ('notifyNewAlarm', 'notifyClearedAlarm', 'notifyChangedAlarm')]
    trend = []
    if include_trend:
        try:
            trend = _dt_trend(scene_run_uuid, since_ms)
        except Exception:
            warnings.append('DT 效能量測暫時無法讀取')
    adapters = [r for r in rows if r['role'] == 'o1adapter']
    expected_mes = {me for g in scope['mes'] for me in
                    [g['cucp'], *[d['me'] for d in g.get('dus') or [{'me': g['du']}]]]}
    current_verified = bool(adapters) and len(live_elements) == len(adapters) and expected_mes.issubset(live_elements)
    return {'scene_run_uuid': scene_run_uuid, 'observed_at': observed_at, 'scope': scope,
            'containers': sorted(rows, key=lambda r: (r['gnb'], r['name'])), 'smo_receipt_verified': False,
            'warnings': warnings, 'pm': {'trend': trend, 'files': files, 'trend_source': 'dt_archive'},
            'cm': {'source': ('snapshot' if historical else 'o1') if elements else 'scene',
                   'observed_at': captured_at, 'elements': elements or _scene_cm(tree)},
            'fm': {'current_verified': current_verified,
                   'observed_at': captured_at, 'active': active, 'events': alarm_events}, 'notifications': events[-200:]}


def snapshot_before_stop(rid: str):
    """Capture before teardown, including when nobody has opened the page."""
    with closing(docker.from_env(timeout=5)) as client:
        for c in client.containers.list(filters={'label': 'ransim.role=o1adapter'}):
            if f'-{rid}-' in c.name:
                run_uuid = c.labels.get('ransim.scene_run_uuid')
                if run_uuid:
                    read_o1(run_uuid, include_trend=False)
                return


def record_delivery(rid: str, run_id: str, event: dict, http_status: int | None):
    """Retain orchestrator clear/deletion evidence after adapters have stopped."""
    if not re.fullmatch(r'[\w-]+', run_id, flags=re.ASCII):
        return
    directory = _directory(rid)
    directory.mkdir(parents=True, exist_ok=True)
    response = f' response_code = {http_status}' if http_status is not None else ''
    records = ves_events(json.dumps(event) + response)
    with (directory / f'delivery_{run_id}.jsonl').open('a', encoding='utf-8') as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + '\n')
