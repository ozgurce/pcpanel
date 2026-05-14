# File Version: 1.0
import os
import time
import json
import re
import asyncio
import datetime
import urllib.parse
from types import SimpleNamespace
from aiohttp import web

from panel_globals import (
    BASE_DIR, LOG_FILE, ERR_FILE, TUYA_LOG_FILE,
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, WORKER_STATE,
    HATA_HTML_FILE_PATH, SITEMAP_HTML_FILE_PATH,
    HTTP_SESSION_LOCK, WORKER_RESTART_COOLDOWN_SECONDS,
    WORKER_HEARTBEAT_TIMEOUT_SECONDS, SERVER_READY
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_int, _get_setting_bool,
    _get_shared_http_session, NO_CACHE_HEADERS
)
from panel_logging import log, log_error, log_ws_debug, log_hwinfo_error
from panel_state import mark_system_cache_changed
from panel_system import get_cached_system_info
from panel_commands import run_command
from panel_media import media_seek
async def _handle_ws_command_message(ws, payload):
    request_id = payload.get("request_id")
    path = str(payload.get("path") or "").strip()
    params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
    log_ws_debug(f"command path={path or '?'} request_id={request_id}")

    async def _reply(ok, result=None, error=None):
        msg = {"type": "command_result", "request_id": request_id, "ok": bool(ok)}
        if result is not None:
            msg["payload"] = result
        if error is not None:
            msg["error"] = str(error)
        await _safe_ws_send_json(ws, msg)

    try:
        if path == "/media/seek":
            req = SimpleNamespace(query={"position": str(params.get("position", ""))}, match_info={})
            response = await media_seek(req)
            result = json.loads(response.text)
            await _reply(response.status < 400 and result.get("ok") is not False, result=result, error=result.get("error") if isinstance(result, dict) else None)
            await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})
            return

        if path.startswith("/tuya/toggle/"):
            device_key = urllib.parse.unquote(path.split("/tuya/toggle/", 1)[1])
            req = SimpleNamespace(match_info={"device_key": device_key}, query={})
            response = await tuya_toggle(req)
            result = json.loads(response.text)
            await _reply(response.status < 400 and result.get("ok") is not False, result=result, error=result.get("error") if isinstance(result, dict) else None)
            await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})
            return

        if path.startswith("/tuya/brightness/"):
            device_key = urllib.parse.unquote(path.split("/tuya/brightness/", 1)[1])
            req = SimpleNamespace(match_info={"device_key": device_key}, query={"value": str(params.get("value", ""))})
            response = await tuya_set_brightness(req)
            result = json.loads(response.text)
            await _reply(response.status < 400 and result.get("ok") is not False, result=result, error=result.get("error") if isinstance(result, dict) else None)
            await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})
            return

        req = SimpleNamespace(query={k: str(v) for k, v in params.items()}, match_info={})
        result_text = await run_command(path, req)
        try:
            parsed_result = json.loads(result_text)
        except Exception:
            parsed_result = {"result": result_text}
        ok = not (isinstance(parsed_result, dict) and parsed_result.get("ok") is False)
        await _reply(ok, result=parsed_result, error=parsed_result.get("error") if isinstance(parsed_result, dict) else None)
        await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})
    except Exception as exc:
        log_ws_debug(f"command exception path={path or '?'}: {exc}")
        await _reply(False, error=str(exc))



LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s+\|\s+(.*)$")


def _parse_grouped_log_entries(path: str, limit: int = 300):
    try:
        lim = max(20, min(2000, int(limit or 300)))
    except Exception:
        lim = 300

    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            raw_lines = [line.rstrip("\\r\\n") for line in f]
    except FileNotFoundError:
        return [{"ts": "-", "source": "SYSTEM", "message": f"Dosya bulunamadi: {path}", "level": "error"}]
    except Exception as exc:
        return [{"ts": "-", "source": "SYSTEM", "message": f"Log file could not be read: {exc}", "level": "error"}]

    entries = []
    current = None
    for raw in raw_lines:
        line = _translate_log_text(_repair_mojibake_text((raw or "").strip()))
        if not line:
            continue
        m = LOG_TS_RE.match(line)
        if m:
            if current:
                entries.append(current)
            current = {"ts": m.group(1), "rest": m.group(2)}
        else:
            if current is None:
                current = {"ts": "-", "rest": line}
            else:
                current["rest"] += " " + line
    if current:
        entries.append(current)

    parsed = []
    for item in reversed(entries[-lim:]):
        rest = _translate_log_text(_repair_mojibake_text(item.get("rest") or ""))
        source, message = rest, ""
        if " | " in rest:
            source, message = rest.split(" | ", 1)
        source = _translate_log_text(_repair_mojibake_text(source.strip() or "SYSTEM"))
        message = _translate_log_text(_repair_mojibake_text(message.strip() or source))
        lowered = f"{source} {message}".lower()
        level = "info"
        if any(token in lowered for token in ("error", "exception", "traceback", "failed", "offline dondu", "check device key or version", "basarisiz")):
            level = "error"
        elif any(token in lowered for token in ("warning", "uyari", "degraded")):
            level = "warn"
        parsed.append({
            "ts": item.get("ts") or "-",
            "source": source,
            "message": message,
            "level": level,
        })
    return parsed


