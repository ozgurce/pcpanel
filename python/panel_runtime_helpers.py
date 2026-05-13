# File Version: 1.0
import os
import subprocess
import json
import time
import re
import sys
import psutil
import ctypes
from functools import wraps

from panel_globals import (
    BASE_DIR,
    LOG_FILE, ERR_FILE, TUYA_LOG_FILE,
    DNSREDIR_CMD_DEFAULT, NOLLIE_BRIGHTNESS_SCRIPT_DEFAULT,
    NOLLIE_STATE_PATH_DEFAULT, LIAN_CONTROL_SCRIPT_DEFAULT,
    LIAN_PROFILE_PATH_DEFAULT, LIAN_STATE_CACHE_PATH_DEFAULT,
    LIAN_DATA_DIR_DEFAULT, LIAN_SERVICE_URL_DEFAULT,
    SENSOR_CACHE_LOCK, FPS_IGNORE_APPS
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_int, _get_setting_float, _get_setting_bool,
    _get_window_str, _get_performance_interval_seconds, _get_window_int,
    _get_runtime_setting_cached
)
from panel_logging import log, log_error

def _startupinfo_hidden():
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0
        return si
    except Exception:
        return None

def _popen_hidden(args, cwd=None):
    kwargs = {"cwd": cwd or BASE_DIR, "shell": False}
    si = _startupinfo_hidden()
    if si is not None:
        kwargs["startupinfo"] = si
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.Popen(args, **kwargs)

def _run_hidden(args, cwd=None):
    kwargs = {"cwd": cwd or BASE_DIR, "capture_output": True, "text": True, "shell": False}
    si = _startupinfo_hidden()
    if si is not None:
        kwargs["startupinfo"] = si
    if hasattr(subprocess, "CREATE_NO_WINDOW"):
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    return subprocess.run(args, **kwargs)

def report_issue(module_name: str, message: str, is_error: bool = True):
    from panel_globals import SYSTEM_CACHE
    from panel_state import mark_system_cache_changed
    ts = time.time()
    msg_str = str(message)
    if is_error:
        log_error(f"[{module_name.upper()}] {msg_str}")
    else:
        log(f"[{module_name.upper()}] {msg_str}")
    with SENSOR_CACHE_LOCK:
        SYSTEM_CACHE["module_status"][module_name] = "error" if is_error else "online"
        issues = SYSTEM_CACHE.get("recent_issues", [])
        issues.append({"module": module_name, "msg": msg_str, "ts": ts, "type": "error" if is_error else "info"})
        SYSTEM_CACHE["recent_issues"] = issues[-5:]
        SYSTEM_CACHE["last_update"] = ts
    mark_system_cache_changed()

def safe_execute(module_name: str, fallback_value=None):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                report_issue(module_name, f"{type(e).__name__}: {e}")
                return fallback_value
        return wrapper
    return decorator

def _get_uptime_refresh_interval_seconds():
    return _get_performance_interval_seconds("uptime_refresh_interval_ms", 5000, 250)

def _get_keep_window_alive_min_interval_seconds():
    min_ms = _get_window_int("keep_window_alive_min_interval_ms", 250)
    return float(max(50, min_ms)) / 1000.0

