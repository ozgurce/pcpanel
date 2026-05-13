# File Version: 1.0
import argparse
import asyncio
import json
import os
import sys
import time
from monitorcontrol import get_monitors
from aiohttp import web

TARGET_FINGERPRINT = 'RTK|LCD|2.2|1,15,16,17,18,3,4|11,12,135,16,172,174,178,18,182,198,2,20,200,202,204,214,22,223,24,253,255,26,4,5,6,8,82,96|1,12,2,227,243,3,7'

PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PYTHON_DIR)
JSON_DIR = os.path.join(BASE_DIR, "json")
STATE_PATH = os.path.join(JSON_DIR, 'monitor_power_state.json')
_MONITOR_ROUTES_REGISTERED = False

POWER_ON = 1
POWER_OFF = 4

def _get_no_cache_headers():
    from panel_globals import NO_CACHE_HEADERS
    return NO_CACHE_HEADERS

def _load_state():
    if not os.path.exists(STATE_PATH): return {}
    try:
        with open(STATE_PATH, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception: return {}

def _save_state(data):
    tmp = STATE_PATH + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, STATE_PATH)

def _caps_to_safe(caps):
    if not isinstance(caps, dict): return {}
    def keys_of(name):
        v = caps.get(name)
        return sorted([str(k) for k in v.keys()]) if isinstance(v, dict) else []
    return {
        'model': str(caps.get('model') or ''),
        'type': str(caps.get('type') or ''),
        'mccs_ver': str(caps.get('mccs_ver') or ''),
        'inputs': sorted([str(x) for x in caps.get('inputs', [])]) if isinstance(caps.get('inputs'), list) else [],
        'vcp_keys': keys_of('vcp'),
        'cmd_keys': keys_of('cmds'),
    }

def _fingerprint(info):
    return '|'.join([info.get('model', ''), info.get('type', ''), info.get('mccs_ver', ''), ','.join(info.get('inputs', [])), ','.join(info.get('vcp_keys', [])), ','.join(info.get('cmd_keys', []))])

def _read_monitor_info(monitor):
    try:
        with monitor: caps = monitor.get_vcp_capabilities()
    except Exception: caps = {}
    info = _caps_to_safe(caps)
    info['fingerprint'] = _fingerprint(info)
    info['ddc'] = bool(caps)
    return info

def _get_all():
    return [(i, m, _read_monitor_info(m)) for i, m in enumerate(get_monitors())]

def _find_target():
    rows = _get_all()
    matches = [r for r in rows if r[2].get('fingerprint') == TARGET_FINGERPRINT]
    if len(matches) == 1: return matches[0]
    raise RuntimeError('Target monitor not found or multiple matches.')

def get_target_status_payload():
    rows = _get_all()
    monitors = []
    target = None
    for _, _, info in rows:
        info['target'] = info.get('fingerprint') == TARGET_FINGERPRINT
        monitors.append(info)
        if info['target']: target = info
    return {'ok': True, 'target_found': target is not None, 'monitors': monitors, 'target': target}

def set_power(mode):
    _, monitor, _ = _find_target()
    try:
        with monitor: monitor.set_power_mode(mode)
        return {'ok': True, 'action': 'power', 'mode': 'on' if mode == POWER_ON else 'off'}
    except Exception as e: return {'ok': False, 'error': str(e)}

async def api_monitor_status(_r):
    try: return web.json_response(await asyncio.to_thread(get_target_status_payload), headers=_get_no_cache_headers())
    except Exception as e: return web.json_response({'ok': False, 'error': str(e)}, status=500)

async def api_monitor_on(_r):
    res = await asyncio.to_thread(set_power, POWER_ON)
    return web.json_response(res, headers=_get_no_cache_headers())

async def api_monitor_off(_r):
    res = await asyncio.to_thread(set_power, POWER_OFF)
    return web.json_response(res, headers=_get_no_cache_headers())

def register_monitor_routes():
    global _MONITOR_ROUTES_REGISTERED
    if _MONITOR_ROUTES_REGISTERED: return
    try:
        from panel_routes_window_main import app as app_obj
    except ImportError:
        return
    routes = [
        ('GET', '/monitor/status', api_monitor_status),
        ('POST', '/monitor/on', api_monitor_on),
        ('POST', '/monitor/off', api_monitor_off),
    ]
    for m, p, h in routes:
        try: app_obj.router.add_route(m, p, h)
        except Exception: pass
    _MONITOR_ROUTES_REGISTERED = True

if __name__ == '__main__': pass