def _clear_log_files():
    cleared = []
    for path in (ERR_FILE, LOG_FILE, TUYA_LOG_FILE):
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8"):
                pass
            cleared.append(path)
        except Exception as exc:
            raise RuntimeError(f"Log file could not be cleared: {path} ({exc})") from exc
    try:
        LOGGER.prune_all_now()
        LOGGER._prune_log_file(TUYA_LOG_FILE, force=True)
    except Exception:
        pass
    return cleared


def _clear_tuya_log_file():
    try:
        os.makedirs(os.path.dirname(TUYA_LOG_FILE), exist_ok=True)
        with open(TUYA_LOG_FILE, "w", encoding="utf-8"):
            pass
        LOGGER._prune_log_file(TUYA_LOG_FILE, force=True)
        return True
    except Exception as exc:
        raise RuntimeError(f"Tuya log file could not be cleared: {TUYA_LOG_FILE} ({exc})") from exc


async def hata_root(r):
    return _load_html_response(HATA_HTML_FILE_PATH, "Error HTML interface")


async def tuya_pc_debug(_request):
    try:
        return web.json_response({"ok": True, **_get_pc_plug_debug_info()})
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)})


async def hata_data(r):
    try:
        limit = int((r.query.get("lines") or "300").strip())
    except Exception:
        limit = 300
    limit = max(20, min(2000, limit))

    error_entries, log_entries, tuya_entries = await asyncio.gather(
        asyncio.to_thread(_parse_grouped_log_entries, ERR_FILE, limit),
        asyncio.to_thread(_parse_grouped_log_entries, LOG_FILE, limit),
        asyncio.to_thread(_parse_grouped_log_entries, TUYA_LOG_FILE, limit),
    )
    cache = get_cached_system_info()
    payload = {
        "ok": True,
        "lines": limit,
        "summary": {
            "updated_at": datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "cpu": cache.get("cpu_percent"),
            "ram": cache.get("ram_percent"),
            "volume": cache.get("volume_percent"),
            "fps": cache.get("fps"),
            "tuya_count": len(cache.get("tuya_devices") or []) if isinstance(cache.get("tuya_devices"), list) else 0,
        },
        "errors": error_entries,
        "logs": log_entries,
        "tuya": tuya_entries,
    }
    return web.json_response(payload, headers=NO_CACHE_HEADERS)