def _normalize_fps_process_key(value):
    text = str(value or "").strip().strip('"').strip("'")
    if not text: return ""
    text = text.replace("\\", "/")
    exe_match = re.search(r"([a-z0-9 _.\-]+\.exe)\b", text, flags=re.IGNORECASE)
    if exe_match: text = exe_match.group(1)
    elif re.match(r"^[a-z]:/", text, flags=re.IGNORECASE) or text.startswith("/"):
        text = text.split("/")[-1]
    text = re.sub(r"\.exe$", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip().lower()

def _get_hwinfo_fps_ignore_apps():
    from panel_globals import FPS_IGNORE_APPS
    items = list(FPS_IGNORE_APPS)
    raw = _get_runtime_setting_cached("hwinfo.fps_ignore_apps_text", "")
    if raw:
        items.extend(re.split(r"[\r\n,;]+", str(raw)))
    return {_normalize_fps_process_key(item) for item in items if str(item).strip()} | {"", "unknown"}

def _configured_path(setting_path: str, default_path: str) -> str:
    value = _get_setting_str(setting_path, default_path).strip() or default_path
    return os.path.abspath(os.path.expandvars(value))

def _find_pythonw():
    candidates = [
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python313\pythonw.exe"),
        os.path.expandvars(r"%LocalAppData%\Programs\Python\Python312\pythonw.exe"),
        r"C:\Program Files\Python313\pythonw.exe",
        r"C:\Program Files\Python312\pythonw.exe",
    ]
    for pyw in candidates:
        if os.path.exists(pyw): return pyw
    exe = sys.executable or ""
    if exe.lower().endswith("python.exe"):
        cand = exe[:-10] + "pythonw.exe"
        if os.path.exists(cand): return cand
    return "pythonw.exe"

def _launch_nollie_brightness(action: str):
    script_path = _configured_path("commands.nollie_brightness_script", NOLLIE_BRIGHTNESS_SCRIPT_DEFAULT)
    state_path = _configured_path("commands.nollie_state_path", NOLLIE_STATE_PATH_DEFAULT)
    include_boot = _get_setting_bool("commands.nollie_include_boot_canvases", True)
    args = [_find_pythonw(), script_path, action, "--state-path", state_path]
    if not include_boot: args.append("--no-boot")
    _popen_hidden(args, cwd=os.path.dirname(script_path))
    return {"ok": True}

def _launch_lian_control(mode: str):
    script_path = _configured_path("commands.lian_control_script", LIAN_CONTROL_SCRIPT_DEFAULT)
    profile_path = _configured_path("commands.lian_profile_path", LIAN_PROFILE_PATH_DEFAULT)
    state_cache_path = _configured_path("commands.lian_state_cache_path", LIAN_STATE_CACHE_PATH_DEFAULT)
    data_dir = _configured_path("commands.lian_data_dir", LIAN_DATA_DIR_DEFAULT)
    service_url = _get_setting_str("commands.lian_service_url", LIAN_SERVICE_URL_DEFAULT)
    timeout = max(0.5, _get_setting_float("commands.lian_timeout_seconds", 2.5))
    args = [sys.executable or "python.exe", script_path, mode, "--json", "--profile", profile_path, "--state-cache", state_cache_path, "--data-dir", data_dir, "--service-url", service_url, "--timeout", str(timeout)]
    try:
        completed = _run_hidden(args, cwd=os.path.dirname(script_path))
        return {"ok": completed.returncode == 0, "data": json.loads(completed.stdout) if completed.stdout else {}}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def run_case_lights(mode: str):
    mode = str(mode or "").strip().lower()
    if mode not in {"on", "off"}: return {"ok": False}
    results = {"nollie": _launch_nollie_brightness("restore" if mode == "on" else "off"), "lian": _launch_lian_control(mode)}
    return {"ok": all(r.get("ok") for r in results.values()), **results}

def hide_current_process_windows(except_hwnd=None):
    try:
        def enum_window_proc(hwnd, lparam):
            if hwnd == except_hwnd: return True
            pid = ctypes.wintypes.DWORD(); ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)); pid = pid.value
            if pid == os.getpid():
                if ctypes.windll.user32.IsWindowVisible(hwnd):
                    ctypes.windll.user32.ShowWindow(hwnd, 0)
            return True
        enum_windows_callback = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)(enum_window_proc)
        ctypes.windll.user32.EnumWindows(enum_windows_callback, 0)
    except Exception: pass

def restore_default_process_scheduling(include_children=False):
    try:
        p = psutil.Process(os.getpid())
        if hasattr(psutil, "NORMAL_PRIORITY_CLASS"):
            p.nice(psutil.NORMAL_PRIORITY_CLASS)
        if include_children:
            for child in p.children(recursive=True):
                try:
                    if hasattr(psutil, "NORMAL_PRIORITY_CLASS"):
                        child.nice(psutil.NORMAL_PRIORITY_CLASS)
                except Exception: pass
    except Exception: pass

__all__ = [name for name in globals() if not name.startswith("__")]


