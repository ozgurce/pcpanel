# File Version: 1.1
import json
import os
import re
import threading
from copy import deepcopy

PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PYTHON_DIR)
JSON_DIR = os.path.join(BASE_DIR, 'json')
PLUGINS_DIR = os.path.join(BASE_DIR, 'plugins')
SETTINGS_PATH = os.path.join(JSON_DIR, 'settings.json')
SETTINGS_LOCK = threading.RLock()

DEFAULT_SETTINGS = {
    "performance": {
        "ui_update_interval_ms": 250,
        "websocket_broadcast_interval_ms": 250,
        "status_poll_interval_ms": 500,
        "hwinfo_refresh_interval_ms": 1000,
        "hwinfo_cache_read_interval_ms": 500,
        "media_refresh_interval_ms": 500,
        "volume_refresh_interval_ms": 250,
        "mute_refresh_interval_ms": 250,
        "fps_refresh_interval_ms": 500,
        "weather_refresh_interval_minutes": 30,
        "shift_cache_check_interval_minutes": 30,
        "network_refresh_interval_ms": 5000,
        "uptime_refresh_interval_ms": 5000,
        "tuya_refresh_interval_ms": 5000,
        "tuya_retry_count": 1
    },
    "frontend": {
        "panel_language": "en",
        "seekbar_update_interval_ms": 250,
        "lyrics_refresh_interval_ms": 1000,
        "idle_text": "nihil infinitum est | el. psy. congroo",
        "hide_seekbar_when_idle": True,
        "show_fps_card": True,
        "show_date_weather_block": True,
        "show_tuya_card": True,
        "show_now_playing_card": True,
        "show_lyrics_card": True,
        "show_media_progress_when_idle": False,
        "liquid_animation_enabled": True,
        "liquid_animation_fps": 16,
        "liquid_animation_mode": "light",
        "liquid_wave_when_idle": False,
        "settings_liquid_live_preview_enabled": True,
        "settings_visual_effects_enabled": True,
        "liquid_theme_cpu": "default_glass",
        "liquid_theme_gpu": "default_glass",
        "liquid_theme_ram": "default_glass",
        "liquid_theme_fps": "default_glass",
        "liquid_theme_power": "default_glass",
        "liquid_theme_shift": "default_glass",
        "media_progress_interval_playing_ms": 150,
        "media_progress_interval_paused_ms": 500,
        "lyrics_animation_interval_ms": 150,
        "lyric_offset_sec": 0.8,
        "volume_remote_sync_delay_ms": 220,
        "mute_remote_sync_delay_ms": 1200,
        "tuya_pending_ms": 1800,
        "no_media_placeholder_title": "el. psy. congroo.",
        "lyrics_waiting_text": "Waiting for lyrics...",
        "animation_level": "normal",
        "low_performance_mode": False
    },
    "window": {
        "port": 5001,
        "title": "",
        "target_monitor_device": "",
        "target_monitor_left": 0,
        "target_monitor_top": 0,
        "target_monitor_width": 1920,
        "target_monitor_height": 1080,
        "always_on_top": True,
        "fit_to_monitor": True,
        "confirm_close": False,
        "keep_window_alive_interval_ms": 2000,
        "keep_window_alive_min_interval_ms": 250,
        "hide_from_taskbar": True,
        "layout_mode": "landscape",
        "panel_width": 1280,
        "panel_height": 800
    },
    "tuya": {
        "visible_device_keys": [],
        "pc_plug_key": "",
        "brightness_popup_timeout_ms": 1600,
        "read_mode": "local",
        "device_timeout_ms": 2500,
        "local_command_timeout_ms": 2500,
        "cloud_command_timeout_ms": 8000,
        "max_parallel_status_workers": 4,
        "status_batch_size": 8
    },
    "logging": {
        "debug_logging_enabled": True,
        "websocket_logging_enabled": False,
        "tuya_error_logging_enabled": True,
        "hwinfo_error_logging_enabled": True,
        "performance_logging_enabled": False,
        "max_lines": 1500,
        "cleanup_interval_seconds": 900
    },
    "startup": {
        "initial_delay_seconds": 0.0
    },
    "api": {
        "shift": {
            "share_url": "",
            "sheet_name": "Shift",
            "employee_name": "",
            "name_column": 3,
            "date_row": 2
        },
        "meteo": {
            "forecast_url": "https://api.open-meteo.com/v1/forecast",
            "geocoding_url": "https://geocoding-api.open-meteo.com/v1/search",
            "location_query": "Kayseri",
            "location_label": "Kayseri",
            "latitude": 38.7205,
            "longitude": 35.4826,
            "timezone": "Europe/Istanbul",
            "language": "en"
        },
        "smartthings": {
            "api_key": "",
            "base_url": "https://api.smartthings.com/v1",
            "location_id": "",
            "device_id": "",
            "oauth_client_id": "",
            "oauth_client_secret": "",
            "oauth_refresh_token": "",
            "oauth_access_token": "",
            "oauth_access_token_expires_at": 0,
            "oauth_redirect_uri": ""
        },
        "tuya": {
            "base_url": "https://openapi.tuyaeu.com",
            "access_id": "",
            "access_secret": ""
        }
    },
    "external_windows": {
        "spotify": {
            "url": "https://open.spotify.com/intl-tr/",
            "window_title": "Spotify Ekrani",
            "target_monitor_device": ""
        }
    },
    "power": {
        "other_system_power_estimate_w": 100.0
    },
    "hwinfo": {
        "fps_ignore_apps_text": "",
        "auto_restart_enabled": True,
        "auto_restart_max_uptime_hours": 11,
        "executable_path": ""
    },
    "commands": {
        "dnsredir_cmd": r"D:\Program\Goodbye\turkey_dnsredir_alternative4_superonline.cmd",
        "nollie_brightness_script": r"D:\Program\pc-control\plugins\nollie\nollie_brightness.py",
        "nollie_state_path": r"D:\Program\pc-control\json\nollie\nollie_brightness_state.json",
        "nollie_include_boot_canvases": True,
        "lian_control_script": r"D:\Program\pc-control\plugins\lian\lconnect_control.py",
        "lian_profile_path": r"D:\Program\pc-control\json\lian\lconnect_profiles.json",
        "lian_state_cache_path": r"D:\Program\pc-control\json\lian\last_lconnect_state.json",
        "lian_data_dir": r"C:\ProgramData\Lian-Li\L-Connect 3",
        "lian_merge_state_path": "",
        "lian_service_url": "http://127.0.0.1:11021/",
        "lian_timeout_seconds": 2.5
    },
    "monitor_power": {
        "target_fingerprint": "",
        "target_index": -1,
        "target_description": ""
    },
    "panel": {
        "pc_plug_query_interval_seconds": 30.0,
        "left_buttons": [
            {
                "id": "admincmd",
                "label": "Admin CMD",
                "visible": True,
                "variant": "white-glow",
                "command": "/admincmd",
                "secondary_command": "",
                "method": "GET",
                "confirm_text": "",
                "icon_svg": "<svg viewBox=\"0 0 24 24\" width=\"60\" height=\"60\" fill=\"none\" stroke=\"white\" stroke-width=\"1\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><polyline points=\"4 17 10 11 4 5\"></polyline><line x1=\"12\" y1=\"19\" x2=\"20\" y2=\"19\"></line></svg>"
            },
            {
                "id": "dnsredir",
                "label": "DNS Redir",
                "visible": True,
                "variant": "white-glow",
                "command": "/dnsredir",
                "secondary_command": "",
                "method": "POST",
                "confirm_text": "",
                "icon_svg": "<svg width=\"68\" height=\"68\" viewBox=\"0 0 24 24\" fill=\"none\" stroke=\"white\" stroke-width=\"1.7\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M3 12h18\"></path><path d=\"M6 8l-3 4 3 4\"></path><path d=\"M18 8l3 4-3 4\"></path><circle cx=\"12\" cy=\"12\" r=\"3\"></circle></svg>"
            },
            {
                "id": "climate",
                "label": "Klima",
                "visible": True,
                "variant": "white-glow",
                "command": "__climate_popup__",
                "secondary_command": "",
                "method": "SPECIAL",
                "confirm_text": "",
                "icon_svg": "<svg viewBox=\"0 0 24 24\" width=\"68\" height=\"68\" fill=\"none\" stroke=\"currentColor\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M12 3v11\"></path><path d=\"M9 6h3\"></path><path d=\"M9 9h3\"></path><path d=\"M9 12h3\"></path><circle cx=\"12\" cy=\"17\" r=\"4\"></circle></svg>"
            },
            {
                "id": "case_lights",
                "label": "RGB",
                "visible": True,
                "variant": "white-glow",
                "command": "/case_lights/on",
                "secondary_command": "/case_lights/off",
                "method": "GET",
                "confirm_text": "",
                "icon_svg": "<img src=\"resimler\\icon\\air-cooling.png\"/>"
            },
            {
                "id": "all_lights_off",
                "label": "Lights Off",
                "visible": True,
                "variant": "white-glow",
                "command": "/lights/tuya/off",
                "secondary_command": "/lights/all/off",
                "method": "GET",
                "confirm_text": "",
                "icon_svg": "<svg viewBox=\"0 0 24 24\" width=\"80\" height=\"80\" fill=\"none\" stroke=\"white\" stroke-width=\"1.8\" stroke-linecap=\"round\" stroke-linejoin=\"round\"><path d=\"M9 18h6\"></path><path d=\"M10 22h4\"></path><path d=\"M12 2a7 7 0 0 0-4 12c.7.6 1 1.2 1 2h6c0-.8.3-1.4 1-2A7 7 0 0 0 12 2z\"></path><path d=\"M4 4l16 16\"></path></svg>"
            },
            {
                "id": "spotify",
                "label": "Spotify",
                "visible": True,
                "variant": "white-glow",
                "command": "/spotify",
                "secondary_command": "/kill/spotify",
                "method": "GET",
                "confirm_text": "",
                "icon_svg": "<svg viewBox=\"0 0 24 24\" width=\"80\" height=\"80\" fill=\"white\" paint-order=\"stroke fill\" stroke=\"black\" stroke-width=\"1\"><path d=\"M12 0C5.37 0 0 5.37 0 12s5.37 12 12 12 12-5.37 12-12S18.63 0 12 0zm5.52 17.34a.75.75 0 0 1-1.03.25c-2.82-1.72-6.37-2.11-10.55-1.16a.75.75 0 1 1-.33-1.46c4.54-1.03 8.44-.59 11.68 1.38.36.22.47.68.23.99zm1.47-3.27a.94.94 0 0 1-1.29.31c-3.23-1.98-8.15-2.56-11.97-1.41a.94.94 0 1 1-.54-1.8c4.36-1.32 9.78-.67 13.47 1.59.44.27.58.85.33 1.31zm.13-3.41c-3.87-2.3-10.26-2.51-13.96-1.38a1.13 1.13 0 1 1-.66-2.17c4.25-1.29 11.31-1.04 15.77 1.63a1.13 1.13 0 1 1-1.15 1.92z\"/></svg>"
            },
            {
                "id": "sleep",
                "label": "Sleep",
                "visible": True,
                "variant": "purple",
                "command": "/sleep",
                "secondary_command": "",
                "method": "GET",
                "confirm_text": "Put the PC to sleep?",
                "icon_svg": "<svg width=\"80\" height=\"80\" fill=\"none\" viewBox=\"0 0 24 24\"><path stroke=\"white\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M20 14.12A7.78 7.78 0 0 1 9.88 4a7.782 7.782 0 0 0 2.9 15A7.782 7.782 0 0 0 20 14.12z\"/></svg>"
            },
            {
                "id": "restart",
                "label": "Restart",
                "visible": True,
                "variant": "green",
                "command": "/restart",
                "secondary_command": "",
                "method": "GET",
                "confirm_text": "Restart the computer?",
                "icon_svg": "<svg width=\"80\" height=\"80\" fill=\"none\" viewBox=\"0 0 24 24\"><path stroke=\"white\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M4.252 4v5H9M5.07 8a8 8 0 1 1-.818 6\"/></svg>"
            },
            {
                "id": "shutdown",
                "label": "Shutdown",
                "visible": True,
                "variant": "red",
                "command": "/shutdown",
                "secondary_command": "",
                "method": "GET",
                "confirm_text": "Shut down the computer?",
                "icon_svg": "<svg width=\"80\" height=\"80\" fill=\"none\" viewBox=\"0 0 24 24\"><path stroke=\"white\" stroke-linecap=\"round\" stroke-linejoin=\"round\" stroke-width=\"2\" d=\"M7.5 7.638a7 7 0 1 0 9 0M12 4v7\"/></svg>"
            }
        ]
    }
}


