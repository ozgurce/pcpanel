import os
import threading
import time
import json
import hmac
import hashlib
import urllib.parse
import urllib.request
import asyncio
from aiohttp import web

from panel_globals import (
    BASE_DIR, SENSOR_CACHE_LOCK, SYSTEM_CACHE, PC_PLUG_QUERY_CACHE,
    PC_PLUG_QUERY_INTERVAL_SECONDS, RUNTIME_THREADS_LOCK, RUNTIME_THREADS_STARTED
)
from panel_bootstrap import (
    _get_runtime_setting_cached, _get_setting_int, _get_setting_float,
    _get_setting_bool, NO_CACHE_HEADERS
)
from panel_logging import log_error, log_tuya, log_tuya_error
from panel_runtime_helpers import safe_execute

# Tuya Runtime imports
from tuya_runtime import (
    init_tuya_runtime, get_recent_tuya_logs, tuya_public_devices_payload,
    get_tuya_devices_config, tuya_updater_loop, tuya_get_device_status,
    refresh_tuya_cache_once, tuya_get_cached_devices, tuya_get_cached_device,
    tuya_update_cached_device, tuya_forget_device, get_tuya_cloud_settings,
    tuya_reload_devices_and_pool, tuya_toggle_device_fast,
    tuya_set_device_brightness_fast, log_tuya_event
)

PC_PLUG_CLOUD_CACHE = {"ts": 0.0, "power_w": None, "status": None, "error": None, "source": None}
PC_PLUG_CLOUD_QUERY_INTERVAL_SECONDS = 60.0

def _safe_float(v):
    try: return float(v) if v is not None and v != "" else None
    except Exception: return None

def _extract_tuya_cur_power_w(device):
    if not isinstance(device, dict): return None
    for key in ("cur_power", "power_w", "power", "watt", "watts"):
        val = _safe_float(device.get(key))
        if val is not None: return round(val, 1)
    return None

def _get_pc_plug_device_key():
    return str(_get_runtime_setting_cached("tuya.pc_plug_key", "")).strip()

def _get_pc_plug_power_w():
    live_power = _safe_float((PC_PLUG_QUERY_CACHE or {}).get("power_w"))
    if live_power is not None and live_power > 0:
        return round(live_power, 1)

    # Query on demand. The PC plug is intentionally excluded from the normal
    # visible Tuya device polling, so the power card must refresh it here.
    try:
        info = _query_pc_plug_status_unified(force=False)
        live_power = _safe_float((info or {}).get("power_w"))
        if live_power is not None and live_power > 0:
            return round(live_power, 1)
    except Exception as e:
        try:
            PC_PLUG_QUERY_CACHE.update({"ts": time.time(), "error": str(e)})
        except Exception:
            pass

    # Last fallback: if a cached public device already contains watt data, use it.
    try:
        pc_key = _get_pc_plug_device_key().strip().lower()
        devices = SYSTEM_CACHE.get("tuya_devices") or []
        for device in devices:
            if not isinstance(device, dict):
                continue
            key = str(device.get("key") or device.get("id") or "").strip().lower()
            if pc_key and key != pc_key:
                continue
            power = _extract_tuya_cur_power_w(device)
            if power is not None and power > 0:
                PC_PLUG_QUERY_CACHE.update({"ts": time.time(), "power_w": power, "source": "cached_device"})
                return round(power, 1)
    except Exception:
        pass

    return None

@safe_execute("tuya")
def _query_pc_plug_status_unified(force=False):
    now_ts = time.time()
    if (not force) and (now_ts - float(PC_PLUG_QUERY_CACHE.get("ts", 0)) < PC_PLUG_QUERY_INTERVAL_SECONDS):
        return PC_PLUG_QUERY_CACHE

    device_key = _get_pc_plug_device_key()
    if not device_key: return PC_PLUG_QUERY_CACHE

    try:
        payload = tuya_get_device_status(device_key)
        power_w = _extract_tuya_cur_power_w(payload)
        PC_PLUG_QUERY_CACHE.update({"ts": now_ts, "power_w": power_w})
        return PC_PLUG_QUERY_CACHE
    except Exception as e:
        log_error(f"Tuya PC plug query error: {e}")
        return PC_PLUG_QUERY_CACHE

def start_runtime_threads():
    global RUNTIME_THREADS_STARTED
    from panel_hwinfo_process import ensure_worker_processes_running
    from panel_hwinfo_reader import hwinfo_cache_reader_loop
    with RUNTIME_THREADS_LOCK:
        if RUNTIME_THREADS_STARTED: return
        RUNTIME_THREADS_STARTED = True

    ensure_worker_processes_running()
    threading.Thread(target=hwinfo_cache_reader_loop, daemon=True).start()

init_tuya_runtime(SYSTEM_CACHE, SENSOR_CACHE_LOCK, log_tuya, log_tuya, os.path.join(BASE_DIR, "json", "devices.json"))

__all__ = [name for name in globals() if not name.startswith("__")]
