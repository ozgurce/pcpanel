# File Version: 1.1
import json
import os
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
        "youtube": {
            "url": "https://www.youtube.com/shorts/",
            "window_title": "YouTube Ekrani",
            "target_monitor_device": ""
        },
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
                "id": "youtube",
                "label": "YouTube",
                "visible": True,
                "variant": "white-glow",
                "command": "/shorts",
                "secondary_command": "/kill/shorts",
                "method": "GET",
                "confirm_text": "",
                "icon_svg": "<svg viewBox=\"0 0 24 24\" width=\"80\" height=\"80\" fill=\"white\" paint-order=\"stroke fill\" stroke=\"black\" stroke-width=\"1\"><path d=\"M23.5 6.2a3 3 0 00-2.1-2.1C19.6 3.5 12 3.5 12 3.5s-7.6 0-9.4.6A3 3 0 00.5 6.2 31.4 31.4 0 000 12a31.4 31.4 0 00.5 5.8 3 3 0 002.1 2.1c1.8.6 9.4.6 9.4.6s7.6 0 9.4-.6a3 3 0 002.1-2.1A31.4 31.4 0 0024 12a31.4 31.4 0 00-.5-5.8zM9.75 15.5v-7l6.5 3.5-6.5 3.5z\"/></svg>"
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
    return _merge_settings(DEFAULT_SETTINGS, loaded)


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
