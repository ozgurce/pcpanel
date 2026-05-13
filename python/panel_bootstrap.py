import asyncio
import aiohttp
import os
import time
from panel_globals import (
    SETTINGS_SNAPSHOT, 
    SETTINGS_SNAPSHOT_LOCK, 
    SETTINGS_SNAPSHOT_TTL_SECONDS,
    NO_CACHE_HEADERS
)
from settings_runtime import load_settings

def refresh_runtime_settings_snapshot(force=False):
    """Creates one short-lived snapshot for loops that read settings frequently."""
    now = time.time()
    with SETTINGS_SNAPSHOT_LOCK:
        data = SETTINGS_SNAPSHOT.get("data")
        last_refresh = float(SETTINGS_SNAPSHOT.get("last_refresh") or 0.0)

        if (not force) and isinstance(data, dict) and (now - last_refresh) < SETTINGS_SNAPSHOT_TTL_SECONDS:
            return data

        try:
            data = load_settings(force_reload=force)
            if not isinstance(data, dict):
                data = {}
            SETTINGS_SNAPSHOT["data"] = data
            SETTINGS_SNAPSHOT["last_refresh"] = now
            return data
        except Exception:
            return data if isinstance(data, dict) else {}

def _get_runtime_setting_cached(path, default=None):
    try:
        node = refresh_runtime_settings_snapshot(False)
        for part in str(path).split('.'):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node
    except Exception:
        return default

def _get_setting_str(path, default=""):
    value = _get_runtime_setting_cached(path, default)
    if value is None:
        return str(default or "")
    return str(value)

def _get_setting_int(path, default=0):
    try:
        return int(float(_get_runtime_setting_cached(path, default)))
    except Exception:
        return int(default)

def _get_setting_float(path, default=0.0):
    try:
        return float(_get_runtime_setting_cached(path, default))
    except Exception:
        return float(default)

def _get_setting_bool(path, default=False):
    value = _get_runtime_setting_cached(path, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "evet"}
    return bool(value)

def _get_window_str(path, default=""):
    return _get_setting_str(f"window.{path}", default)

def _get_window_bool(path, default=False):
    return _get_setting_bool(f"window.{path}", default)

def _get_window_int(path, default=0):
    return _get_setting_int(f"window.{path}", default)

def _get_window_monitor_device():
    return _get_window_str("target_monitor_device", "")

def _get_performance_int(path, default=0):
    return _get_setting_int(f"performance.{path}", default)

def _get_performance_interval_seconds(path, default_ms=1000, min_ms=50):
    value_ms = _get_performance_int(path, default_ms)
    try:
        value_ms = max(float(min_ms), float(value_ms))
    except Exception:
        value_ms = float(default_ms)
    return value_ms / 1000.0

def _get_fps_refresh_interval_seconds():
    return _get_performance_interval_seconds("fps_refresh_interval_ms", 500, 50)

def _get_hwinfo_worker_refresh_interval_seconds():
    return min(
        _get_performance_interval_seconds("hwinfo_refresh_interval_ms", 500, 100),
        _get_fps_refresh_interval_seconds(),
    )

def _get_weather_refresh_interval_seconds():
    minutes = _get_setting_float("performance.weather_refresh_interval_minutes", 30.0)
    return max(60.0, minutes * 60.0)

def _get_shift_share_url():
    return _get_setting_str("api.shift.share_url", "")

def _get_shift_sheet_name():
    return _get_setting_str("api.shift.sheet_name", "Shift")

def _get_shift_employee_name():
    return _get_setting_str("api.shift.employee_name", "")

def _get_shift_name_column():
    return _get_setting_int("api.shift.name_column", 3)

def _get_shift_date_row():
    return _get_setting_int("api.shift.date_row", 2)

def _get_meteo_latitude():
    return _get_setting_float("api.meteo.latitude", 0.0)

def _get_meteo_longitude():
    return _get_setting_float("api.meteo.longitude", 0.0)

def _get_meteo_location_label():
    return _get_setting_str("api.meteo.location_label", "")

def _get_meteo_location_query():
    return _get_setting_str("api.meteo.location_query", "")

def _get_meteo_geocoding_url():
    return _get_setting_str("api.meteo.geocoding_url", "https://geocoding-api.open-meteo.com/v1/search")

def _get_meteo_language():
    return _get_setting_str("api.meteo.language", "en")

def _get_meteo_forecast_url():
    return _get_setting_str("api.meteo.forecast_url", "https://api.open-meteo.com/v1/forecast")

def _get_meteo_timezone():
    return _get_setting_str("api.meteo.timezone", "auto")

def _get_keep_window_alive_min_interval_seconds():
    return _get_performance_interval_seconds("keep_window_alive_min_interval_ms", 250, 100)

def _get_network_refresh_interval_seconds():
    return _get_performance_interval_seconds("network_refresh_interval_ms", 5000, 500)

def restore_default_process_scheduling(include_children=False):
    pass

def _write_fallback_startup_error(e):
    from panel_globals import ERR_FILE
    try:
        with open(ERR_FILE, "a", encoding="utf-8") as f:
            f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] CRITICAL STARTUP ERROR: {e}\n")
    except Exception:
        pass

from panel_globals import HTTP_SESSIONS_BY_LOOP, HTTP_SESSION_LOCK

def _get_shared_http_session(name='default'):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return None
    with HTTP_SESSION_LOCK:
        sessions = HTTP_SESSIONS_BY_LOOP.get(loop)
        if sessions is None:
            sessions = {}
            HTTP_SESSIONS_BY_LOOP[loop] = sessions
        session = sessions.get(name)
        if session is None or session.closed:
            connector = aiohttp.TCPConnector(limit=20, ttl_dns_cache=300)
            session = aiohttp.ClientSession(connector=connector)
            sessions[name] = session
        return session

async def _close_shared_http_sessions(_app=None):
    try: loop = asyncio.get_running_loop()
    except RuntimeError: return
    with HTTP_SESSION_LOCK:
        sessions = HTTP_SESSIONS_BY_LOOP.pop(loop, {})
    for session in list(sessions.values()):
        try:
            if session and not session.closed: await session.close()
        except Exception: pass

__all__ = [name for name in globals() if not name.startswith("__")]
