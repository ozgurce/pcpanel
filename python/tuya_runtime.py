# Ver. 0.7
import concurrent.futures
import json
import os
import re
import threading
import time
import hashlib
import hmac

try:
    import requests
except Exception:
    requests = None

from urllib import request as urllib_request
from collections import deque
from pprint import pformat

try:
    from settings_runtime import load_settings as _load_runtime_settings_file
except Exception:
    _load_runtime_settings_file = None

try:
    import tinytuya
    TINYTUYA_AVAILABLE = True
except Exception:
    tinytuya = None
    TINYTUYA_AVAILABLE = False

SYSTEM_CACHE = None
SENSOR_CACHE_LOCK = None
_LOG = None
_LOG_ERROR = None

def init_tuya_runtime(system_cache, sensor_cache_lock, log_func=None, log_error_func=None, devices_file=None):
    global SYSTEM_CACHE, SENSOR_CACHE_LOCK, _LOG, _LOG_ERROR, TUYA_DEVICES_FILE
    SYSTEM_CACHE = system_cache
    SENSOR_CACHE_LOCK = sensor_cache_lock
    _LOG = log_func
    _LOG_ERROR = log_error_func
    if devices_file:
        TUYA_DEVICES_FILE = devices_file

def log(message: str):
    if callable(_LOG):
        _LOG(message)

def log_error(message: str):
    if callable(_LOG_ERROR):
        _LOG_ERROR(message)
    elif callable(_LOG):
        _LOG(message)

SETTINGS_CACHE_LOCK = threading.Lock()
SETTINGS_CACHE = {"data": None, "last_refresh": 0.0}
SETTINGS_CACHE_TTL_SECONDS = 1.0


def _load_runtime_settings(force=False):
    if not callable(_load_runtime_settings_file):
        return {}
    now = time.time()
    with SETTINGS_CACHE_LOCK:
        cached = SETTINGS_CACHE.get("data")
        if (not force) and isinstance(cached, dict) and (now - float(SETTINGS_CACHE.get("last_refresh") or 0.0)) < SETTINGS_CACHE_TTL_SECONDS:
            return cached
        try:
            data = _load_runtime_settings_file(force_reload=force) or {}
        except TypeError:
            data = _load_runtime_settings_file() or {}
        except Exception:
            return cached if isinstance(cached, dict) else {}
        if not isinstance(data, dict):
            data = {}
        SETTINGS_CACHE["data"] = data
        SETTINGS_CACHE["last_refresh"] = now
        return data


def refresh_tuya_settings_cache(force=True):
    return _load_runtime_settings(force=force)


def _settings_get(path, default=None):
    cur = _load_runtime_settings()
    for part in str(path or "").split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _settings_get_bool(path, default=False):
    value = _settings_get(path, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on", "evet"}
    return bool(value)

def _settings_int(path, default=0):
    try:
        return int(float(_settings_get(path, default)))
    except Exception:
        return int(default)


def _settings_int_any(paths, default=0):
    for path in paths:
        value = _settings_get(path, None)
        if value in (None, ""):
            continue
        try:
            return int(float(value))
        except Exception:
            continue
    return int(default)


def _get_tuya_local_timeout_seconds(default_ms=2500):
    configured = _settings_int_any(("tuya.local_command_timeout_ms", "tuya.device_timeout_ms"), default_ms)
    return max(0.75, min(12.0, float(configured) / 1000.0))


def _get_tuya_cloud_timeout_seconds(default_ms=8000):
    configured = _settings_int("tuya.cloud_command_timeout_ms", default_ms)
    return max(2.0, min(30.0, float(configured) / 1000.0))

TUYA_DEVICES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "json", "devices.json")
TUYA_DEVICES = None
TUYA_DEVICES_ERROR = None
TUYA_DEVICES_MTIME_NS = None
TUYA_DEVICES_LOCK = threading.Lock()

def _load_tuya_cloud_settings_values():
    env_base = os.environ.get("TUYA_CLOUD_BASE_URL", "https://openapi.tuyaeu.com").strip() or "https://openapi.tuyaeu.com"
    env_id = os.environ.get("TUYA_CLOUD_ACCESS_ID", "").strip()
    env_secret = os.environ.get("TUYA_CLOUD_ACCESS_SECRET", "").strip()

    settings_base = ""
    settings_id = ""
    settings_secret = ""

    if callable(_load_runtime_settings_file):
        try:
            settings = _load_runtime_settings() or {}
            api = settings.get("api") if isinstance(settings, dict) else {}
            tuya_cfg = api.get("tuya") if isinstance(api, dict) else {}
            settings_base = str(tuya_cfg.get("base_url") or "").strip()
            settings_id = str(tuya_cfg.get("access_id") or "").strip()
            settings_secret = str(tuya_cfg.get("access_secret") or "").strip()
        except Exception:
            settings_base = ""
            settings_id = ""
            settings_secret = ""

    return (
        settings_base or env_base or "https://openapi.tuyaeu.com",
        settings_id or env_id,
        settings_secret or env_secret,
    )


TUYA_CLOUD_BASE_URL, TUYA_CLOUD_ACCESS_ID, TUYA_CLOUD_ACCESS_SECRET = _load_tuya_cloud_settings_values()
TUYA_CLOUD_TOKEN_CACHE = {"token": None, "expire_at": 0.0}
TUYA_CLOUD_LOCK = threading.RLock()
TUYA_HTTP_SESSION = None
TUYA_HTTP_SESSION_LOCK = threading.RLock()


def _reset_tuya_http_session():
    global TUYA_HTTP_SESSION
    with TUYA_HTTP_SESSION_LOCK:
        session = TUYA_HTTP_SESSION
        TUYA_HTTP_SESSION = None
    if session is not None:
        try:
            session.close()
        except Exception:
            pass


def _get_tuya_http_session():
    global TUYA_HTTP_SESSION
    if requests is None:
        return None
    with TUYA_HTTP_SESSION_LOCK:
        if TUYA_HTTP_SESSION is None:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=0)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            TUYA_HTTP_SESSION = session
        return TUYA_HTTP_SESSION


def _refresh_tuya_cloud_settings():
    global TUYA_CLOUD_BASE_URL, TUYA_CLOUD_ACCESS_ID, TUYA_CLOUD_ACCESS_SECRET
    new_base, new_id, new_secret = _load_tuya_cloud_settings_values()

    changed = (new_base != TUYA_CLOUD_BASE_URL) or (new_id != TUYA_CLOUD_ACCESS_ID) or (new_secret != TUYA_CLOUD_ACCESS_SECRET)
    TUYA_CLOUD_BASE_URL = new_base
    TUYA_CLOUD_ACCESS_ID = new_id
    TUYA_CLOUD_ACCESS_SECRET = new_secret
    if changed:
        with TUYA_CLOUD_LOCK:
            TUYA_CLOUD_TOKEN_CACHE["token"] = None
            TUYA_CLOUD_TOKEN_CACHE["expire_at"] = 0.0
        _reset_tuya_http_session()


def get_tuya_cloud_settings():
    _refresh_tuya_cloud_settings()
    return {
        "base_url": TUYA_CLOUD_BASE_URL,
        "access_id": TUYA_CLOUD_ACCESS_ID,
        "access_secret": TUYA_CLOUD_ACCESS_SECRET,
    }


def _device_matches_pc_candidate(dev, candidate_names):
    if not isinstance(dev, dict):
        return False
    values = []
    for field in ("key", "name", "device_id", "id", "devId", "gwId"):
        raw = dev.get(field)
        if raw not in (None, ""):
            values.append(str(raw).strip().lower())
    return any(v in candidate_names for v in values if v)