async def api_logs_clear(_request):
    try:
        cleared = await asyncio.to_thread(_clear_log_files)
        return web.json_response({"ok": True, "cleared": cleared}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


async def api_tuya_logs_clear(_request):
    try:
        await asyncio.to_thread(_clear_tuya_log_file)
        return web.json_response({"ok": True, "cleared": [TUYA_LOG_FILE]}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


async def api_hwinfo_restart(_request):
    try:
        before = await asyncio.to_thread(get_hwinfo_app_status)
        ok = await asyncio.to_thread(restart_hwinfo_application_if_needed, True, "manual_settings_button")
        after = await asyncio.to_thread(get_hwinfo_app_status)
        if not ok:
            error_text = str(WORKER_STATE.get("last_hwinfo_restart_error") or "").strip()
            return web.json_response({
                "ok": False,
                "error": error_text or "HWiNFO could not be restarted. Check the HWiNFO executable path setting.",
                "before": before,
                "after": after,
            }, status=500, headers=NO_CACHE_HEADERS)
        return web.json_response({"ok": True, "before": before, "after": after}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_hwinfo_error(f"HWiNFO manual restart endpoint error: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)



ROUTE_HINTS = {
    "/": {"title": "Main Panel", "description": "Horizontal main panel UI.", "category": "UI"},
    "/dikey": {"title": "Vertical Panel", "description": "Vertical panel UI.", "category": "UI"},
    "/status": {"title": "Live Status", "description": "Returns the full system, media, audio, and Tuya status as JSON.", "category": "Status"},
    "/health": {"title": "Health Check", "description": "Summarizes the panel's core service health.", "category": "Status"},
    "/hata": {"title": "Error Screen", "description": "Modern log viewer interface.", "category": "Log"},
    "/hata/data": {"title": "Error Data", "description": "JSON data source for the error screen.", "category": "Log"},
    "/ws/status": {"title": "WebSocket Status", "description": "WebSocket endpoint for live panel updates.", "category": "Status"},
    "/weather/meteo": {"title": "Weather", "description": "Open-Meteo-based weather data.", "category": "Weather"},
    "/weather/mgm": {"title": "Weather (MGM)", "description": "MGM alias route serving the same data.", "category": "Weather"},
    "/media/seek": {"title": "Media Seek", "description": "Seeks active media to the requested second. Requires the position parameter.", "category": "Media", "examples": [{"label": "Seek to 30 seconds", "path": "/media/seek?position=30"}]},
    "/mute": {"title": "Mute", "description": "Toggles mute on or off.", "category": "Audio"},
    "/volup": {"title": "Volume Up", "description": "Increases the volume level.", "category": "Audio"},
    "/voldown": {"title": "Volume Down", "description": "Decreases the volume level.", "category": "Audio"},
    "/setvolume": {"title": "Set Volume", "description": "Sets volume using the value parameter.", "category": "Audio", "examples": [{"label": "Set to 30%", "path": "/setvolume?value=30"}, {"label": "Set to 70%", "path": "/setvolume?value=70"}]},
    "/playpause": {"title": "Play/Pause", "description": "Pauses or resumes media playback.", "category": "Media"},
    "/next": {"title": "Next Track", "description": "Skips to the next media track.", "category": "Media"},
    "/prev": {"title": "Previous Track", "description": "Returns to the previous media track.", "category": "Media"},
    "/spotify": {"title": "Open Spotify", "description": "Opens Spotify or brings it to the foreground.", "category": "App"},
    "/kill/spotify": {"title": "Close Spotify", "description": "Closes the Spotify process.", "category": "App"},
    "/tiktok": {"title": "TikTok", "description": "Opens the TikTok page.", "category": "App"},
    "/chrome": {"title": "Chrome", "description": "Opens Chrome.", "category": "App"},
    "/settings": {"title": "Windows Settings", "description": "Opens the Windows settings screen.", "category": "System"},
    "/taskmgr": {"title": "Task Manager", "description": "Opens Task Manager.", "category": "System"},
    "/case_lights/on": {"title": "Case Lights On", "description": "Restores Nollie brightness and applies the L-Connect lights-on command.", "category": "System"},
    "/case_lights/off": {"title": "Case Lights Off", "description": "Sets Nollie brightness to zero and applies the L-Connect lights-off command.", "category": "System"},
    "/lights/tuya/off": {"title": "Tuya Lights Off", "description": "Turns off Tuya devices configured as light or bulb.", "category": "System"},
    "/lights/all/off": {"title": "All Lights and Monitor Off", "description": "Turns off Tuya lights, case lights, and the selected monitor.", "category": "System"},
    "/admincmd": {"title": "Admin CMD", "description": "Opens an elevated command prompt.", "category": "System"},
    "/shutdown": {"title": "Shut Down", "description": "Shuts down the computer.", "category": "Power"},
    "/restart": {"title": "Restart", "description": "Restarts the computer.", "category": "Power"},
    "/sleep": {"title": "Sleep", "description": "Puts the computer to sleep.", "category": "Power"},
    "/lock": {"title": "Lock", "description": "Locks the current session.", "category": "Power"},
    "/restart_app": {"title": "Restart Panel Application", "description": "Restarts the Python process and the panel.", "category": "Power"},
    "/tuya/status": {"title": "Tuya Status", "description": "Returns JSON status for all Tuya devices.", "category": "Tuya"},
    "/tuya/pc_debug": {"title": "PC Plug Debug", "description": "Shows raw data and wattage parsing for the smart plug named PC.", "category": "Tuya"},
    "/tuya/toggle/{device_key}": {"title": "Tuya Toggle", "description": "Toggles the specified device key on or off.", "category": "Tuya"},
    "/tuya/brightness/{device_key}": {"title": "Tuya Brightness", "description": "Sets brightness using the value parameter.", "category": "Tuya"},
    "/api/tuya/check": {"title": "Tuya Check", "description": "Refreshes and returns live Tuya device status.", "category": "Tuya"},
    "/api/tuya/reset": {"title": "Tuya Reset", "description": "Clears Tuya runtime connections and checks devices again.", "category": "Tuya"},
    "/api/tuya/logs/clear": {"title": "Clear Tuya Logs", "description": "Clears only the separate Tuya log file.", "category": "Tuya"},
    "/check_refresh": {"title": "Refresh Check", "description": "Checks whether the UI needs a refresh.", "category": "Utility"},
    "/trigger_refresh": {"title": "Trigger Refresh", "description": "Sends a refresh signal to the UI.", "category": "Utility"},
    "/script.js": {"title": "Panel Script", "description": "Main panel JavaScript file.", "category": "Asset"},
    "/liquid_themes.js": {"title": "Liquid Theme Presets", "description": "Shared liquid theme list used by the main panel and settings UI.", "category": "Asset"},
    "/resimler": {"title": "Images", "description": "Panel visual asset directory.", "category": "Asset"},
    "/fonts": {"title": "Fonts", "description": "Panel font directory.", "category": "Asset"},
}


def _guess_route_category(path: str):
    if path.startswith("/tuya/") or path.startswith("/api/tuya/"):
        return "Tuya"
    if path.startswith("/weather/"):
        return "Weather"
    if path.startswith("/media/"):
        return "Media"
    if path.startswith("/hata"):
        return "Log"
    if path.startswith("/ws/") or path in ("/status", "/health"):
        return "Status"
    if path in ("/mute", "/volup", "/voldown", "/setvolume"):
        return "Audio"
    if path in ("/shutdown", "/restart", "/sleep", "/lock", "/restart_app"):
        return "Power"
    if path.startswith("/resimler") or path.startswith("/fonts") or path.endswith(".js"):
        return "Asset"
    return "Other"


def _load_tuya_device_examples():
    devices_path = os.path.join(BASE_DIR, "json", "devices.json")
    try:
        with open(devices_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, dict):
        data = data.get("devices") or data.get("items") or []
    examples = []
    if isinstance(data, list):
        for item in data:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or item.get("device_key") or "").strip()
            name = str(item.get("name") or key).strip() or key
            if not key:
                continue
            examples.append({"key": key, "name": name})
    return examples


def _build_sitemap_items(base_url: str, app_obj):
    items = []
    tuya_examples = _load_tuya_device_examples()
    seen = set()
    for resource in app_obj.router.resources():
        info = resource.get_info()
        path = info.get("path") or info.get("formatter") or getattr(resource, "canonical", None) or ""
        if not path:
            continue
        if path in seen:
            continue
        seen.add(path)
        methods = sorted({getattr(route, "method", "GET") for route in resource})
        hint = ROUTE_HINTS.get(path, {})
        title = hint.get("title") or path.strip("/") or "root"
        description = hint.get("description") or "HTTP endpoint registered by the panel."
        category = hint.get("category") or _guess_route_category(path)
        examples = []
        for example in hint.get("examples", []):
            ex_path = example.get("path") or path
            examples.append({"label": example.get("label") or ex_path, "url": base_url + ex_path})
        if path == "/tuya/toggle/{device_key}":
            for dev in tuya_examples:
                examples.append({"label": f"{dev['name']} toggle", "url": base_url + f"/tuya/toggle/{urllib.parse.quote(dev['key'])}"})
        elif path == "/tuya/brightness/{device_key}":
            for dev in tuya_examples:
                examples.append({"label": f"{dev['name']} %25", "url": base_url + f"/tuya/brightness/{urllib.parse.quote(dev['key'])}?value=25"})
                examples.append({"label": f"{dev['name']} %100", "url": base_url + f"/tuya/brightness/{urllib.parse.quote(dev['key'])}?value=100"})
        elif not examples:
            examples.append({"label": "Endpointi ac", "url": base_url + path})
        items.append({
            "path": path,
            "title": title,
            "description": description,
            "category": category,
            "methods": methods,
            "examples": examples,
        })
    items.sort(key=lambda x: (x["category"], x["path"]))
    return items


async def sitemap_root(r):
    return _load_html_response(SITEMAP_HTML_FILE_PATH, "Sitemap HTML UI")


async def sitemap_data(r):
    base_url = f"{r.scheme}://{r.host}"
    items = await asyncio.to_thread(_build_sitemap_items, base_url, r.app)
    return web.json_response({"ok": True, "base_url": base_url, "count": len(items), "items": items}, headers=NO_CACHE_HEADERS)


async def health(r):
    """
    Lightweight health check:
    - last update age
    - basic metric availability
    - simple HWiNFO / Tuya / media loop flags
    """
    with SENSOR_CACHE_LOCK:
        cached = dict(SYSTEM_CACHE)

    now = time.time()
    last_update = float(cached.get("last_update") or 0)
    age = now - last_update if last_update > 0 else None

    basic_ok = (
        cached.get("cpu_percent") is not None
        and cached.get("ram_percent") is not None
    )

    media_ok = True
    tuya_ok = isinstance(cached.get("tuya_devices"), list)

    status = "ok"
    details = []

    if age is None or age > 10:
        status = "degraded"
        details.append("system_cache_stale")
    if not basic_ok:
        status = "degraded"
        details.append("basic_metrics_missing")
    if not tuya_ok:
        details.append("tuya_unavailable")

    payload = {
        "status": status,
        "age_seconds": age,
        "last_update_ts": last_update,
        "basic_ok": basic_ok,
        "media_ok": media_ok,
        "tuya_ok": tuya_ok,
        "details": details,
    }
    return web.json_response(payload)


def _format_health_relative_age(seconds):
    try:
        seconds = float(seconds)
    except Exception:
        return "Unknown"
    if seconds < 1:
        return "Now"
    if seconds < 60:
        return f"{int(seconds)} sec ago"
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min ago"
    hours = int(minutes // 60)
    if hours < 24:
        return f"{hours} hr ago"
    days = int(hours // 24)
    return f"{days} days ago"


def _format_health_timestamp(ts):
    try:
        ts = float(ts)
    except Exception:
        return "-"
    if ts <= 0:
        return "-"
    try:
        return datetime.datetime.fromtimestamp(ts).strftime("%d.%m.%Y %H:%M:%S")
    except Exception:
        return "-"


def _mask_secret(value, keep=4):
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= keep:
        return "*" * len(text)
    return ("*" * max(4, len(text) - keep)) + text[-keep:]



def get_recent_tuya_logs(limit: int = 12):
    try:
        from tuya_runtime import get_recent_tuya_logs as _runtime_get_recent_tuya_logs
        return _runtime_get_recent_tuya_logs(limit)
    except Exception:
        try:
            return _parse_grouped_log_entries(TUYA_LOG_FILE, limit)
        except Exception:
            return []


def _normalize_log_items(items):
    normalized = []
    if not isinstance(items, list):
        items = [] if items in (None, '') else [items]
    for item in items:
        if isinstance(item, dict):
            normalized.append(item)
        else:
            normalized.append({
                "ts": "-",
                "source": "TUYA",
                "message": str(item),
                "level": "error" if "error" in str(item).lower() else "info",
            })
    return normalized

def _health_status_from_parts(ok=None, warning=False):
    if ok is True and not warning:
        return "ok"
    if ok is False:
        return "error"
    if warning:
        return "warn"
    return "warn"


def _build_health_report():
    """Build a health report defensively; never assume Tuya/settings/cache objects are dicts."""
    now = time.time()

    def as_dict(value):
        return value if isinstance(value, dict) else {}

    def as_list(value):
        if isinstance(value, list):
            return value
        if value in (None, ""):
            return []
        return [value]

    def safe_get(obj, key, default=None):
        return obj.get(key, default) if isinstance(obj, dict) else default

    def safe_float(value, default=None):
        try:
            if value in (None, ""):
                return default
            return float(value)
        except Exception:
            return default

    def safe_len(value):
        try:
            return len(value or [])
        except Exception:
            return 0

    def normalize_devices(value):
        return [d for d in as_list(value) if isinstance(d, dict)]

    with SENSOR_CACHE_LOCK:
        cached = dict(SYSTEM_CACHE) if isinstance(SYSTEM_CACHE, dict) else {}

    settings_data = as_dict(load_settings() or {})
    api_cfg = as_dict(settings_data.get("api"))
    smartthings_cfg = as_dict(api_cfg.get("smartthings"))
    meteo_cfg = as_dict(api_cfg.get("meteo"))
    tuya_api_cfg = as_dict(api_cfg.get("tuya"))

    last_update_ts = safe_float(cached.get("last_update"), 0.0) or 0.0
    cache_age = (now - last_update_ts) if last_update_ts > 0 else None
    hwinfo_last_seen = safe_float(safe_get(WORKER_STATE, "last_hwinfo_seen", 0.0), 0.0) or 0.0
    hwinfo_age = (now - hwinfo_last_seen) if hwinfo_last_seen > 0 else None

    raw_tuya_devices = cached.get("tuya_devices")
    tuya_devices = normalize_devices(raw_tuya_devices)
    try:
        configured_devices = get_tuya_devices_config()
    except Exception as exc:
        configured_devices = []
        log_error(f"Health Tuya config read error: {type(exc).__name__}: {exc}")
    configured_device_count = safe_len(configured_devices if not isinstance(configured_devices, dict) else configured_devices.keys())

    tuya_online = sum(1 for d in tuya_devices if d.get("online") is True)
    tuya_errors = [d for d in tuya_devices if d.get("error")]
    tuya_pending_refresh = [d for d in tuya_errors if str(d.get("error") or "").strip().lower() in {"waiting for refresh", "refresh pending"}]
    tuya_real_errors = [d for d in tuya_errors if d not in tuya_pending_refresh]

    pc_plug_info = as_dict(PC_PLUG_QUERY_CACHE)
    pc_plug_cloud_info = as_dict(PC_PLUG_CLOUD_CACHE)
    pc_plug_ts = safe_float(pc_plug_info.get("ts"), 0.0) or 0.0
    pc_plug_age = (now - pc_plug_ts) if pc_plug_ts > 0 else None

    weather_payload = as_dict(_get_cached_weather_payload())
    weather_ok = cached.get("weather_ok") is True
    weather_error = weather_payload.get("error") if not weather_ok else None
    weather_ready = cached.get("weather_summary") not in (None, "", "No Data")

    recent_tuya_logs = _normalize_log_items(get_recent_tuya_logs(8))
    recent_tuya_error = next((item for item in recent_tuya_logs if isinstance(item, dict) and str(item.get("level") or "").lower() == "error"), None)
    recent_error_logs = _parse_grouped_log_entries(ERR_FILE, 10)
    recent_general_logs = _parse_grouped_log_entries(LOG_FILE, 10)
    recent_tuya_file_logs = _normalize_log_items(_parse_grouped_log_entries(TUYA_LOG_FILE, 10))

    def snap_num(value, suffix="", decimals=1):
        num = safe_float(value)
        if num is None:
            return "-"
        text = f"{num:.{decimals}f}".rstrip("0").rstrip(".")
        return f"{text}{suffix}"

    smartthings_access_token = str(smartthings_cfg.get("oauth_access_token") or smartthings_cfg.get("api_key") or "").strip()
    smartthings_refresh_ready = bool(
        str(smartthings_cfg.get("oauth_client_id") or "").strip()
        and str(smartthings_cfg.get("oauth_client_secret") or "").strip()
        and str(smartthings_cfg.get("oauth_refresh_token") or "").strip()
    )
    smartthings_configured = bool(str(smartthings_cfg.get("device_id") or "").strip() and (smartthings_access_token or smartthings_refresh_ready))
    weather_configured = bool(str(meteo_cfg.get("location_query") or "").strip() and str(meteo_cfg.get("latitude") or "").strip() and str(meteo_cfg.get("longitude") or "").strip())
    tuya_cloud_configured = bool(str(tuya_api_cfg.get("access_id") or "").strip() and str(tuya_api_cfg.get("access_secret") or "").strip())
    tuya_local_configured = bool(tuya_devices or configured_device_count)

    checks = []
    snapshots = []
    configuration = []

    cache_ok = cache_age is not None and cache_age <= 10.0 and cached.get("cpu_percent") is not None and cached.get("ram_percent") is not None
    checks.append({
        "key": "system_cache", "label": "System Cache",
        "status": _health_status_from_parts(cache_ok, warning=cache_age is not None and cache_age > 4.0 and cache_ok),
        "summary": "Live sensor cache state",
        "detail": f"Last update: {_format_health_relative_age(cache_age)}",
        "last_success": _format_health_timestamp(last_update_ts),
        "meta": {"cpu_percent": cached.get("cpu_percent"), "ram_percent": cached.get("ram_percent"), "volume_percent": cached.get("volume_percent")},
    })

    down_speed = safe_float(cached.get("download_speed_mbps"))
    up_speed = safe_float(cached.get("upload_speed_mbps"))
    network_value = "-"
    if down_speed is not None or up_speed is not None:
        network_value = f"{snap_num(down_speed, ' ↓', 2)} / {snap_num(up_speed, ' ↑', 2)}"

    media_title = str(cached.get("media_title") or "").strip()
    media_source_app = str(cached.get("media_source_app") or "").strip()
    snapshots.extend([
        {"label": "CPU", "value": snap_num(cached.get("cpu_percent"), "%", 1), "subvalue": snap_num(cached.get("cpu_temp"), "°C", 1) if cached.get("cpu_temp") is not None else "No heat data", "status": "ok" if cached.get("cpu_percent") is not None else "warn"},
        {"label": "GPU", "value": snap_num(cached.get("gpu_util"), "%", 1), "subvalue": snap_num(cached.get("gpu_temp"), "°C", 1) if cached.get("gpu_temp") is not None else "No heat data", "status": "ok" if cached.get("gpu_util") is not None else "warn"},
        {"label": "MoBo/VRM", "value": snap_num(cached.get("motherboard_temp") or cached.get("mobo_temp"), "°C", 1), "subvalue": snap_num(cached.get("vmos_temp") or cached.get("vrm_temp") or cached.get("vrmos_temp"), "°C", 1), "status": "ok" if (cached.get("motherboard_temp") is not None or cached.get("vmos_temp") is not None) else "warn"},
        {"label": "RAM", "value": snap_num(cached.get("ram_percent"), "%", 1), "subvalue": f"{snap_num(cached.get('ram_used_gb'), '', 1)} GB used" if cached.get("ram_used_gb") is not None else "Memory details unavailable", "status": "ok" if cached.get("ram_percent") is not None else "warn"},
        {"label": "Audio", "value": f"{cached.get('volume_percent')}%" if cached.get("volume_percent") is not None else "-", "subvalue": "Muted" if cached.get("is_muted") else "On", "status": "ok" if cached.get("volume_percent") is not None else "warn"},
        {"label": "FPS", "value": str(cached.get("fps") if cached.get("fps") is not None else "-"), "subvalue": "No active FPS value" if cached.get("fps") is None else "Active", "status": "ok" if cached.get("fps") is not None else "warn"},
        {"label": "Network", "value": network_value, "subvalue": str(cached.get("uptime") or "-"), "status": "ok" if down_speed is not None or up_speed is not None else "warn"},
        {"label": "Weather", "value": str(cached.get("weather_summary") or "-"), "subvalue": str(cached.get("weather_location") or _get_meteo_location_label() or "-"), "status": "ok" if weather_ok else "warn"},
        {"label": "Media", "value": media_title or "-", "subvalue": str(cached.get("media_artist") or media_source_app or "No active media"), "status": "ok"},
    ])

    try:
        hwinfo_app_status = as_dict(get_hwinfo_app_status())
    except Exception as exc:
        hwinfo_app_status = {"error": str(exc)}
    hwinfo_ok = hwinfo_age is not None and hwinfo_age <= WORKER_HEARTBEAT_TIMEOUT_SECONDS
    hwinfo_warning = hwinfo_age is not None and hwinfo_age > (WORKER_HEARTBEAT_TIMEOUT_SECONDS * 0.5) and hwinfo_ok
    checks.append({
        "key": "hwinfo", "label": "HWiNFO Worker",
        "status": _health_status_from_parts(hwinfo_ok, warning=hwinfo_warning),
        "summary": "Hardware worker snapshot stream",
        "detail": f"Last heartbeat: {_format_health_relative_age(hwinfo_age)}",
        "last_success": _format_health_timestamp(hwinfo_last_seen),
        "meta": {"worker_running": bool(safe_get(WORKER_STATE, "hwinfo_proc") and safe_get(WORKER_STATE, "hwinfo_proc").poll() is None), "hwinfo_running": bool(hwinfo_app_status.get("running")), "gpu_temp": cached.get("gpu_temp")},
    })

    weather_status = _health_status_from_parts(weather_ok, warning=(not weather_ok and weather_configured))
    checks.append({"key": "weather", "label": "Weather", "status": weather_status if weather_ready or weather_configured else "warn", "summary": "Open-Meteo integration", "detail": str(cached.get("weather_summary") or weather_error or "Weather data is not ready"), "last_success": _format_health_timestamp(last_update_ts if weather_ok else 0), "meta": {"configured": weather_configured}})

    tuya_ok = tuya_local_configured and (not tuya_devices or tuya_online > 0)
    tuya_warning = tuya_local_configured and bool(tuya_real_errors)
    tuya_detail = f"Devices: {tuya_online}/{len(tuya_devices)} online" if tuya_devices else ("No device has been read yet" if tuya_local_configured else "Device configuration is incomplete")
    checks.append({"key": "tuya", "label": "Tuya Devices", "status": _health_status_from_parts(tuya_ok, warning=tuya_warning or (tuya_local_configured and not tuya_devices)), "summary": "Local device cache and device access", "detail": tuya_detail, "last_success": _format_health_timestamp(last_update_ts if tuya_online > 0 else 0), "meta": {"configured": tuya_local_configured, "visible_count": len(tuya_devices), "configured_count": configured_device_count, "error_count": len(tuya_real_errors)}})

    checks.append({"key": "pc_plug", "label": "PC Plug Wattage", "status": _health_status_from_parts(pc_plug_info.get("power_w") is not None, warning=bool(pc_plug_info.get("error") or pc_plug_cloud_info.get("error"))), "summary": "PC power draw query", "detail": f"{pc_plug_info.get('power_w')} W ({pc_plug_info.get('source') or 'local'})" if pc_plug_info.get("power_w") is not None else str(pc_plug_info.get("error") or pc_plug_cloud_info.get("error") or "No data"), "last_success": _format_health_timestamp(pc_plug_ts), "meta": {"age": _format_health_relative_age(pc_plug_age), "cloud_source": pc_plug_cloud_info.get("source"), "cloud_error": pc_plug_cloud_info.get("error")}})

    checks.append({"key": "smartthings", "label": "SmartThings Climate", "status": "ok" if smartthings_configured else "warn", "summary": "Climate control integration settings", "detail": "Configured" if smartthings_configured else "Token or device ID is missing", "last_success": "-", "meta": {"configured": smartthings_configured, "oauth_refresh_ready": smartthings_refresh_ready}})
    checks.append({"key": "media", "label": "Media Session", "status": "ok", "summary": "Now playing / media session info", "detail": media_title or (f"Source: {media_source_app}" if media_source_app else "No active media session is currently exposed"), "last_success": _format_health_timestamp(last_update_ts if (media_title or media_source_app) else 0), "meta": {"source_app": media_source_app or "-", "is_playing": bool(cached.get("media_is_playing"))}})
    checks.append({"key": "websocket", "label": "WebSocket Broadcast", "status": "ok", "summary": "Live status broadcast channel", "detail": f"Connected clients: {len(get_ws_clients_snapshot())}", "last_success": _format_health_timestamp(now), "meta": {}})

    configuration.extend([
        {"label": "Meteo", "value": "Ready" if weather_configured else "Missing", "detail": f"City: {meteo_cfg.get('location_query') or '-'}", "status": "ok" if weather_configured else "warn"},
        {"label": "SmartThings", "value": "Ready" if smartthings_configured else "Missing", "detail": f"Device: {str(smartthings_cfg.get('device_id') or '-')[:24]}", "status": "ok" if smartthings_configured else "warn"},
        {"label": "Tuya Local", "value": "Ready" if tuya_local_configured else "Missing", "detail": f"Device definitions: {configured_device_count}", "status": "ok" if tuya_local_configured else "warn"},
        {"label": "Tuya Cloud", "value": "Ready" if tuya_cloud_configured else "Missing", "detail": f"Access ID: {_mask_secret(tuya_api_cfg.get('access_id')) or '-'}", "status": "ok" if tuya_cloud_configured else "warn"},
        {"label": "WebView/Runtime", "value": "Running" if SERVER_READY.is_set() else "Waiting", "detail": f"WS clients: {len(get_ws_clients_snapshot())}", "status": "ok" if SERVER_READY.is_set() else "warn"},
        {"label": "Log Files", "value": "Ready", "detail": f"Errors: {len(recent_error_logs)} | Logs: {len(recent_general_logs)} | Tuya: {len(recent_tuya_file_logs)}", "status": "ok"},
    ])

    issues = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        check_status = check.get("status")
        if check_status in {"warn", "error"}:
            issues.append({"label": check.get("label"), "status": check_status, "detail": check.get("detail"), "suggestion": "Recheck the related settings and logs."})

    overall_status = "error" if any(c.get("status") == "error" for c in checks if isinstance(c, dict)) else ("warn" if any(c.get("status") == "warn" for c in checks if isinstance(c, dict)) else "ok")
    recent_events = []
    if recent_tuya_error:
        recent_events.append({"source": "Tuya", "level": "error", "time": recent_tuya_error.get("time") or recent_tuya_error.get("ts") or "-", "message": recent_tuya_error.get("message") or "Tuya error"})
    if weather_error:
        recent_events.append({"source": "Weather", "level": "warn", "time": _format_health_timestamp(now), "message": str(weather_error)})
    if cache_age is not None and cache_age > 10:
        recent_events.append({"source": "System Cache", "level": "error", "time": _format_health_timestamp(last_update_ts), "message": f"System cache is stale ({cache_age:.1f} sec)."})

    return {
        "ok": True,
        "summary": {"overall_status": overall_status, "generated_at": _format_health_timestamp(now), "generated_relative": _format_health_relative_age(0), "online_checks": sum(1 for c in checks if c.get("status") == "ok"), "warning_checks": sum(1 for c in checks if c.get("status") == "warn"), "error_checks": sum(1 for c in checks if c.get("status") == "error"), "tuya_online": tuya_online, "tuya_total": len(tuya_devices), "last_cache_update": _format_health_timestamp(last_update_ts), "cache_age": _format_health_relative_age(cache_age), "ws_clients": len(get_ws_clients_snapshot()), "last_hwinfo": _format_health_timestamp(hwinfo_last_seen)},
        "snapshots": snapshots,
        "configuration": configuration,
        "checks": checks,
        "issues": issues,
        "recent_events": recent_events[:12],
    }


def _json_safe_health_payload(value):
    if isinstance(value, dict):
        return {str(k): _json_safe_health_payload(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe_health_payload(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe_health_payload(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    try:
        return str(value)
    except Exception:
        return repr(value)

async def api_health_report(_request):
    try:
        payload = await asyncio.to_thread(_build_health_report)
        if not isinstance(payload, dict):
            payload = {"ok": False, "error": str(payload)}
        return web.json_response(_json_safe_health_payload(payload), headers=NO_CACHE_HEADERS)
    except Exception as exc:
        try:
            import traceback
            log_error("Health report could not be created:\n" + traceback.format_exc())
        except Exception:
            log_error(f"Health report could not be created: {exc}")
        return web.json_response({"ok": False, "error": str(exc)}, status=500, headers=NO_CACHE_HEADERS)

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.
__all__ = [name for name in globals() if not name.startswith("__")]


from panel_logging import LOGGER
from app_logging import _translate_log_text, _repair_mojibake_text
from settings_runtime import load_settings
from panel_hwinfo_process import get_hwinfo_app_status, restart_hwinfo_application_if_needed
from panel_ws_clients import get_ws_clients_snapshot, _safe_ws_send_json
from panel_assets import _load_html_response
from panel_tuya import _safe_float, PC_PLUG_QUERY_CACHE, PC_PLUG_CLOUD_CACHE, get_tuya_devices_config

def _get_cached_weather_payload(): return {}

async def tuya_devices_status(r):
    from tuya_runtime import tuya_get_cached_devices, tuya_public_devices_payload
    devices = tuya_get_cached_devices()
    return web.json_response(tuya_public_devices_payload(devices), headers=NO_CACHE_HEADERS)

async def tuya_toggle(r):
    from tuya_runtime import tuya_toggle_device_fast
    device_key = r.match_info.get('device_key')
    res = await asyncio.to_thread(tuya_toggle_device_fast, device_key)
    return web.json_response(res, headers=NO_CACHE_HEADERS)

async def tuya_set_brightness(r):
    from tuya_runtime import tuya_set_device_brightness_fast
    device_key = r.match_info.get('device_key')
    try: val = int(r.query.get('value', 0))
    except: val = 0
    res = await asyncio.to_thread(tuya_set_device_brightness_fast, device_key, val)
    return web.json_response(res, headers=NO_CACHE_HEADERS)

async def api_tuya_check(r):
    from tuya_runtime import refresh_tuya_cache_once, tuya_get_cached_devices, tuya_public_devices_payload
    await asyncio.to_thread(refresh_tuya_cache_once)
    devices = tuya_get_cached_devices()
    return web.json_response({'ok': True, 'devices': tuya_public_devices_payload(devices)}, headers=NO_CACHE_HEADERS)

async def api_tuya_reset(r):
    from tuya_runtime import tuya_reload_devices_and_pool, tuya_get_cached_devices, tuya_public_devices_payload
    await asyncio.to_thread(tuya_reload_devices_and_pool, True)
    devices = tuya_get_cached_devices()
    return web.json_response({'ok': True, 'devices': tuya_public_devices_payload(devices)}, headers=NO_CACHE_HEADERS)

def _get_pc_plug_debug_info():
    from panel_tuya import _query_pc_plug_status_unified
    return _query_pc_plug_status_unified(force=True)