def _normalize_settings(data):
    if not isinstance(data, dict):
        return data
    return deepcopy(data)

CURRENT_SETTINGS = None
CURRENT_SETTINGS_MTIME_NS = None


def _get_settings_mtime_ns():
    try:
        stat = os.stat(SETTINGS_PATH)
    except OSError:
        return None
    return getattr(stat, "st_mtime_ns", None) or int(stat.st_mtime * 1_000_000_000)


def _load_settings_from_disk():
    loaded = None
    if os.path.exists(SETTINGS_PATH):
        try:
            with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
                loaded = _normalize_settings(json.load(f))
        except Exception:
            loaded = None
    return _sanitize_settings_by_schema(DEFAULT_SETTINGS, _merge_settings(DEFAULT_SETTINGS, loaded))


def _ensure_settings_loaded_locked(force_reload=False):
    global CURRENT_SETTINGS, CURRENT_SETTINGS_MTIME_NS
    current_mtime_ns = _get_settings_mtime_ns()
    should_reload = force_reload or CURRENT_SETTINGS is None or CURRENT_SETTINGS_MTIME_NS != current_mtime_ns
    if should_reload:
        CURRENT_SETTINGS = _load_settings_from_disk()
        CURRENT_SETTINGS_MTIME_NS = current_mtime_ns
    return CURRENT_SETTINGS


