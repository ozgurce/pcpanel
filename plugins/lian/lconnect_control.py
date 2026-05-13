import argparse
import glob
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import re


PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(os.path.dirname(PLUGIN_DIR))
JSON_DIR = os.path.join(BASE_DIR, "json", "lian")
PROFILE_PATH = os.path.join(JSON_DIR, "lconnect_profiles.json")
LAST_STATE_PATH = os.path.join(JSON_DIR, "last_lconnect_state.json")
DEFAULT_SERVICE_URL = "http://127.0.0.1:11021/"
DEFAULT_LCONNECT_DATA_DIR = r"C:\ProgramData\Lian-Li\L-Connect 3"


class LConnectError(RuntimeError):
    pass


def _load_profile(path=PROFILE_PATH):
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise LConnectError("profile file is not an object")
    return data


def _read_gzip_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json_atomic(path, data):
    folder = os.path.dirname(os.path.abspath(path))
    if folder:
        os.makedirs(folder, exist_ok=True)
    temp_path = f"{path}.tmp"
    with open(temp_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(temp_path, path)


def _clamp(value, low, high):
    return max(low, min(high, value))


def _percent(value, default):
    try:
        parsed = int(round(float(value)))
    except (TypeError, ValueError):
        parsed = int(default)
    return _clamp(parsed, 0, 100)


def _rf_brightness(percent):
    value = _percent(percent, 100)
    if value <= 0:
        return 0
    if value <= 25:
        return 64
    if value <= 50:
        return 128
    if value <= 75:
        return 192
    return 255


def _rf_speed(percent):
    value = _percent(percent, 50)
    if value <= 0:
        return 7
    if value <= 25:
        return 6
    if value <= 50:
        return 5
    if value <= 75:
        return 4
    return 3


def _json_default(value):
    if hasattr(value, "__dict__"):
        return value.__dict__
    raise TypeError(f"{type(value).__name__} is not JSON serializable")


class LConnectClient:
    def __init__(self, service_url=DEFAULT_SERVICE_URL, timeout=2.5):
        self.service_url = (service_url or DEFAULT_SERVICE_URL).rstrip("/") + "/"
        self.timeout = float(timeout)

    def request(self, action, body=None, query=None, timeout=None):
        params = {"action": str(action)}
        if query:
            params.update({str(k): str(v) for k, v in dict(query).items()})
        url = self.service_url + "?" + urllib.parse.urlencode(params)
        payload = b""
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False, separators=(",", ":"), default=_json_default).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json;charset=UTF-8", "User-Agent": ""},
        )
        try:
            with urllib.request.urlopen(req, timeout=float(timeout or self.timeout)) as response:
                raw = response.read()
                text = raw.decode("utf-8", errors="replace") if raw else ""
                try:
                    parsed = json.loads(text) if text else None
                except Exception:
                    parsed = text
                return {
                    "ok": 200 <= int(response.status) < 300,
                    "status": int(response.status),
                    "action": action,
                    "query": query or {},
                    "data": parsed,
                    "raw": text,
                }
        except urllib.error.URLError as exc:
            raise LConnectError(str(exc)) from exc

    def ping(self):
        return self.request("Ping", timeout=min(self.timeout, 1.5))

    def sync_controller_list(self):
        return self.request("SyncControllerList")

    def lwireless(self, request_type, body):
        return self.request("LWireless", body=body, query={"type": request_type})

    def device(self, device_path, request_type, body=None):
        return self.request("Device", body=body, query={"devicePath": device_path, "type": request_type})

    def set_wmerge_lighting_effect(self, body):
        return self.request("SetWMergeLightingEffect", body=body)

    def apply_wmerge_lighting_effect(self, body):
        return self.request("ApplyWMergeLightingEffect", body=body)


def _profile_brightness(config, mode):
    profiles = config.get("profiles") or {}
    profile = profiles.get(mode) or {}
    if "brightness_percent" in profile:
        return profile["brightness_percent"]
    return 100 if mode == "on" else 0


