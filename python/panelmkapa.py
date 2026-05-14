# File Version: 1.2
import argparse
import asyncio
import json
import sys
import threading
import time

from aiohttp import web
from monitorcontrol import get_monitors

from panelmkapa_safe import POWER_OFF, POWER_ON, _enumerate_monitors
from settings_runtime import load_settings, save_settings

_MONITOR_ROUTES_REGISTERED = False
_TARGET_CACHE_LOCK = threading.Lock()
_TARGET_MONITOR_CACHE = {
    "fingerprint": "",
    "index": -1,
    "monitor": None,
    "info": None,
    "expires_at": 0.0,
}
_TARGET_CACHE_TTL_SECONDS = 3600.0
_POWER_COMMAND_LOCK = threading.Lock()


def _get_no_cache_headers():
    try:
        from panel_globals import NO_CACHE_HEADERS
        return NO_CACHE_HEADERS
    except Exception:
        return {
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
        }


def _log_monitor_power_error(message):
    try:
        from panel_logging import log_error
        log_error(message)
    except Exception:
        print(message)


def _get_target_fingerprint():
    settings = load_settings() or {}
    monitor_power = settings.get("monitor_power") if isinstance(settings, dict) else {}
    return str((monitor_power or {}).get("target_fingerprint") or "").strip()


def _get_target_config():
    settings = load_settings() or {}
    monitor_power = settings.get("monitor_power") if isinstance(settings, dict) else {}
    if not isinstance(monitor_power, dict):
        monitor_power = {}
    try:
        target_index = int(monitor_power.get("target_index") if str(monitor_power.get("target_index", "")).strip() else -1)
    except Exception:
        target_index = -1
    return {
        "fingerprint": str(monitor_power.get("target_fingerprint") or "").strip(),
        "index": target_index,
        "description": str(monitor_power.get("target_description") or "").strip(),
    }


def _set_target_fingerprint(fingerprint):
    settings = load_settings(force_reload=True) or {}
    monitor_power = settings.setdefault("monitor_power", {})
    if not isinstance(monitor_power, dict):
        monitor_power = {}
        settings["monitor_power"] = monitor_power
    monitor_power["target_fingerprint"] = str(fingerprint or "").strip()
    save_settings(settings)


def _set_target_config(fingerprint, index=-1, description=""):
    settings = load_settings(force_reload=True) or {}
    monitor_power = settings.setdefault("monitor_power", {})
    if not isinstance(monitor_power, dict):
        monitor_power = {}
        settings["monitor_power"] = monitor_power
    monitor_power["target_fingerprint"] = str(fingerprint or "").strip()
    monitor_power["target_index"] = int(index) if index is not None else -1
    monitor_power["target_description"] = str(description or "").strip()
    save_settings(settings)


def _remember_target_monitor(fingerprint, index, monitor, info):
    with _TARGET_CACHE_LOCK:
        _TARGET_MONITOR_CACHE.update({
            "fingerprint": str(fingerprint or "").strip(),
            "index": int(index),
            "monitor": monitor,
            "info": dict(info or {}),
            "expires_at": time.time() + _TARGET_CACHE_TTL_SECONDS,
        })


def _forget_target_monitor():
    with _TARGET_CACHE_LOCK:
        _TARGET_MONITOR_CACHE.update({
            "fingerprint": "",
            "index": -1,
            "monitor": None,
            "info": None,
            "expires_at": 0.0,
        })


def _resolve_from_cache(target_fingerprint):
    with _TARGET_CACHE_LOCK:
        if (
            _TARGET_MONITOR_CACHE.get("fingerprint") == target_fingerprint
            and _TARGET_MONITOR_CACHE.get("monitor") is not None
            and time.time() < float(_TARGET_MONITOR_CACHE.get("expires_at") or 0.0)
        ):
            return (
                int(_TARGET_MONITOR_CACHE.get("index")),
                _TARGET_MONITOR_CACHE.get("monitor"),
                dict(_TARGET_MONITOR_CACHE.get("info") or {}),
            )
    return None


def _resolve_from_saved_index(target_config):
    target_fingerprint = str(target_config.get("fingerprint") or "").strip()
    target_index = int(target_config.get("index") if target_config.get("index") is not None else -1)
    if not target_fingerprint or target_index < 0:
        return None

    monitors = get_monitors()
    if target_index >= len(monitors):
        raise RuntimeError("Selected monitor power target is not currently available. Re-select it in Settings.")

    monitor = monitors[target_index]
    description = str(getattr(getattr(monitor, "vcp", None), "description", "") or "")
    expected_description = str(target_config.get("description") or "").strip()
    if expected_description and description and description != expected_description:
        raise RuntimeError("Selected monitor power target changed position. Re-select it in Settings.")

    info = {
        "fingerprint": target_fingerprint,
        "index": target_index,
        "description": description,
        "fast_resolved": True,
    }
    _remember_target_monitor(target_fingerprint, target_index, monitor, info)
    return target_index, monitor, info


def _monitor_label(info, index):
    model = str(info.get("model") or "?")
    kind = str(info.get("type") or "?")
    mccs = str(info.get("mccs_ver") or "?")
    ddc = "DDC" if info.get("ddc") else "no DDC"
    return f"[{index}] {model} {kind} MCCS {mccs} ({ddc})"