def _merge_settings(defaults, loaded):
    if not isinstance(defaults, dict):
        return deepcopy(loaded) if loaded is not None else deepcopy(defaults)
    result = deepcopy(defaults)
    if not isinstance(loaded, dict):
        return result
    for key, value in loaded.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_settings(result[key], value)
        else:
            result[key] = value
    return result


_NUMERIC_LIMITS = {
    "performance.ui_update_interval_ms": (50, 60000),
    "performance.websocket_broadcast_interval_ms": (50, 60000),
    "performance.status_poll_interval_ms": (100, 300000),
    "performance.hwinfo_refresh_interval_ms": (100, 60000),
    "performance.hwinfo_cache_read_interval_ms": (100, 60000),
    "performance.media_refresh_interval_ms": (100, 60000),
    "performance.volume_refresh_interval_ms": (100, 60000),
    "performance.mute_refresh_interval_ms": (100, 60000),
    "performance.fps_refresh_interval_ms": (50, 60000),
    "performance.weather_refresh_interval_minutes": (1, 1440),
    "performance.shift_cache_check_interval_minutes": (1, 1440),
    "performance.network_refresh_interval_ms": (500, 300000),
    "performance.uptime_refresh_interval_ms": (1000, 300000),
    "performance.tuya_refresh_interval_ms": (500, 300000),
    "performance.tuya_retry_count": (0, 10),
    "frontend.seekbar_update_interval_ms": (50, 60000),
    "frontend.lyrics_refresh_interval_ms": (250, 300000),
    "frontend.liquid_animation_fps": (1, 60),
    "frontend.media_progress_interval_playing_ms": (50, 60000),
    "frontend.media_progress_interval_paused_ms": (100, 60000),
    "frontend.lyrics_animation_interval_ms": (50, 60000),
    "frontend.lyric_offset_sec": (-30, 30),
    "frontend.volume_remote_sync_delay_ms": (0, 10000),
    "frontend.mute_remote_sync_delay_ms": (0, 10000),
    "frontend.tuya_pending_ms": (0, 30000),
    "window.port": (1, 65535),
    "window.target_monitor_left": (-100000, 100000),
    "window.target_monitor_top": (-100000, 100000),
    "window.target_monitor_width": (100, 100000),
    "window.target_monitor_height": (100, 100000),
    "window.keep_window_alive_interval_ms": (100, 300000),
    "window.keep_window_alive_min_interval_ms": (50, 60000),
    "window.panel_width": (100, 100000),
    "window.panel_height": (100, 100000),
    "tuya.brightness_popup_timeout_ms": (100, 30000),
    "tuya.device_timeout_ms": (500, 60000),
    "tuya.local_command_timeout_ms": (500, 60000),
    "tuya.cloud_command_timeout_ms": (1000, 120000),
    "tuya.max_parallel_status_workers": (1, 32),
    "tuya.status_batch_size": (1, 64),
    "logging.max_lines": (20, 20000),
    "logging.cleanup_interval_seconds": (30, 86400),
    "startup.initial_delay_seconds": (0, 300),
    "api.shift.name_column": (1, 500),
    "api.shift.date_row": (1, 500),
    "api.meteo.latitude": (-90, 90),
    "api.meteo.longitude": (-180, 180),
    "api.smartthings.oauth_access_token_expires_at": (0, 4102444800),
    "power.other_system_power_estimate_w": (0, 3000),
    "hwinfo.auto_restart_max_uptime_hours": (1, 168),
    "commands.lian_timeout_seconds": (0.5, 60),
    "monitor_power.target_index": (-1, 128),
    "panel.pc_plug_query_interval_seconds": (1, 3600),
}