def _tuya_cloud_enabled():
    _refresh_tuya_cloud_settings()
    return bool(TUYA_CLOUD_BASE_URL and TUYA_CLOUD_ACCESS_ID and TUYA_CLOUD_ACCESS_SECRET)


def _tuya_http_json(method: str, url: str, headers=None, body=None, timeout: float = 8.0):
    headers = dict(headers or {})
    if requests is not None:
        headers.setdefault("Connection", "keep-alive")
        session = _get_tuya_http_session()
        with TUYA_HTTP_SESSION_LOCK:
            resp = session.request(method.upper(), url, headers=headers, data=body, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    req = urllib_request.Request(url, data=body, headers=headers, method=method.upper())
    with urllib_request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", errors="replace"))


def _tuya_cloud_sign(message: str) -> str:
    return hmac.new(TUYA_CLOUD_ACCESS_SECRET.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest().upper()


def _tuya_cloud_request(method: str, path: str, body_obj=None, access_token: str | None = None, timeout: float = 8.0):
    _refresh_tuya_cloud_settings()
    body = b""
    if body_obj is not None:
        body = json.dumps(body_obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    body_hash = hashlib.sha256(body).hexdigest()
    t_ms = str(int(time.time() * 1000))
    token_part = access_token or ""
    string_to_sign = f"{TUYA_CLOUD_ACCESS_ID}{token_part}{t_ms}{method.upper()}\n{body_hash}\n\n{path}"
    headers = {
        "client_id": TUYA_CLOUD_ACCESS_ID,
        "t": t_ms,
        "sign_method": "HMAC-SHA256",
        "sign": _tuya_cloud_sign(string_to_sign),
    }
    if access_token:
        headers["access_token"] = access_token
    if body:
        headers["Content-Type"] = "application/json"
    return _tuya_http_json(method, TUYA_CLOUD_BASE_URL.rstrip("/") + path, headers=headers, body=body, timeout=timeout)


def _tuya_cloud_get_token(force_refresh: bool = False):
    now = time.time()
    with TUYA_CLOUD_LOCK:
        token = TUYA_CLOUD_TOKEN_CACHE.get("token")
        expire_at = float(TUYA_CLOUD_TOKEN_CACHE.get("expire_at") or 0.0)
        if (not force_refresh) and token and now < (expire_at - 60.0):
            return token
    data = _tuya_cloud_request("GET", "/v1.0/token?grant_type=1")
    if not data.get("success"):
        raise RuntimeError(f"cloud token could not be fetched: {json.dumps(data, ensure_ascii=False)}")
    result = data.get("result") or {}
    token = result.get("access_token")
    expire = float(result.get("expire_time") or 3600)
    with TUYA_CLOUD_LOCK:
        TUYA_CLOUD_TOKEN_CACHE["token"] = token
        TUYA_CLOUD_TOKEN_CACHE["expire_at"] = now + expire
    return token


def _tuya_cloud_api(method: str, path: str, body_obj=None, timeout: float = 8.0):
    token = _tuya_cloud_get_token()
    data = _tuya_cloud_request(method, path, body_obj=body_obj, access_token=token, timeout=timeout)
    if not data.get("success") and str(data.get("code")) in ("1010", "1011", "1012", "1106"):
        token = _tuya_cloud_get_token(force_refresh=True)
        data = _tuya_cloud_request(method, path, body_obj=body_obj, access_token=token, timeout=timeout)
    return data


def _tuya_cloud_status_list(device_id: str):
    data = _tuya_cloud_api("GET", f"/v1.0/iot-03/devices/{device_id}/status", timeout=_get_tuya_cloud_timeout_seconds(6000))
    if not data.get("success"):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    result = data.get("result") or []
    return result if isinstance(result, list) else []


def _tuya_cloud_value(status_list, *codes):
    wanted = {str(x).strip().lower() for x in codes if str(x).strip()}
    for item in (status_list or []):
        if isinstance(item, dict) and str(item.get("code") or "").strip().lower() in wanted:
            return item.get("value")
    return None


def _tuya_scale_power_w(raw_val, mapping=None):
    try:
        if raw_val is None or raw_val == "":
            return None
        val = float(raw_val)
    except Exception:
        return None

    scale = None
    if isinstance(mapping, dict):
        try:
            scale = int((((mapping.get("19") or {}).get("values") or {}).get("scale")))
        except Exception:
            scale = None

    if scale is None:
        scale = 1 if abs(val) >= 100 else 0

    return round(val / (10 ** max(scale, 0)), 1)


def _tuya_cloud_build_payload(cfg: dict, status_list):
    dev_type = str(cfg.get("type") or "").strip().lower()
    is_on = _tuya_cloud_value(status_list, "switch_led", "switch_1", "switch")
    bright = _tuya_cloud_value(status_list, "bright_value_v2", "brightness", "bright_value")
    power_w = _tuya_scale_power_w(_tuya_cloud_value(status_list, "cur_power", "power", "power_w", "19"))
    brightness_percent = None
    try:
        if bright is not None:
            val = int(bright)
            brightness_percent = max(1, min(100, int(round(((val - 10) / 990.0) * 100.0)))) if val > 255 else max(1, min(100, int(round((val / 255.0) * 100.0))))
    except Exception:
        brightness_percent = None
    return {
        "key": cfg.get("key"),
        "name": cfg.get("name"),
        "ip": cfg.get("ip"),
        "online": True,
        "is_on": bool(is_on) if isinstance(is_on, bool) else None,
        "brightness_percent": brightness_percent if dev_type in ("light", "bulb") else 100,
        "power_w": power_w,
        "type": dev_type or None,
        "status": status_list,
        "raw_status": status_list,
        "mapping": None,
        "source": "cloud",
    }


def _tuya_cloud_device_id_from_cfg(cfg: dict) -> str:
    if not isinstance(cfg, dict):
        return ""
    return str(cfg.get("device_id") or cfg.get("id") or cfg.get("uuid") or "").strip()


def _normalize_tuya_read_mode(value, default="local") -> str:
    text = str(value or "").strip().lower()
    if text in {"cloud", "tuya_cloud"}:
        return "cloud"
    if text in {"local", "lan", "tuya_local"}:
        return "local"
    return "cloud" if str(default or "").strip().lower() == "cloud" else "local"


def get_tuya_read_mode() -> str:
    configured = _settings_get("tuya.read_mode", None)
    if configured not in (None, ""):
        return _normalize_tuya_read_mode(configured, "local")
    return "local"


def _tuya_mode_for_device(device_key: str) -> str:
    return get_tuya_read_mode()


def _tuya_cloud_allowed_for_device(device_key: str) -> bool:
    if _tuya_mode_for_device(device_key) != "cloud":
        return False
    if not _tuya_cloud_enabled():
        return False
    cfg = get_tuya_devices_config().get(device_key) or {}
    return bool(_tuya_cloud_device_id_from_cfg(cfg))


def _tuya_cloud_unavailable_payload(device_key: str, message: str = ""):
    cfg = get_tuya_devices_config().get(device_key) or {}
    if not message:
        if not _tuya_cloud_enabled():
            message = "Tuya Cloud settings are incomplete"
        elif not _tuya_cloud_device_id_from_cfg(cfg):
            message = "cloud device_id is missing"
        else:
            message = "Tuya Cloud is unavailable"
    return {
        "key": device_key,
        "name": cfg.get("name", device_key),
        "ip": cfg.get("ip"),
        "type": str(cfg.get("type") or "").strip().lower() or None,
        "online": False,
        "is_on": None,
        "source": "cloud",
        "error": str(message),
        "raw": {"Error": str(message)},
    }


def _tuya_cloud_status_payload(device_key: str):
    cfg = get_tuya_devices_config().get(device_key)
    if not isinstance(cfg, dict):
        raise KeyError(f"device not found: {device_key}")
    device_id = _tuya_cloud_device_id_from_cfg(cfg)
    if not device_id:
        raise RuntimeError("cloud device_id is missing")
    return _tuya_cloud_build_payload(cfg, _tuya_cloud_status_list(device_id))


def _tuya_cloud_set_power(device_key: str, is_on: bool):
    cfg = get_tuya_devices_config().get(device_key)
    if not isinstance(cfg, dict):
        raise KeyError(f"device not found: {device_key}")
    device_id = _tuya_cloud_device_id_from_cfg(cfg)
    if not device_id:
        raise RuntimeError("cloud device_id yok")
    dev_type = str(cfg.get("type") or "").strip().lower()
    code = str(cfg.get("cloud_power_code") or ("switch_led" if dev_type in ("light", "bulb") else "switch_1")).strip()
    data = _tuya_cloud_api("POST", f"/v1.0/iot-03/devices/{device_id}/commands", body_obj={"commands": [{"code": code, "value": bool(is_on)}]}, timeout=_get_tuya_cloud_timeout_seconds(8000))
    if not data.get("success"):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    time.sleep(0.35)
    return _tuya_cloud_build_payload(cfg, _tuya_cloud_status_list(device_id))


def _tuya_cloud_set_brightness(device_key: str, brightness_percent: int):
    cfg = get_tuya_devices_config().get(device_key)
    if not isinstance(cfg, dict):
        raise KeyError(f"device not found: {device_key}")
    device_id = _tuya_cloud_device_id_from_cfg(cfg)
    if not device_id:
        raise RuntimeError("cloud device_id yok")
    brightness_percent = max(1, min(100, int(brightness_percent)))
    raw_value = max(10, min(1000, int(round(10 + (brightness_percent / 100.0) * 990.0))))
    power_code = str(cfg.get("cloud_power_code") or "switch_led").strip() or "switch_led"
    bright_code = str(cfg.get("cloud_brightness_code") or "bright_value_v2").strip() or "bright_value_v2"
    data = _tuya_cloud_api("POST", f"/v1.0/iot-03/devices/{device_id}/commands", body_obj={"commands": [{"code": power_code, "value": True}, {"code": bright_code, "value": raw_value}]}, timeout=_get_tuya_cloud_timeout_seconds(8000))
    if not data.get("success"):
        raise RuntimeError(json.dumps(data, ensure_ascii=False))
    time.sleep(0.35)
    return _tuya_cloud_build_payload(cfg, _tuya_cloud_status_list(device_id))


def _slugify_device_key(name: str, fallback: str = "device"):
    text = str(name or fallback or "device").strip().lower()
    text = (text.replace("ç", "c").replace("ğ", "g").replace("ı", "i")
                .replace("ö", "o").replace("ş", "s").replace("ü", "u"))
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or str(fallback or "device")

def _guess_device_type(entry):
    category = str(entry.get("category") or "").strip().lower()
    mapping = entry.get("mapping") or {}
    if category == "dj" or any(str(k) in mapping for k in (20, 21, 22, "20", "21", "22")):
        return "light"
    return "switch"

def _normalize_devices_config(data):
    if isinstance(data, dict) and data:
        return data
    if not isinstance(data, list) or not data:
        raise ValueError("devices.json is empty or invalid")

    normalized = {}
    used = set()
    for index, item in enumerate(data, start=1):
        if not isinstance(item, dict):
            continue
        explicit_key = str(item.get("key") or "").strip()
        name = str(item.get("name") or item.get("device_name") or explicit_key or f"Device {index}").strip()
        key_name = _slugify_device_key(explicit_key or name, f"device_{index}")
        if key_name in used:
            suffix = 2
            while f"{key_name}_{suffix}" in used:
                suffix += 1
            key_name = f"{key_name}_{suffix}"
        used.add(key_name)

        dev_type = str(item.get("type") or _guess_device_type(item)).strip().lower() or "switch"
        cfg = {
            "key": key_name,
            "name": name or key_name,
            "device_id": str(item.get("device_id") or item.get("id") or item.get("uuid") or "").strip(),
            "id": str(item.get("id") or item.get("device_id") or item.get("uuid") or "").strip(),
            "local_key": str(item.get("local_key") or "").strip(),
            "ip": str(item.get("ip") or "").strip(),
            "version": str(item.get("version") or "3.3").strip() or "3.3",
            "type": dev_type,
            "timeout": float(item.get("timeout") or 1.1),
            "verify_delay": float(item.get("verify_delay") or TUYA_VERIFY_DELAY_SECONDS),
            "dps": int(item.get("dps") or (20 if dev_type in ("light", "bulb") else 1)),
        }
        if dev_type in ("light", "bulb"):
            cfg["brightness_dps"] = int(item.get("brightness_dps") or 22)
            cfg["brightness_scale"] = str(item.get("brightness_scale") or "1000")
        normalized[key_name] = cfg

    if not normalized:
        raise ValueError("devices.json is empty or invalid")
    return normalized

def tuya_reset_runtime(clear_logs: bool = False):
    global TUYA_DEVICES, TUYA_DEVICES_ERROR, TUYA_DEVICES_MTIME_NS
    with TUYA_DEVICES_LOCK:
        TUYA_DEVICES = None
        TUYA_DEVICES_ERROR = None
        TUYA_DEVICES_MTIME_NS = None
    with TUYA_LOCK:
        TUYA_DEVICE_POOL.clear()
    TUYA_DEVICE_NEXT_REFRESH_AT.clear()
    try:
        with TUYA_COMMAND_LOCKS_GUARD:
            TUYA_COMMAND_LOCKS.clear()
    except Exception:
        pass
    try:
        TUYA_LAST_COMMAND_AT.clear()
    except Exception:
        pass
    try:
        with TUYA_CLOUD_LOCK:
            TUYA_CLOUD_TOKEN_CACHE["token"] = None
            TUYA_CLOUD_TOKEN_CACHE["expire_at"] = 0.0
    except Exception:
        pass
    if clear_logs:
        TUYA_ACTION_LOGS.clear()


def load_tuya_devices_from_file():
    with open(TUYA_DEVICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return _normalize_devices_config(data)

def _get_tuya_devices_mtime_ns():
    try:
        stat = os.stat(TUYA_DEVICES_FILE)
        return getattr(stat, "st_mtime_ns", None) or int(stat.st_mtime * 1_000_000_000)
    except Exception:
        return None


def get_tuya_devices_config():
    global TUYA_DEVICES, TUYA_DEVICES_ERROR, TUYA_DEVICES_MTIME_NS
    with TUYA_DEVICES_LOCK:
        current_mtime_ns = _get_tuya_devices_mtime_ns()
        should_reload = TUYA_DEVICES is None or TUYA_DEVICES_MTIME_NS != current_mtime_ns
        if not should_reload:
            return TUYA_DEVICES
        try:
            TUYA_DEVICES = load_tuya_devices_from_file()
            TUYA_DEVICES_ERROR = None
            TUYA_DEVICES_MTIME_NS = current_mtime_ns
            with TUYA_LOCK:
                TUYA_DEVICE_POOL.clear()
                TUYA_DEVICE_STATUS_LOCKS.clear()
            TUYA_DEVICE_NEXT_REFRESH_AT.clear()
        except Exception as e:
            TUYA_DEVICES = {}
            TUYA_DEVICES_ERROR = str(e)
            TUYA_DEVICES_MTIME_NS = current_mtime_ns
            with TUYA_LOCK:
                TUYA_DEVICE_POOL.clear()
                TUYA_DEVICE_STATUS_LOCKS.clear()
            TUYA_DEVICE_NEXT_REFRESH_AT.clear()
        return TUYA_DEVICES

TUYA_LOCK = threading.Lock()
TUYA_DEVICE_POOL = {}
TUYA_DEVICE_STATUS_LOCKS = {}
TUYA_REFRESH_INTERVAL_SECONDS = 3.0
OFFLINE_TUYA_REFRESH_INTERVAL_SECONDS = 15.0
TUYA_ACTION_LOGS = deque(maxlen=120)
TUYA_VERIFY_DELAY_SECONDS = 0.35
TUYA_SLOW_VERIFY_THRESHOLD_MS = 1500.0
TUYA_PUBLIC_DEVICE_FIELDS = (
    "key",
    "name",
    "online",
    "is_on",
    "brightness_percent",
    "power_w",
    "power_state",
    "details",
    "ip",
    "type",
    "source",
    "error",
)

def _safe_jsonable(value, depth=0):
    if depth >= 3:
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        out = {}
        for k, v in list(value.items())[:20]:
            out[str(k)] = _safe_jsonable(v, depth + 1)
        return out
    if isinstance(value, (list, tuple, set)):
        return [_safe_jsonable(v, depth + 1) for v in list(value)[:20]]
    return str(value)

def log_tuya_event(level: str, message: str, device_key: str = '', **extra):
    level_upper = str(level or 'info').upper()
    if level_upper == 'ERROR' and not _settings_get_bool("logging.tuya_error_logging_enabled", True):
        return

    entry = {
        'ts': time.time(),
        'time': time.strftime('%H:%M:%S'),
        'level': level_upper,
        'device_key': str(device_key or ''),
        'message': str(message or ''),
        'extra': _safe_jsonable(extra),
    }
    TUYA_ACTION_LOGS.appendleft(entry)
    extra_text = ''
    if extra:
        try:
            extra_text = ' | ' + pformat(entry['extra'], compact=True, width=140)
        except Exception:
            extra_text = f" | {entry['extra']}"
    line = f"TUYA {entry['level']}"
    if entry['device_key']:
        line += f" [{entry['device_key']}]"
    line += f" {entry['message']}{extra_text}"
    if entry['level'] == 'ERROR':
        log_error(line)
    else:
        log(line)

def get_recent_tuya_logs(limit: int = 12):
    limit = max(1, min(50, int(limit)))
    return [dict(item) for item in list(TUYA_ACTION_LOGS)[:limit]]


def tuya_public_device_payload(device_payload):
    if not isinstance(device_payload, dict):
        return {}
    public_payload = {}
    for key in TUYA_PUBLIC_DEVICE_FIELDS:
        if key in device_payload:
            public_payload[key] = device_payload.get(key)
    public_payload["key"] = str(public_payload.get("key") or device_payload.get("key") or "")
    public_payload["name"] = str(public_payload.get("name") or device_payload.get("name") or public_payload["key"])
    if "online" not in public_payload:
        public_payload["online"] = device_payload.get("online", False)
    if "is_on" not in public_payload:
        public_payload["is_on"] = device_payload.get("is_on")
    if "brightness_percent" in public_payload and public_payload["brightness_percent"] is None:
        public_payload.pop("brightness_percent", None)
    if "error" in public_payload and not public_payload["error"]:
        public_payload.pop("error", None)
    return public_payload


def tuya_public_devices_payload(devices):
    return [tuya_public_device_payload(device) for device in list(devices or [])]


def _resolve_device_key(device_key: str):
    requested = str(device_key or '').strip()
    devices_cfg = get_tuya_devices_config()
    if requested in devices_cfg:
        return requested

    requested_slug = _slugify_device_key(requested, requested)
    for real_key, cfg in devices_cfg.items():
        if str(real_key).strip() == requested:
            return real_key
        if _slugify_device_key(real_key, real_key) == requested_slug:
            return real_key
        name = str((cfg or {}).get('name') or '').strip()
        if name and (_slugify_device_key(name, name) == requested_slug or name == requested):
            return real_key
        for alt in (cfg or {}).get('aliases') or []:
            alt_s = str(alt).strip()
            if alt_s == requested or _slugify_device_key(alt_s, alt_s) == requested_slug:
                return real_key
        for ident in ('id', 'device_id', 'uuid'):
            val = str((cfg or {}).get(ident) or '').strip()
            if val and val == requested:
                return real_key
    raise KeyError(f"device not found: {requested}")

def tuya_device_exists(device_key: str):
    return _resolve_device_key(device_key)

def tuya_make_device(cfg):
    if not TINYTUYA_AVAILABLE:
        raise RuntimeError("tinytuya module is not installed")

    dev_type = str(cfg.get("type", "switch")).lower()
    if dev_type in ("light", "bulb"):
        dev = tinytuya.BulbDevice(cfg["device_id"], cfg["ip"], cfg["local_key"])
    elif dev_type in ("switch", "plug", "outlet"):
        dev = tinytuya.OutletDevice(cfg["device_id"], cfg["ip"], cfg["local_key"])
    else:
        dev = tinytuya.Device(cfg["device_id"], cfg["ip"], cfg["local_key"])

    dev.set_version(float(cfg.get("version", 3.3)))
    dev.set_socketTimeout(_get_tuya_local_timeout_seconds(2500))
    return dev

def tuya_get_or_create_device(device_key: str):
    tuya_device_exists(device_key)
    with TUYA_LOCK:
        dev = TUYA_DEVICE_POOL.get(device_key)
        if dev is not None:
            return dev
        devices_cfg = get_tuya_devices_config()
        dev = tuya_make_device(devices_cfg[device_key])
        TUYA_DEVICE_POOL[device_key] = dev
        return dev

def _get_tuya_device_status_lock(device_key: str):
    key = str(device_key or "")
    with TUYA_LOCK:
        lock = TUYA_DEVICE_STATUS_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            TUYA_DEVICE_STATUS_LOCKS[key] = lock
        return lock

def tuya_forget_device(device_key: str):
    with TUYA_LOCK:
        return TUYA_DEVICE_POOL.pop(device_key, None)

def _coerce_tuya_power_value(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        s = value.strip().lower()
        if s in ("true", "on", "1"):
            return True
        if s in ("false", "off", "0"):
            return False
    return None


def tuya_extract_power_state(status, dps_key=1):
    if not isinstance(status, dict):
        return None
    dps = status.get("dps")
    if not isinstance(dps, dict):
        return None

    preferred_keys = [dps_key, str(dps_key)]
    for key in preferred_keys:
        if key in dps:
            parsed = _coerce_tuya_power_value(dps[key])
            if parsed is not None:
                return parsed

    for value in dps.values():
        parsed = _coerce_tuya_power_value(value)
        if parsed is not None:
            return parsed
    return None

def tuya_extract_brightness_percent(status, cfg):
    if not isinstance(status, dict):
        return None
    dps = status.get("dps")
    if not isinstance(dps, dict):
        return None

    keys = []
    preferred = cfg.get("brightness_dps")
    if preferred is not None:
        keys.extend([preferred, str(preferred)])
    keys.extend([22, "22", 3, "3"])

    raw = None
    for key in keys:
        if key in dps and isinstance(dps[key], (int, float)):
            raw = float(dps[key])
            break

    if raw is None:
        return None

    scale = str(cfg.get("brightness_scale", "1000")).strip().lower()
    if scale == "255":
        percent = round((raw / 255.0) * 100.0)
    elif scale == "100":
        percent = round(raw)
    else:
        if raw <= 10:
            percent = 1
        else:
            percent = round(((raw - 10.0) / 990.0) * 100.0)

    return max(1, min(100, int(percent)))


def tuya_extract_power_w(status):
    if not isinstance(status, dict):
        return None

    mapping = status.get("mapping") if isinstance(status.get("mapping"), dict) else None

    for key in ("power_w", "watt", "watts", "meter_power_w"):
        try:
            if status.get(key) is not None and status.get(key) != "":
                return round(float(status.get(key)), 1)
        except Exception:
            pass

    for key in ("cur_power", "power"):
        power_w = _tuya_scale_power_w(status.get(key), mapping=mapping)
        if power_w is not None:
            return power_w

    for container_key in ("dps", "raw_dps", "status", "raw_status"):
        container = status.get(container_key)
        if isinstance(container, dict):
            raw_val = container.get("cur_power", container.get("19"))
            power_w = _tuya_scale_power_w(raw_val, mapping=mapping)
            if power_w is not None:
                return power_w

            nested_dps = container.get("dps")
            if isinstance(nested_dps, dict):
                raw_val = nested_dps.get("cur_power", nested_dps.get("19"))
                power_w = _tuya_scale_power_w(raw_val, mapping=mapping)
                if power_w is not None:
                    return power_w

        elif isinstance(container, list):
            for item in container:
                if not isinstance(item, dict):
                    continue
                code = str(item.get("code") or "").strip().lower()
                if code in ("cur_power", "power", "power_w", "19"):
                    power_w = _tuya_scale_power_w(item.get("value"), mapping=mapping)
                    if power_w is not None:
                        return power_w

    return None


def tuya_normalize_status(device_key: str, status):
    cfg = get_tuya_devices_config()[device_key]
    dev_type = str(cfg.get("type") or "").strip().lower()
    online = not (isinstance(status, dict) and status.get("Error"))
    is_on = tuya_extract_power_state(status, int(cfg.get("dps", 1))) if isinstance(status, dict) else None
    payload = {
        "key": device_key,
        "name": cfg.get("name", device_key),
        "ip": cfg.get("ip"),
        "type": dev_type or None,
        "online": online,
        "is_on": is_on,
        "brightness_percent": tuya_extract_brightness_percent(status, cfg) if isinstance(status, dict) else None,
        "power_w": tuya_extract_power_w(status) if isinstance(status, dict) else None,
        "source": "local",
        "raw": status,
    }
    if not online and isinstance(status, dict) and status.get("Error"):
        payload["error"] = str(status.get("Error"))
    return payload


def _is_transient_tuya_error(error_text):
    text = str(error_text or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in (
        "unable to connect",
        "unexpected payload",
        "timed out",
        "timeout",
        "connection",
        "network error",
    ))

def tuya_get_device_status(device_key: str):
    tuya_device_exists(device_key)
    cfg = get_tuya_devices_config()[device_key]
    mode = _tuya_mode_for_device(device_key)
    if mode == "cloud":
        if not _tuya_cloud_allowed_for_device(device_key):
            payload = _tuya_cloud_unavailable_payload(device_key)
            log_tuya_event("error", "Cloud status read skipped; cloud mode is selected but unavailable", device_key, error=payload.get("error"))
            return payload
        try:
            cloud_payload = _tuya_cloud_status_payload(device_key)
            return cloud_payload
        except Exception as cloud_exc:
            log_tuya_event("error", "Cloud status read failed", device_key, ip=cfg.get("ip"), error=str(cloud_exc))
            return _tuya_cloud_unavailable_payload(device_key, str(cloud_exc))
    last_error = None
    last_normalized = None
    for attempt in range(2):
        try:
            with _get_tuya_device_status_lock(device_key):
                if attempt > 0:
                    TUYA_DEVICE_POOL.pop(device_key, None)
                dev = tuya_get_or_create_device(device_key)
                status = dev.status()
            normalized = tuya_normalize_status(device_key, status)
            if normalized.get("online"):
                normalized["source"] = "local"
                return normalized

            last_normalized = normalized
            last_error = normalized.get("error") or "offline"
            with TUYA_LOCK:
                TUYA_DEVICE_POOL.pop(device_key, None)
            if attempt == 0 and _is_transient_tuya_error(last_error):
                time.sleep(0.15)
                continue
            log_tuya_event("error", "Local status read returned offline", device_key, ip=normalized.get("ip"), raw=normalized.get("raw"), error=normalized.get("error"))
            return normalized
        except Exception as exc:
            last_error = str(exc)
            with TUYA_LOCK:
                TUYA_DEVICE_POOL.pop(device_key, None)
            if attempt == 0 and _is_transient_tuya_error(last_error):
                time.sleep(0.15)
                continue
            log_tuya_event("error", "Local status read exception", device_key, ip=cfg.get("ip"), error=str(exc))
            return {
                "key": device_key,
                "name": cfg.get("name", device_key),
                "ip": cfg.get("ip"),
                "online": False,
                "is_on": None,
                "source": "local",
                "error": str(exc),
                "raw": {"Error": str(exc)},
            }

    if isinstance(last_normalized, dict):
        log_tuya_event("error", "Local status read returned offline", device_key, ip=last_normalized.get("ip"), raw=last_normalized.get("raw"), error=last_normalized.get("error"))
        return last_normalized
    log_tuya_event("error", "Local status read exception", device_key, ip=cfg.get("ip"), error=str(last_error or "unknown"))
    return {
        "key": device_key,
        "name": cfg.get("name", device_key),
        "ip": cfg.get("ip"),
        "online": False,
        "is_on": None,
        "source": "local",
        "error": str(last_error or "unknown"),
        "raw": {"Error": str(last_error or "unknown")},
    }

def _tuya_status_error_payload(device_key: str, exc):
    cfg = get_tuya_devices_config().get(device_key) or {}
    source = _tuya_mode_for_device(device_key)
    return {
        "key": device_key,
        "name": cfg.get("name", device_key),
        "ip": cfg.get("ip"),
        "type": str(cfg.get("type") or "").strip().lower() or None,
        "online": False,
        "is_on": None,
        "source": source,
        "error": str(exc),
        "raw": {"Error": str(exc)},
    }


def _get_tuya_status_worker_count(worker_hint=None):
    try:
        max_workers = int(worker_hint or len(get_tuya_devices_config()) or 1)
    except Exception:
        max_workers = 1
    configured_limit = max(1, _settings_int("tuya.max_parallel_status_workers", 4))
    return max(1, min(configured_limit, 8, max_workers))


def _get_tuya_status_batch_timeout_seconds(key_count=1):
    configured_ms = _settings_int("tuya.status_batch_timeout_ms", 0)
    if configured_ms > 0:
        return max(1.0, min(30.0, float(configured_ms) / 1000.0))
    local_timeout = _get_tuya_local_timeout_seconds(2500)
    # Keep one unresponsive LAN device from blocking the whole Tuya status pass.
    # Slow/offline devices are retried by the updater on the offline interval.
    return max(2.5, min(8.0, local_timeout + 1.5))


def _get_tuya_status_map_parallel(device_keys):
    keys = [str(k) for k in device_keys]
    if not keys:
        return {}
    if len(keys) == 1:
        key = keys[0]
        try:
            return {key: tuya_get_device_status(key)}
        except Exception as exc:
            return {key: _tuya_status_error_payload(key, exc)}

    max_workers = _get_tuya_status_worker_count(len(keys))
    executor = concurrent.futures.ThreadPoolExecutor(
        max_workers=max_workers,
        thread_name_prefix="tuya-status-once",
    )
    futures = {executor.submit(tuya_get_device_status, key): key for key in keys}
    results = {}
    timeout_seconds = _get_tuya_status_batch_timeout_seconds(len(keys))
    done, pending = concurrent.futures.wait(
        futures.keys(),
        timeout=timeout_seconds,
        return_when=concurrent.futures.ALL_COMPLETED,
    )
    for future in done:
        key = futures[future]
        try:
            results[key] = future.result()
        except Exception as exc:
            results[key] = _tuya_status_error_payload(key, exc)
    for future in pending:
        key = futures[future]
        future.cancel()
        with TUYA_LOCK:
            TUYA_DEVICE_POOL.pop(key, None)
        results[key] = _tuya_status_error_payload(key, f"Tuya status read timed out after {timeout_seconds:.1f}s")
    try:
        executor.shutdown(wait=False, cancel_futures=True)
    except TypeError:
        executor.shutdown(wait=False)
    except Exception:
        pass
    return results

def tuya_list_devices_with_status(device_keys=None):
    keys = list(device_keys or get_tuya_devices_config().keys())
    results = _get_tuya_status_map_parallel(keys)
    return [results[key] if key in results else _tuya_status_error_payload(key, "Tuya status was not read") for key in keys]


def _settings_list(path):
    value = _settings_get(path, [])
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item or "").strip()]
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    return []


def _get_tuya_status_poll_keys():
    devices = get_tuya_devices_config()
    keys = list(devices.keys())
    visible_keys = [key for key in _settings_list("tuya.visible_device_keys") if key in devices]
    if visible_keys:
        keys = visible_keys

    pc_key = str(_settings_get("tuya.pc_plug_key", "") or "").strip().lower()
    if pc_key:
        keys = [key for key in keys if str(key).strip().lower() != pc_key]
    return keys

def refresh_tuya_cache_once():
    devices = tuya_list_devices_with_status()
    with SENSOR_CACHE_LOCK:
        SYSTEM_CACHE["tuya_devices"] = tuya_public_devices_payload(devices)
    return devices

def tuya_updater_loop():
    backoff_seconds = 1.0

    try:
        time.sleep(2.0)
    except Exception:
        pass

    while True:
        sleep_seconds = backoff_seconds
        try:
            now = time.time()
            cached_map = {}
            due_keys = []

            poll_keys = _get_tuya_status_poll_keys()
            for key in poll_keys:
                next_at = TUYA_DEVICE_NEXT_REFRESH_AT.get(key, 0.0)
                cached = tuya_get_cached_device(key)
                if cached and now < next_at:
                    cached_map[key] = cached
                else:
                    if cached:
                        cached_map[key] = cached
                    due_keys.append(key)

            batch_size = max(1, _settings_int("tuya.status_batch_size", 8))
            batch_keys = due_keys[:batch_size]
            due_results = _get_tuya_status_map_parallel(batch_keys)
            devices = []

            for key in poll_keys:
                if key in due_results:
                    status = due_results[key]
                    cached = cached_map.get(key)
                    transient_status_error = _is_transient_tuya_error(status.get("error"))
                    if (
                        isinstance(cached, dict)
                        and cached.get("online") is True
                        and not status.get("online")
                        and transient_status_error
                        and _tuya_mode_for_device(key) == "local"
                    ):
                        status = dict(cached)
                        status["source"] = "local-stale"
                        status.pop("error", None)
                    devices.append(status)
                    online_interval_sec = max(0.5, _settings_int("performance.tuya_refresh_interval_ms", 2000) / 1000.0)
                    offline_interval_sec = max(2.0, online_interval_sec * 4.0)
                    if transient_status_error:
                        offline_interval_sec = max(60.0, offline_interval_sec)
                    interval = offline_interval_sec if transient_status_error else (online_interval_sec if status.get("online") else offline_interval_sec)
                    TUYA_DEVICE_NEXT_REFRESH_AT[key] = now + interval
                else:
                    cached = cached_map.get(key)
                    if cached:
                        devices.append(cached)
                    else:
                        devices.append({
                            "key": key,
                            "name": (get_tuya_devices_config().get(key) or {}).get("name", key),
                            "ip": (get_tuya_devices_config().get(key) or {}).get("ip"),
                            "online": False,
                            "is_on": None,
                            "error": "Waiting for refresh",
                        })
                        TUYA_DEVICE_NEXT_REFRESH_AT[key] = now + 1.0

            public_devices = tuya_public_devices_payload(devices)
            with SENSOR_CACHE_LOCK:
                if SYSTEM_CACHE.get("tuya_devices") != public_devices:
                    SYSTEM_CACHE["tuya_devices"] = public_devices

            if len(due_keys) > len(batch_keys):
                sleep_seconds = 0.35
            elif poll_keys:
                next_due_at = min(float(TUYA_DEVICE_NEXT_REFRESH_AT.get(key, now + 5.0) or now + 5.0) for key in poll_keys)
                sleep_seconds = max(0.5, min(5.0, next_due_at - time.time()))
            else:
                sleep_seconds = 5.0
            backoff_seconds = 1.0
        except Exception as e:
            if _settings_get_bool("logging.tuya_error_logging_enabled", True):
                log_error(f"Tuya cache update error: {e}")
            backoff_seconds = min(backoff_seconds * 2.0, 12.0)
            sleep_seconds = backoff_seconds

        time.sleep(sleep_seconds)

def tuya_get_cached_devices():
    with SENSOR_CACHE_LOCK:
        devices = SYSTEM_CACHE.get("tuya_devices") or []
        if devices:
            return [dict(x) for x in devices]
    return refresh_tuya_cache_once()

def tuya_get_cached_device(device_key: str):
    with SENSOR_CACHE_LOCK:
        devices = SYSTEM_CACHE.get("tuya_devices") or []
        for device in devices:
            if device.get("key") == device_key:
                return dict(device)
    return None

def tuya_update_cached_device(device_payload: dict):
    with SENSOR_CACHE_LOCK:
        devices = list(SYSTEM_CACHE.get("tuya_devices") or [])
        replaced = False
        for idx, item in enumerate(devices):
            if item.get("key") == device_payload.get("key"):
                merged = dict(item)
                merged.update(device_payload)
                devices[idx] = merged
                replaced = True
                break
        if not replaced:
            devices.append(device_payload)
        SYSTEM_CACHE["tuya_devices"] = tuya_public_devices_payload(devices)


def _tuya_verify_state_classification(device_payload, target_state: bool):
    if not isinstance(device_payload, dict):
        return "VERIFY_INVALID_PAYLOAD"
    if device_payload.get("online") is False:
        return "VERIFY_OFFLINE"
    live_state = device_payload.get("is_on")
    if live_state is None:
        return "VERIFY_STATE_UNKNOWN"
    if bool(live_state) != bool(target_state):
        return "VERIFY_STATE_MISMATCH"
    return "OK"


def _tuya_verify_power_state(device_key: str, target_state: bool, wait_seconds: float | None = None):
    if wait_seconds is None:
        wait_seconds = TUYA_VERIFY_DELAY_SECONDS
    wait_seconds = max(0.0, float(wait_seconds))
    if wait_seconds > 0:
        time.sleep(wait_seconds)
    live = tuya_get_device_status(device_key)
    classification = _tuya_verify_state_classification(live, target_state)
    return {
        "classification": classification,
        "device": live,
        "is_match": classification == "OK",
    }

def _tuya_set_device_power_fast_inner(device_key: str, is_on: bool):
    device_key = tuya_device_exists(device_key)
    cfg = get_tuya_devices_config()[device_key]
    target_state = bool(is_on)

    if _tuya_mode_for_device(device_key) == "cloud":
        if not _tuya_cloud_allowed_for_device(device_key):
            payload = _tuya_cloud_unavailable_payload(device_key)
            error_text = payload.get("error") or "Tuya Cloud is unavailable"
            log_tuya_event("error", "Cloud toggle skipped; cloud mode is selected but unavailable", device_key, error=error_text, target_state=target_state)
            return {
                "ok": False,
                "error": error_text,
                "device_key": device_key,
                "device": tuya_public_device_payload(payload),
                "diag": {"path": "cloud", "classification": "CLOUD_UNAVAILABLE"},
            }
        try:
            updated = _tuya_cloud_set_power(device_key, target_state)
            tuya_update_cached_device(updated)
            TUYA_DEVICE_NEXT_REFRESH_AT[device_key] = time.time() + 1.0
            return {
                "ok": True,
                "device_key": device_key,
                "new_state": target_state,
                "device": tuya_public_device_payload(updated),
                "diag": {"path": "cloud", "classification": "OK"},
            }
        except Exception as cloud_exc:
            log_tuya_event("error", "Cloud toggle failed", device_key, error=str(cloud_exc), target_state=target_state)
            payload = _tuya_cloud_unavailable_payload(device_key, str(cloud_exc))
            return {
                "ok": False,
                "error": str(cloud_exc),
                "device_key": device_key,
                "device": tuya_public_device_payload(payload),
                "diag": {"path": "cloud", "classification": "CLOUD_COMMAND_FAILED"},
            }

    dps = int(cfg.get("dps", 1))
    started_at = time.time()
    verify_wait = float(cfg.get("verify_delay", TUYA_VERIFY_DELAY_SECONDS))
    last_result = None
    last_device = None
    final_classification = "UNKNOWN"

    retry_count = max(1, _settings_int("performance.tuya_retry_count", 1))
    max_attempts = retry_count + 1
    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            with TUYA_LOCK:
                TUYA_DEVICE_POOL.pop(device_key, None)
                log_tuya_event("info", "Retrying after verification mismatch", device_key, target_state=target_state, dps=dps, previous_classification=final_classification)

        try:
            dev = tuya_get_or_create_device(device_key)
            last_result = dev.set_status(target_state, switch=dps)
        except Exception as exc:
            final_classification = f"SET_STATUS_EXCEPTION_ATTEMPT_{attempt}"
            elapsed_ms = round((time.time() - started_at) * 1000.0, 1)
            log_tuya_event("error", f"set_status attempt failed (attempt {attempt})", device_key, target_state=target_state, ip=cfg.get("ip"), dps=dps, error=str(exc), elapsed_ms=elapsed_ms, classification=final_classification)
            if attempt >= max_attempts:
                return {
                    "ok": False,
                    "error": str(exc),
                    "device_key": device_key,
                    "device": tuya_public_device_payload(tuya_get_cached_device(device_key)),
                    "diag": {
                        "attempt": attempt,
                        "elapsed_ms": elapsed_ms,
                        "classification": final_classification,
                    },
                }
            continue

        verify = _tuya_verify_power_state(device_key, target_state, wait_seconds=verify_wait)
        last_device = verify.get("device")
        final_classification = verify.get("classification") or "VERIFY_UNKNOWN"
        elapsed_ms = round((time.time() - started_at) * 1000.0, 1)

        if verify.get("is_match"):
            updated = dict(last_device or {})
            updated.update({
                "key": device_key,
                "name": cfg.get("name", device_key),
                "online": updated.get("online", True),
                "is_on": target_state,
            })
            tuya_update_cached_device(updated)
            TUYA_DEVICE_NEXT_REFRESH_AT[device_key] = time.time() + 1.5

            log_payload = {
                "target_state": target_state,
                "ip": cfg.get("ip"),
                "dps": dps,
                "attempt": attempt,
                "elapsed_ms": elapsed_ms,
                "result": last_result,
                "verify_state": (last_device or {}).get("is_on"),
                "classification": "OK",
            }
            if elapsed_ms >= TUYA_SLOW_VERIFY_THRESHOLD_MS:
                    log_tuya_event("error", "Toggle succeeded but verification was slow", device_key, **log_payload)
            else:
                    log_tuya_event("info", "Toggle succeeded", device_key, **log_payload)

            return {
                "ok": True,
                "device_key": device_key,
                "new_state": target_state,
                "device": tuya_public_device_payload(updated),
                "diag": {
                    "attempt": attempt,
                    "elapsed_ms": elapsed_ms,
                    "classification": "OK",
                    "verify_state": (last_device or {}).get("is_on"),
                },
            }

        log_tuya_event(
            "error",
                f"Verification failed (attempt {attempt})",
            device_key,
            target_state=target_state,
            ip=cfg.get("ip"),
            dps=dps,
            elapsed_ms=elapsed_ms,
            classification=final_classification,
            verify_state=(last_device or {}).get("is_on"),
            verify_error=(last_device or {}).get("error"),
            result=last_result,
            verify_raw=(last_device or {}).get("raw"),
        )

    failure_device = dict(last_device or tuya_get_cached_device(device_key) or {})
    if failure_device:
        failure_device.update({
            "key": device_key,
            "name": cfg.get("name", device_key),
        })
        tuya_update_cached_device(failure_device)

    elapsed_ms = round((time.time() - started_at) * 1000.0, 1)
    final_error_map = {
        "VERIFY_OFFLINE": "The device appears offline after the toggle.",
        "VERIFY_STATE_UNKNOWN": "The device state could not be read after the toggle.",
        "VERIFY_STATE_MISMATCH": "The command was sent, but the device did not reach the target state.",
        "VERIFY_INVALID_PAYLOAD": "Verification returned an invalid payload.",
    }
    final_error = final_error_map.get(final_classification, "Tuya toggle could not be verified.")
    log_tuya_event("error", "Toggle could not be verified", device_key, target_state=target_state, ip=cfg.get("ip"), dps=dps, elapsed_ms=elapsed_ms, classification=final_classification, verify_state=(failure_device or {}).get("is_on"), verify_error=(failure_device or {}).get("error"), result=last_result)
    return {
        "ok": False,
        "error": final_error,
        "device_key": device_key,
        "device": tuya_public_device_payload(failure_device) if failure_device else None,
        "diag": {
            "attempt": max_attempts,
            "elapsed_ms": elapsed_ms,
            "classification": final_classification,
            "verify_state": (failure_device or {}).get("is_on"),
        },
    }

def tuya_set_device_power_fast(device_key: str, is_on: bool):
    device_key = tuya_device_exists(device_key)
    with _tuya_command_lock(device_key):
        _tuya_wait_command_spacing(device_key)
        result = _tuya_set_device_power_fast_inner(device_key, is_on)
        _tuya_mark_quick_refresh(device_key, 0.75 if result.get("ok") else 1.5)
        return result

def tuya_toggle_device_fast(device_key: str):
    mode = _tuya_mode_for_device(device_key)
    cached = tuya_get_cached_device(device_key)
    if mode == "cloud":
        cached = None
    if isinstance(cached, dict) and cached.get("online") is False:
        error_text = cached.get("error") or "device is unreachable on the local network"
        log_tuya_event("error", "Toggle skipped; device is offline in cache", device_key, error=error_text, ip=cached.get("ip"))
        return {"ok": False, "error": error_text, "device": tuya_public_device_payload(cached)}

    current_state = cached.get("is_on") if isinstance(cached, dict) else None
    if current_state is None:
        live = tuya_get_device_status(device_key)
        current_state = live.get("is_on")
        if current_state is None:
            log_tuya_event("error", "Could not read device state before toggle", device_key, error=live.get("error"), raw=live.get("raw"))
            return {"ok": False, "error": live.get("error") or "device state could not be read", "device": tuya_public_device_payload(live)}
    return tuya_set_device_power_fast(device_key, not bool(current_state))


def _tuya_set_device_brightness_fast_inner(device_key: str, brightness_percent: int):
    device_key = tuya_device_exists(device_key)
    cfg = get_tuya_devices_config()[device_key]
    if str(cfg.get("type", "")).lower() not in ("light", "bulb"):
        return {"ok": False, "error": "This device does not support brightness."}

    try:
        brightness = max(1, min(100, int(round(float(brightness_percent)))))
    except Exception:
        return {"ok": False, "error": "Invalid brightness value."}

    if _tuya_mode_for_device(device_key) == "cloud":
        if not _tuya_cloud_allowed_for_device(device_key):
            payload = _tuya_cloud_unavailable_payload(device_key)
            error_text = payload.get("error") or "Tuya Cloud is unavailable"
            log_tuya_event("error", "Cloud brightness update skipped; cloud mode is selected but unavailable", device_key, error=error_text, brightness_percent=brightness)
            return {
                "ok": False,
                "error": error_text,
                "device_key": device_key,
                "device": tuya_public_device_payload(payload),
                "diag": {"path": "cloud", "classification": "CLOUD_UNAVAILABLE"},
            }
        try:
            updated = _tuya_cloud_set_brightness(device_key, brightness)
            tuya_update_cached_device(updated)
            TUYA_DEVICE_NEXT_REFRESH_AT[device_key] = time.time() + 1.0
            return {
                "ok": True,
                "device_key": device_key,
                "brightness_percent": brightness,
                "device": tuya_public_device_payload(updated),
                "diag": {"path": "cloud", "classification": "OK"},
            }
        except Exception as cloud_exc:
            log_tuya_event("error", "Cloud brightness update failed", device_key, error=str(cloud_exc), brightness_percent=brightness)
            payload = _tuya_cloud_unavailable_payload(device_key, str(cloud_exc))
            return {
                "ok": False,
                "error": str(cloud_exc),
                "device_key": device_key,
                "device": tuya_public_device_payload(payload),
                "diag": {"path": "cloud", "classification": "CLOUD_COMMAND_FAILED"},
            }

    power_dps = int(cfg.get("dps", 20))
    brightness_dps = int(cfg.get("brightness_dps", 22))
    scale = str(cfg.get("brightness_scale", "1000")).strip().lower()

    if scale == "255":
        raw_value = max(0, min(255, int(round((brightness / 100.0) * 255.0))))
    elif scale == "100":
        raw_value = brightness
    else:
        raw_value = max(10, min(1000, int(round(10 + (brightness / 100.0) * 990.0))))

    try:
        dev = tuya_get_or_create_device(device_key)
        result = None

        if hasattr(dev, "set_multiple_values"):
            try:
                result = dev.set_multiple_values({
                    str(power_dps): True,
                    str(brightness_dps): raw_value,
                })
            except Exception:
                result = None

        if result is None:
            try:
                dev.set_status(True, switch=power_dps)
            except Exception:
                pass

            if hasattr(dev, "set_value"):
                try:
                    result = dev.set_value(brightness_dps, raw_value)
                except Exception:
                    result = None

        if result is None:
            return {"ok": False, "error": "Brightness could not be applied on the device."}

        live_after = None
        try:
            time.sleep(float(cfg.get("brightness_verify_delay", 0.20)))
            live_after = tuya_get_device_status(device_key)
        except Exception:
            live_after = None

        updated = dict(live_after or tuya_get_cached_device(device_key) or {})
        updated.update({
            "key": device_key,
            "name": cfg.get("name", device_key),
            "online": updated.get("online", True),
            "is_on": True,
            "brightness_percent": updated.get("brightness_percent") if updated.get("brightness_percent") is not None else brightness,
        })
        tuya_update_cached_device(updated)
        return {"ok": True, "device_key": device_key, "brightness_percent": updated.get("brightness_percent", brightness), "device": tuya_public_device_payload(updated)}
    except Exception as exc:
        with TUYA_LOCK:
            TUYA_DEVICE_POOL.pop(device_key, None)
        return {"ok": False, "error": str(exc)}

def tuya_set_device_brightness_fast(device_key: str, brightness_percent: int):
    device_key = tuya_device_exists(device_key)
    with _tuya_command_lock(device_key):
        _tuya_wait_command_spacing(device_key)
        result = _tuya_set_device_brightness_fast_inner(device_key, brightness_percent)
        _tuya_mark_quick_refresh(device_key, 0.75 if result.get("ok") else 1.5)
        return result



TUYA_DEVICE_NEXT_REFRESH_AT = {}
TUYA_STATUS_MAX_WORKERS = 0
TUYA_STATUS_EXECUTOR = None
TUYA_STATUS_EXECUTOR_LOCK = threading.Lock()


def _get_tuya_status_executor(worker_hint=None):
    global TUYA_STATUS_MAX_WORKERS, TUYA_STATUS_EXECUTOR
    try:
        max_workers = int(worker_hint or len(get_tuya_devices_config()) or 1)
    except Exception:
        max_workers = 1
    configured_limit = max(1, _settings_int("tuya.max_parallel_status_workers", 4))
    max_workers = max(1, min(configured_limit, 8, max_workers))
    with TUYA_STATUS_EXECUTOR_LOCK:
        if TUYA_STATUS_EXECUTOR is not None and TUYA_STATUS_MAX_WORKERS == max_workers:
            return TUYA_STATUS_EXECUTOR
        old_executor = TUYA_STATUS_EXECUTOR
        TUYA_STATUS_EXECUTOR = concurrent.futures.ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="tuya-status",
        )
        TUYA_STATUS_MAX_WORKERS = max_workers
    if old_executor is not None:
        try:
            old_executor.shutdown(wait=False, cancel_futures=True)
        except TypeError:
            old_executor.shutdown(wait=False)
        except Exception:
            pass
    return TUYA_STATUS_EXECUTOR

TUYA_COMMAND_LOCKS = {}
TUYA_COMMAND_LOCKS_GUARD = threading.Lock()
TUYA_LAST_COMMAND_AT = {}


def _tuya_command_lock(device_key: str):
    key = str(device_key or '')
    with TUYA_COMMAND_LOCKS_GUARD:
        lock = TUYA_COMMAND_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            TUYA_COMMAND_LOCKS[key] = lock
        return lock


def _tuya_command_spacing_seconds():
    return max(0.0, _settings_int_any([
        "tuya.command_spacing_ms",
        "performance.tuya_command_spacing_ms",
    ], 180) / 1000.0)


def _tuya_wait_command_spacing(device_key: str):
    spacing = _tuya_command_spacing_seconds()
    if spacing <= 0:
        return
    key = str(device_key or '')
    now = time.time()
    last_at = float(TUYA_LAST_COMMAND_AT.get(key) or 0.0)
    wait = spacing - (now - last_at)
    if wait > 0:
        time.sleep(min(wait, 1.0))
    TUYA_LAST_COMMAND_AT[key] = time.time()


def _tuya_mark_quick_refresh(device_key: str, seconds: float = 0.35):
    try:
        TUYA_DEVICE_NEXT_REFRESH_AT[str(device_key or '')] = time.time() + max(0.1, float(seconds))
    except Exception:
        pass


def tuya_reload_devices_and_pool(clear_logs: bool = False):
    tuya_reset_runtime(clear_logs=clear_logs)
    cfg = get_tuya_devices_config()
    return {
        "ok": bool(cfg),
        "device_count": len(cfg),
        "error": TUYA_DEVICES_ERROR,
        "keys": list(cfg.keys()),
    }
