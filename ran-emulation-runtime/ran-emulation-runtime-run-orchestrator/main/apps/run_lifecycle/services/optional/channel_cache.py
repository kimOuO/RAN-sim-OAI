"""場景有沒有預算好的通道快取(2026-09-28)。

「有沒有預算」是場景的屬性、不是場次狀態:快取檔 `<legacy_scenario_id 或 scene_uuid>.npz`
在共用的 channel_cache 目錄裡(DU / RU 以同一個 scenario id 載入)。以前前端只看 registry 的
cache_path,但從舊劇本匯入的場景有檔案、cache_path 卻是空的 —— 以檔案為準。
"""
from __future__ import annotations

import os
import ast
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

from django.conf import settings

CACHE_DIR = getattr(settings, "PRECOMPUTE_LOG_DIR", "/data/channel_cache")   # orchestrator 內的掛載點
CACHE_DIR_IN_RAN = "/app/data/channel_cache"                                  # registry cache_path 慣用的寫法


def scenario_id(scene: dict) -> str:
    return str((scene or {}).get("legacy_scenario_id") or (scene or {}).get("scene_uuid") or "")


def available(scene: dict) -> bool:
    sid = scenario_id(scene)
    return bool(sid) and os.path.isfile(os.path.join(CACHE_DIR, f"{sid}.npz"))


def cache_path_for(scene: dict) -> str:
    return f"{CACHE_DIR_IN_RAN}/{scenario_id(scene)}.npz"


def fingerprint(tree: dict) -> str:
    """Only physical inputs; status, UUID timestamps, traffic and A3 do not invalidate RT."""
    def clean(value):
        if isinstance(value, dict):
            return {k: clean(v) for k, v in value.items() if k not in {
                'id', 'status', 'traffic', 'active_windows', 'presence_restricted', 'config_template',
                'neighbor_seeds', 'run', 'knobs', 'description', 'category', 'e2_block', 'e2_index',
                'a3_enabled', 'a3_offset_db', 'a3_hys_db', 'a3_ttt_ms',
            } and not k.endswith(('_created_at', '_updated_at', '_uuid'))}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    physical = {k: tree.get(k) for k in ('scene', 'gnbs', 'ues', 'buildings')}
    run = tree.get('run') or {}
    physical['timing'] = {k: run.get(k) for k in ('duration_sec', 'sim_dt_ms')}
    return hashlib.sha256(json.dumps(clean(physical), sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def _npy_header(stream):
    if stream.read(6) != b'\x93NUMPY':
        raise ValueError('invalid npy magic')
    version = stream.read(2)
    length_size = 2 if version[0] == 1 else 4
    length = int.from_bytes(stream.read(length_size), 'little')
    if length > 65536:
        raise ValueError('invalid npy header length')
    return ast.literal_eval(stream.read(length).decode('latin1'))


def inspect_cache(tree: dict) -> dict:
    """Read bounded NPY headers/scalars without loading channel arrays or pickle."""
    sid = scenario_id(tree.get('scene') or {})
    path = Path(CACHE_DIR) / f'{sid}.npz'
    if not sid or not path.is_file():
        return {'available': False, 'valid': False, 'reason': '尚未預算通道快取'}
    result = {'available': True, 'valid': False, 'reason': ''}
    try:
        with zipfile.ZipFile(path) as z:
            scalars = {}
            for name in ('duration_sec', 'tick_ms', 'total_ticks'):
                with z.open(name + '.npy') as f:
                    header = _npy_header(f)
                    fmt = {'<f4': '<f', '<f8': '<d', '<i4': '<i', '<i8': '<q'}.get(header['descr'])
                    if header['shape'] != () or fmt is None:
                        raise ValueError(f'invalid scalar {name}')
                    scalars[name] = struct.unpack(fmt, f.read(struct.calcsize(fmt)))[0]
            with z.open('path_gain_db.npy') as f:
                shape = _npy_header(f)['shape']
        if not all(math.isfinite(float(v)) for v in scalars.values()) or scalars['tick_ms'] <= 0 or scalars['total_ticks'] <= 0:
            raise ValueError('invalid cache timing')
        result.update(scalars)
        if len(shape) != 3 or shape[0] != scalars['total_ticks']:
            raise ValueError('cache shape does not match total_ticks')
        run = tree.get('run') or {}
        required = float(run.get('duration_sec') or 0)
        coverage = min(scalars['duration_sec'], scalars['tick_ms'] * scalars['total_ticks'] / 1000)
        if coverage + 1e-3 < required:
            raise ValueError(f'快取只有 {coverage:g} 秒，Run 需要 {required:g} 秒；請重新預算')
        if shape[1] != len(tree.get('ues') or []):
            raise ValueError('UE 數量已變更，請重新預算')
        manifest = path.with_suffix('.manifest.json')
        if manifest.is_file():
            meta = json.loads(manifest.read_text())
            if meta.get('fingerprint') != fingerprint(tree):
                raise ValueError('場景、路徑或預算設定已變更，請重新預算')
            if meta.get('cache_size') != path.stat().st_size:
                raise ValueError('快取內容與版本紀錄不符，請重新預算')
        elif not (tree.get('scene') or {}).get('legacy_scenario_id'):
            raise ValueError('快取缺少場景版本紀錄，請重新預算')
        result['valid'] = True
    except (OSError, ValueError, KeyError, TypeError, IndexError, SyntaxError, struct.error, zipfile.BadZipFile) as exc:
        result['reason'] = str(exc)
    return result