_PANEL_BUTTON_FIELDS = {
    "id": "",
    "label": "",
    "visible": True,
    "variant": "white-glow",
    "command": "",
    "secondary_command": "",
    "method": "GET",
    "confirm_text": "",
    "icon_svg": "",
}
_PANEL_BUTTON_METHODS = {"GET", "POST", "SPECIAL"}
def _clamp_number(path, value):
    limits = _NUMERIC_LIMITS.get(path)
    if not limits:
        return value
    low, high = limits
    try:
        value = max(float(low), min(float(high), float(value)))
    except Exception:
        return value
    return int(value) if isinstance(low, int) and isinstance(high, int) else value


def _coerce_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "evet"}
    return bool(default)


def _coerce_number(path, value, default, as_int=False):
    try:
        if isinstance(value, str):
            value = value.strip().replace(",", ".")
        value = float(value)
        value = _clamp_number(path, value)
        return int(value) if as_int else float(value)
    except Exception:
        return deepcopy(default)


def _sanitize_text(value, default="", max_len=4096):
    if value is None:
        value = default
    text = str(value)
    text = text.replace("\x00", "")
    if len(text) > max_len:
        text = text[:max_len]
    return text


def _sanitize_icon_markup(value):
    text = _sanitize_text(value, "", 8000)
    if not text:
        return ""
    text = re.sub(r"<\s*/?\s*(script|iframe|object|embed|link|meta|style|foreignobject)\b[^>]*>", "", text, flags=re.I)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*(['\"]).*?\1", "", text, flags=re.I | re.S)
    text = re.sub(r"\s+on[a-zA-Z]+\s*=\s*[^\s>]+", "", text, flags=re.I)
    text = re.sub(r"javascript\s*:", "", text, flags=re.I)
    text = re.sub(r"data\s*:\s*text/html[^'\"\s>]*", "", text, flags=re.I)
    return text[:8000]


def _sanitize_panel_button(button, index=0):
    if not isinstance(button, dict):
        button = {}
    out = deepcopy(_PANEL_BUTTON_FIELDS)
    out["id"] = re.sub(r"[^a-zA-Z0-9_-]+", "_", _sanitize_text(button.get("id"), f"button_{index + 1}", 80)).strip("_") or f"button_{index + 1}"
    out["label"] = _sanitize_text(button.get("label"), f"Button {index + 1}", 120).strip() or f"Button {index + 1}"
    out["visible"] = _coerce_bool(button.get("visible"), True)
    out["variant"] = re.sub(r"[^a-zA-Z0-9_-]+", "", _sanitize_text(button.get("variant"), "white-glow", 80)) or "white-glow"
    out["command"] = _sanitize_text(button.get("command"), "", 512).strip()
    out["secondary_command"] = _sanitize_text(button.get("secondary_command"), "", 512).strip()
    method = _sanitize_text(button.get("method"), "GET", 20).strip().upper()
    out["method"] = method if method in _PANEL_BUTTON_METHODS else "GET"
    out["confirm_text"] = _sanitize_text(button.get("confirm_text"), "", 300).strip()
    out["icon_svg"] = _sanitize_icon_markup(button.get("icon_svg"))
    return out


def _sanitize_panel_buttons(value):
    items = value if isinstance(value, list) else DEFAULT_SETTINGS["panel"]["left_buttons"]
    out = []
    seen_ids = set()
    for index, item in enumerate(items[:24]):
        button = _sanitize_panel_button(item, index)
        if button["id"] in seen_ids:
            button["id"] = f"{button['id']}_{index + 1}"
        seen_ids.add(button["id"])
        out.append(button)
    return out


def _sanitize_list(path, value, default):
    if path == "panel.left_buttons":
        return _sanitize_panel_buttons(value)
    if not isinstance(value, list):
        value = default if isinstance(default, list) else []
    if path == "tuya.visible_device_keys":
        return [_sanitize_text(item, "", 160).strip() for item in value[:64] if _sanitize_text(item, "", 160).strip()]
    return deepcopy(value)


def _sanitize_settings_by_schema(schema, value, path=""):
    if isinstance(schema, dict):
        source = value if isinstance(value, dict) else {}
        return {
            key: _sanitize_settings_by_schema(default, source.get(key, default), f"{path}.{key}" if path else key)
            for key, default in schema.items()
        }
    if isinstance(schema, list):
        return _sanitize_list(path, value, schema)
    if isinstance(schema, bool):
        return _coerce_bool(value, schema)
    if isinstance(schema, int) and not isinstance(schema, bool):
        return _coerce_number(path, value, schema, as_int=True)
    if isinstance(schema, float):
        return _coerce_number(path, value, schema, as_int=False)
    if isinstance(schema, str):
        return _sanitize_text(value, schema)
    return deepcopy(value if value is not None else schema)


def load_settings(force_reload=False):
    with SETTINGS_LOCK:
        data = _ensure_settings_loaded_locked(force_reload=force_reload)
        return deepcopy(data)


def peek_settings(force_reload=False):
    with SETTINGS_LOCK:
        return _ensure_settings_loaded_locked(force_reload=force_reload)


def peek_setting(path, default=None, force_reload=False):
    data = peek_settings(force_reload=force_reload)
    node = data
    for part in str(path).split('.'):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


def save_settings(new_settings, replace=False):
    global CURRENT_SETTINGS, CURRENT_SETTINGS_MTIME_NS
    with SETTINGS_LOCK:
        base = DEFAULT_SETTINGS if replace else _ensure_settings_loaded_locked(force_reload=True)
        merged = _merge_settings(DEFAULT_SETTINGS, _merge_settings(base, _normalize_settings(new_settings)))
        merged = _sanitize_settings_by_schema(DEFAULT_SETTINGS, merged)
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        CURRENT_SETTINGS = deepcopy(merged)
        CURRENT_SETTINGS_MTIME_NS = _get_settings_mtime_ns()
        return deepcopy(CURRENT_SETTINGS)


def reset_settings():
    return save_settings(DEFAULT_SETTINGS, replace=True)


def get_setting(path, default=None):
    node = peek_setting(path, default=default)
    return deepcopy(node)