def list_monitor_payload():
    target_fingerprint = _get_target_fingerprint()
    monitors = []
    for index, monitor, info in _enumerate_monitors():
        item = dict(info)
        item["index"] = index
        item["label"] = _monitor_label(item, index)
        item["target"] = bool(target_fingerprint and item.get("fingerprint") == target_fingerprint)
        if item["target"]:
            _remember_target_monitor(target_fingerprint, index, monitor, item)
        monitors.append(item)
    target = next((item for item in monitors if item.get("target")), None)
    return {
        "ok": True,
        "target_found": target is not None,
        "target_fingerprint": target_fingerprint,
        "target": target,
        "monitors": monitors,
    }


def _resolve_panel_monitor():
    target_config = _get_target_config()
    target_fingerprint = target_config.get("fingerprint")
    if not target_fingerprint:
        raise RuntimeError("Monitor power target is not selected. Open Settings > Services > Monitor Power and choose a monitor.")

    cached = _resolve_from_cache(target_fingerprint)
    if cached is not None:
        return cached

    fast_match = _resolve_from_saved_index(target_config)
    if fast_match is not None:
        return fast_match

    matches = []
    for index, monitor, info in _enumerate_monitors():
        if str(info.get("fingerprint") or "") == target_fingerprint:
            matches.append((index, monitor, info))

    if len(matches) == 1:
        _remember_target_monitor(target_fingerprint, matches[0][0], matches[0][1], matches[0][2])
        return matches[0]
    if not matches:
        raise RuntimeError("Selected monitor power target is not currently available. Re-select it in Settings.")
    raise RuntimeError("Selected monitor power target matched multiple monitors. Re-select a unique target in Settings.")


def set_panel_power(mode):
    resolved_index, monitor, info = _resolve_panel_monitor()
    try:
        with monitor:
            monitor.set_power_mode(mode)
    except Exception:
        _forget_target_monitor()
        raise
    return {
        "ok": True,
        "action": "power",
        "index": resolved_index,
        "mode": "on" if mode == POWER_ON else "off",
        "target": info,
    }


def _run_power_command_background(mode):
    def _worker():
        if not _POWER_COMMAND_LOCK.acquire(blocking=False):
            return
        try:
            set_panel_power(mode)
        except Exception as exc:
            _log_monitor_power_error(f"Monitor power command failed: {exc}")
        finally:
            _POWER_COMMAND_LOCK.release()

    threading.Thread(target=_worker, daemon=True, name="monitor-power-command").start()


async def api_monitor_status(_request):
    try:
        payload = await asyncio.to_thread(list_monitor_payload)
        return web.json_response(payload, headers=_get_no_cache_headers())
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500, headers=_get_no_cache_headers())


async def api_monitor_on(_request):
    try:
        target_config = _get_target_config()
        if not target_config.get("fingerprint"):
            raise RuntimeError("Monitor power target is not selected. Open Settings > Services > Monitor Power and choose a monitor.")
        _run_power_command_background(POWER_ON)
        return web.json_response({
            "ok": True,
            "action": "power",
            "mode": "on",
            "queued": True,
        }, status=202, headers=_get_no_cache_headers())
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500, headers=_get_no_cache_headers())


async def api_monitor_off(_request):
    try:
        payload = await asyncio.to_thread(set_panel_power, POWER_OFF)
        return web.json_response(payload, headers=_get_no_cache_headers())
    except Exception as exc:
        return web.json_response({"ok": False, "error": str(exc)}, status=500, headers=_get_no_cache_headers())


def register_monitor_routes():
    global _MONITOR_ROUTES_REGISTERED
    if _MONITOR_ROUTES_REGISTERED:
        return
    try:
        from panel_routes_window_main import app as app_obj
    except Exception:
        return

    routes = [
        ("GET", "/monitor/status", api_monitor_status),
        ("GET", "/monitor/list", api_monitor_status),
        ("GET", "/monitor/on", api_monitor_on),
        ("POST", "/monitor/on", api_monitor_on),
        ("GET", "/monitor/off", api_monitor_off),
        ("POST", "/monitor/off", api_monitor_off),
    ]
    for method, path, handler in routes:
        try:
            app_obj.router.add_route(method, path, handler)
        except Exception:
            pass
    _MONITOR_ROUTES_REGISTERED = True


def cli_main():
    parser = argparse.ArgumentParser(description="Panel monitor power control using the target selected in settings.")
    parser.add_argument("command", choices=["list", "select", "on", "off"])
    parser.add_argument("--index", type=int, default=None, help="Monitor index for select.")
    parser.add_argument("--json", action="store_true", help="Print JSON output for list.")
    args = parser.parse_args()

    try:
        payload = list_monitor_payload()
        if args.command == "list":
            if args.json:
                print(json.dumps(payload.get("monitors", []), ensure_ascii=False, indent=2))
            else:
                for item in payload.get("monitors", []):
                    suffix = "  <-- settings target" if item.get("target") else ""
                    print(f"{item.get('label')}{suffix}")
                    print(f"    fingerprint={item.get('fingerprint')}")
                if not payload.get("target_fingerprint"):
                    print("No monitor power target selected in settings.")
            return 0

        if args.command == "select":
            if args.index is None:
                print("select requires --index. Example: py python\\panelmkapa.py select --index 1")
                return 1
            selected = next((item for item in payload.get("monitors", []) if int(item.get("index")) == int(args.index)), None)
            if not selected:
                print(f"Monitor index not found: {args.index}")
                return 1
            if not selected.get("ddc"):
                print(f"Monitor index {args.index} does not expose DDC/CI controls.")
                return 1
            _set_target_config(selected.get("fingerprint"), selected.get("index"), selected.get("description"))
            print(f"Saved monitor power target: {selected.get('label')}")
            return 0

        result = set_panel_power(POWER_ON if args.command == "on" else POWER_OFF)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"HATA: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(cli_main())