def _normalize_mac(value):
    text = str(value or "").strip().lower()
    return text if re.match(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$", text) else ""


def _configured_merge_devices(config):
    return [
        dict(item)
        for item in list(config.get("devices") or [])
        if _normalize_mac(item.get("mac")) and (int(item.get("fan_count") or 0) > 0 or int(item.get("led_num") or 0) > 0)
    ]


def _device_direction_map(snapshot):
    body = (snapshot or {}).get("setting_body") or {}
    macs = list(body.get("PortOrderList") or [])
    directions = list(body.get("DirectionList") or [])
    result = {}
    for idx, mac in enumerate(macs):
        normalized = _normalize_mac(mac)
        if not normalized:
            continue
        try:
            result[normalized] = int(directions[idx])
        except Exception:
            result[normalized] = 0
    return result


def _find_lconnect_device_paths(config):
    data_dir = config.get("lconnect_data_dir") or DEFAULT_LCONNECT_DATA_DIR
    return glob.glob(os.path.join(data_dir, "device", "*", "*.0"))


def _discover_active_lwireless_macs(config):
    macs = []
    seen = set()
    for path in _find_lconnect_device_paths(config):
        try:
            data = _read_gzip_json(path)
        except Exception:
            continue
        if data.get("DeviceID") != "LWireless-Controller":
            continue
        if data.get("Type") not in {"Fan", "Pump", "Case"}:
            continue
        payload = data.get("Data")
        if not isinstance(payload, dict):
            continue
        for raw_mac in payload.keys():
            mac = _normalize_mac(raw_mac)
            if mac and mac not in seen:
                seen.add(mac)
                macs.append(mac)
    return macs


def _merge_devices(config, snapshot=None):
    configured = _configured_merge_devices(config)
    configured_by_mac = {_normalize_mac(item.get("mac")): item for item in configured}
    configured_order = {_normalize_mac(item.get("mac")): int(item.get("sort_index") or idx + 1) for idx, item in enumerate(configured)}
    direction_by_mac = _device_direction_map(snapshot)
    active_macs = _discover_active_lwireless_macs(config)
    source_macs = active_macs or [_normalize_mac(item.get("mac")) for item in configured]

    devices = []
    for idx, mac in enumerate(source_macs):
        if not mac:
            continue
        item = dict(configured_by_mac.get(mac) or {})
        item["mac"] = mac
        item.setdefault("fan_count", 1)
        item.setdefault("led_num", 1)
        item["sort_index"] = configured_order.get(mac, len(configured_order) + idx + 1)
        if mac in direction_by_mac:
            item["direction"] = int(direction_by_mac[mac])
        devices.append(item)

    devices = sorted(devices, key=lambda item: int(item.get("sort_index") or 0))
    if not devices:
        raise LConnectError("no merge devices in profile")
    return devices


def _black_color():
    return {
        "ColorContext": None,
        "A": 255,
        "R": 0,
        "G": 0,
        "B": 0,
        "ScA": 1,
        "ScR": 0,
        "ScG": 0,
        "ScB": 0,
    }


def _device_order(devices):
    directions = []
    for item in devices:
        if "direction" in item:
            try:
                directions.append(int(item.get("direction") or 0))
                continue
            except Exception:
                pass
        directions.append(1 if item.get("is_reverse") else 0)
    return [str(d.get("mac")) for d in devices], directions


def _apply_body(port_order, directions):
    return {"PortOrderList": port_order, "DirectionList": directions}


def _setting_body_from_device_state(device_state):
    data = (device_state or {}).get("Data") or {}
    lighting = data.get("LightingEffectSetting") or {}
    devices = data.get("DeviceList") or []
    port_order = [str(item.get("MacStr")) for item in devices if item.get("MacStr")]
    directions = [int(item.get("Direction") or 0) for item in devices if item.get("MacStr")]
    if not port_order or not lighting:
        return None
    return {
        "PortOrderList": port_order,
        "DirectionList": directions,
        "MergeMode": int(lighting.get("UIEffect", 5)),
        "Scope": int(lighting.get("EffectScope", 2)),
        "Speed": int(lighting.get("SpeedType", 5)),
        "Direction": int(lighting.get("iDir", 0)),
        "Brightness": int(lighting.get("BrightnessType", 255)),
        "Color": list(lighting.get("UserColors") or []),
    }


def _is_black_color(color):
    return int(color.get("R") or 0) == 0 and int(color.get("G") or 0) == 0 and int(color.get("B") or 0) == 0


def _is_off_setting_body(body):
    if not body:
        return False
    colors = list(body.get("Color") or [])
    if int(body.get("Brightness") or 0) == 0:
        return True
    return int(body.get("MergeMode") or 0) == 3 and bool(colors) and all(_is_black_color(color) for color in colors)


def _find_merge_state_path(config):
    configured = config.get("merge_state_path")
    if configured and os.path.exists(configured):
        return configured
    for path in _find_lconnect_device_paths(config):
        try:
            data = _read_gzip_json(path)
        except Exception:
            continue
        if data.get("Type") == "MergeLightingEffectSetting":
            return path
    return None


def _capture_current_state(config):
    path = _find_merge_state_path(config)
    if not path:
        return None
    device_state = _read_gzip_json(path)
    setting_body = _setting_body_from_device_state(device_state)
    if not setting_body:
        return None
    return {
        "captured_at": int(time.time()),
        "source_path": path,
        "device_state": device_state,
        "setting_body": setting_body,
    }


def _load_last_state(path=LAST_STATE_PATH):
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        return None
    return data


def _save_last_state(snapshot, path=LAST_STATE_PATH):
    _write_json_atomic(path, snapshot)


def _find_lwireless_state_paths(config, device_type):
    wanted_type = str(device_type or "").strip().lower()
    paths = []
    for path in _find_lconnect_device_paths(config):
        try:
            data = _read_gzip_json(path)
        except Exception:
            continue
        if data.get("DeviceID") != "LWireless-Controller":
            continue
        if str(data.get("Type") or "").strip().lower() != wanted_type:
            continue
        paths.append(path)
    return paths


def _pump_lcd_config(config):
    pump_lcd = dict((config or {}).get("pump_lcd") or {})
    pump_lcd.setdefault("enabled", True)
    pump_lcd.setdefault("brightness_off", 0)
    pump_lcd.setdefault("brightness_on", 25)
    return pump_lcd


def _pump_lcd_macs(config):
    pump_lcd = _pump_lcd_config(config)
    macs = []
    for value in list(pump_lcd.get("macs") or []):
        mac = _normalize_mac(value)
        if mac:
            macs.append(mac)
    return macs


def _capture_pump_lcd_state(config):
    pump_lcd = _pump_lcd_config(config)
    if not bool(pump_lcd.get("enabled", True)):
        return []

    wanted_macs = set(_pump_lcd_macs(config))
    snapshots = []
    for path in _find_lwireless_state_paths(config, "Pump"):
        try:
            data = _read_gzip_json(path)
        except Exception:
            continue
        payload = data.get("Data")
        if not isinstance(payload, dict):
            continue
        for raw_mac, body in payload.items():
            mac = _normalize_mac(raw_mac)
            if not mac or (wanted_macs and mac not in wanted_macs):
                continue
            aio = (body or {}).get("AioParams") or {}
            if "LcdBrightness" not in aio:
                continue
            try:
                brightness = int(aio.get("LcdBrightness"))
            except Exception:
                brightness = int(pump_lcd.get("brightness_on", 25))
            snapshots.append({"path": path, "mac": mac, "brightness": _clamp(brightness, 0, 100)})
    return snapshots


def _pump_lcd_snapshot_map(snapshot):
    result = {}
    for item in list((snapshot or {}).get("pump_lcd") or []):
        mac = _normalize_mac(item.get("mac"))
        if not mac:
            continue
        try:
            result[mac] = _clamp(int(item.get("brightness")), 0, 100)
        except Exception:
            pass
    return result


def _apply_pump_lcd_brightness(config, client, mode, snapshot=None):
    pump_lcd = _pump_lcd_config(config)
    if not bool(pump_lcd.get("enabled", True)):
        return {"ok": True, "action": "Device", "query": {"type": "SetPumpLCDBrightness"}, "skipped": True, "reason": "pump_lcd disabled"}

    # Captured from L-Connect/Wireshark. This is the real LCD brightness endpoint.
    # Decodes to: usb\\vid_0416&pid_8040\\7&1eeeae73&0&3
    device_path = str(pump_lcd.get("device_path") or "dXNiXFx2aWRfMDQxNiZwaWRfODA0MFxcNyYxZWVlYWU3MyYwJjM=")
    # Accept both raw and already-url-encoded values in config; urllib will encode it exactly once.
    device_path = urllib.parse.unquote(device_path)

    wanted_macs = set(_pump_lcd_macs(config))
    snapshot_brightness = _pump_lcd_snapshot_map(snapshot)
    default_on = _clamp(int(pump_lcd.get("brightness_on", 25)), 0, 100)
    off_value = _clamp(int(pump_lcd.get("brightness_off", 0)), 0, 100)
    changed = []
    results = []

    # Find pump LCD MACs from L-Connect cache, but DO NOT write to the cache file.
    for path in _find_lwireless_state_paths(config, "Pump"):
        try:
            data = _read_gzip_json(path)
        except Exception:
            continue
        payload = data.get("Data")
        if not isinstance(payload, dict):
            continue

        for raw_mac, device_body in payload.items():
            mac = _normalize_mac(raw_mac)
            if not mac or (wanted_macs and mac not in wanted_macs):
                continue
            aio = (device_body or {}).get("AioParams")
            if not isinstance(aio, dict) or "LcdBrightness" not in aio:
                continue

            if mode == "off":
                target = off_value
            else:
                target = snapshot_brightness.get(mac, default_on)
            target = _clamp(int(target), 0, 100)

            # Captured request body length matches this shape, e.g.
            # {"Brightness":25,"MacStr":"9b:67:63:62:32:e1"}
            body = {"Brightness": target, "MacStr": mac}
            result = client.device(device_path, "SetPumpLCDBrightness", body)
            results.append(result)
            changed.append({"mac": mac, "brightness": target})

    if not results:
        return {"ok": True, "action": "Device", "query": {"type": "SetPumpLCDBrightness", "devicePath": device_path}, "skipped": True, "reason": "no pump lcd brightness found"}

    return {
        "ok": all(bool(item.get("ok")) for item in results),
        "action": "Device",
        "query": {"type": "SetPumpLCDBrightness", "devicePath": device_path},
        "changed": changed,
        "results": results,
    }

def _quick_sync_bodies(config, mode, devices):
    merge = config.get("merge") or {}
    brightness_percent = _percent(_profile_brightness(config, mode), 100 if mode == "on" else 0)
    brightness = _rf_brightness(brightness_percent)
    speed = _rf_speed(merge.get("speed_percent", 50))
    port_order, directions = _device_order(devices)
    setting_body = {
        "PortOrderList": port_order,
        "DirectionList": directions,
        "MergeMode": int(merge.get("mode", 5)),
        "Scope": int(merge.get("scope", 2)),
        "Speed": speed,
        "Direction": int(merge.get("direction", 0)),
        "Brightness": brightness,
        "Color": list(merge.get("colors") or []),
    }
    apply_body = _apply_body(port_order, directions)
    return setting_body, apply_body, brightness_percent, brightness


def _off_bodies(config, devices):
    merge = config.get("merge") or {}
    port_order, directions = _device_order(devices)
    brightness = 0
    setting_body = {
        "PortOrderList": port_order,
        "DirectionList": directions,
        "MergeMode": 3,
        "Scope": int(merge.get("scope", 2)),
        "Speed": _rf_speed(merge.get("speed_percent", 50)),
        "Direction": int(merge.get("direction", 0)),
        "Brightness": brightness,
        "Color": [_black_color()],
    }
    return setting_body, _apply_body(port_order, directions), 0, brightness


def _restore_bodies(snapshot, config, devices):
    setting_body = (snapshot or {}).get("setting_body")
    if not setting_body:
        device_state = (snapshot or {}).get("device_state")
        setting_body = _setting_body_from_device_state(device_state)
    if not setting_body or _is_off_setting_body(setting_body):
        return _quick_sync_bodies(config, "on", devices)
    port_order, directions = _device_order(devices)
    setting_body = dict(setting_body)
    setting_body["PortOrderList"] = port_order
    setting_body["DirectionList"] = directions
    return setting_body, _apply_body(port_order, directions), None, int(setting_body.get("Brightness") or 0)


def apply_lights(mode, config=None, client=None, state_path=LAST_STATE_PATH):
    mode = str(mode or "").strip().lower()
    aliases = {"ac": "on", "acik": "on", "open": "on", "kapat": "off", "kapali": "off", "close": "off"}
    mode = aliases.get(mode, mode)
    if mode not in {"on", "off"}:
        raise LConnectError(f"invalid mode: {mode}")

    config = config or _load_profile()
    client = client or LConnectClient(config.get("service_url") or DEFAULT_SERVICE_URL)
    restore_source = "profile"
    snapshot_saved = False
    if mode == "off":
        snapshot = _capture_current_state(config) or {}
        snapshot["pump_lcd"] = _capture_pump_lcd_state(config)
        devices = _merge_devices(config, snapshot=snapshot)
        if not _is_off_setting_body(snapshot.get("setting_body")) or snapshot.get("pump_lcd"):
            _save_last_state(snapshot, path=state_path)
            snapshot_saved = True
        setting_body, apply_body, brightness_percent, brightness = _off_bodies(config, devices)
        restore_source = "snapshot" if snapshot_saved else "off"
    else:
        snapshot = _load_last_state(path=state_path)
        devices = _merge_devices(config, snapshot=snapshot)
        if snapshot:
            setting_body, apply_body, brightness_percent, brightness = _restore_bodies(snapshot, config, devices)
            restore_source = "snapshot"
        else:
            setting_body, apply_body, brightness_percent, brightness = _quick_sync_bodies(config, mode, devices)
    started = time.perf_counter()
    results = []
    results.append(client.ping())
    results.append(client.set_wmerge_lighting_effect(setting_body))
    results.append(client.apply_wmerge_lighting_effect(apply_body))
    pump_lcd_result = _apply_pump_lcd_brightness(config, client, mode, snapshot=snapshot if 'snapshot' in locals() else None)
    results.append(pump_lcd_result)

    ok = all(bool(item.get("ok")) for item in results)
    return {
        "ok": ok,
        "mode": mode,
        "brightness_percent": brightness_percent,
        "brightness_rf": brightness,
        "device_count": len(devices),
        "device_macs": [str(item.get("mac")) for item in devices],
        "pump_lcd": pump_lcd_result,
        "quick_sync": True,
        "restore_source": restore_source,
        "snapshot_saved": snapshot_saved,
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "results": results,
    }


def get_status(config=None, client=None):
    config = config or _load_profile()
    client = client or LConnectClient(config.get("service_url") or DEFAULT_SERVICE_URL)
    started = time.perf_counter()
    ping = client.ping()
    controllers = client.sync_controller_list()
    return {
        "ok": bool(ping.get("ok")) and bool(controllers.get("ok")),
        "elapsed_ms": int((time.perf_counter() - started) * 1000),
        "ping": ping,
        "controllers": controllers,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Control L-Connect 3 lights through its local HTTP service.")
    parser.add_argument("command", choices=["on", "off", "ac", "acik", "kapat", "kapali", "status", "ping"])
    parser.add_argument("--profile", default=PROFILE_PATH)
    parser.add_argument("--state-cache", default=LAST_STATE_PATH)
    parser.add_argument("--data-dir", default="")
    parser.add_argument("--merge-state-path", default="")
    parser.add_argument("--service-url", default="")
    parser.add_argument("--timeout", type=float, default=2.5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    config = _load_profile(args.profile)
    if args.data_dir:
        config["lconnect_data_dir"] = args.data_dir
    if args.merge_state_path:
        config["merge_state_path"] = args.merge_state_path
    if args.service_url:
        config["service_url"] = args.service_url
    client = LConnectClient(config.get("service_url") or DEFAULT_SERVICE_URL, timeout=args.timeout)
    try:
        if args.command == "ping":
            result = client.ping()
        elif args.command == "status":
            result = get_status(config, client=client)
        else:
            result = apply_lights(args.command, config=config, client=client, state_path=args.state_cache)
        if args.json:
            print(json.dumps(result, ensure_ascii=False))
        else:
            print(f"ok={bool(result.get('ok'))} command={args.command} elapsed_ms={result.get('elapsed_ms', 0)}")
        return 0 if result.get("ok") else 1
    except Exception as exc:
        result = {"ok": False, "error": str(exc), "command": args.command}
        if args.json:
            print(json.dumps(result, ensure_ascii=False), file=sys.stderr)
        else:
            print(f"ok=False command={args.command} error={exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
