# File Version: 1.0
import sys
import os
import time
import subprocess
import psutil
import datetime
import threading
from panel_globals import (
    BASE_DIR, WORKER_STATE, HWINFO_PROCESS_NAMES, 
    HWINFO_SHARED_MEMORY_RESTART_COOLDOWN_SECONDS
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_int, _get_setting_float, _get_setting_bool
)
from panel_logging import log, log_hwinfo_error
from win_utils import shell32

def _get_hwinfo_auto_restart_enabled():
    return _get_setting_bool("hwinfo.auto_restart_enabled", True)

def _get_hwinfo_auto_restart_max_uptime_seconds():
    hours = _get_setting_float("hwinfo.auto_restart_max_uptime_hours", 11.0)
    return max(1.0, float(hours)) * 3600.0

def _get_hwinfo_wall_clock_age_seconds(processes=None, now_ts=None):
    items = processes if processes is not None else _find_hwinfo_processes()
    create_times = [float(item.get("create_time") or 0.0) for item in list(items or []) if float(item.get("create_time") or 0.0) > 0]
    if not create_times:
        return None, None
    started_at = min(create_times)
    now_value = float(now_ts if now_ts is not None else time.time())
    return max(0.0, now_value - started_at), started_at

def _format_duration_short(seconds):
    try: seconds = max(0, int(float(seconds or 0)))
    except Exception: seconds = 0
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days: return f"{days}d {hours}h {minutes}m"
    if hours: return f"{hours}h {minutes}m"
    return f"{minutes}m"

def _find_hwinfo_processes():
    processes = []
    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline", "create_time"]):
        try:
            name = str(proc.info.get("name") or "").lower()
            if name not in HWINFO_PROCESS_NAMES: continue
            exe = proc.info.get("exe") or ""
            if not exe:
                cmdline = proc.info.get("cmdline") or []
                exe = str(cmdline[0]) if cmdline else ""
            processes.append({
                "pid": proc.pid,
                "name": proc.info.get("name") or name,
                "exe": exe,
                "create_time": float(proc.info.get("create_time") or 0.0),
                "proc": proc,
            })
        except (psutil.NoSuchProcess, psutil.AccessDenied): continue
    processes.sort(key=lambda item: item.get("create_time") or time.time())
    return processes

def _launch_hwinfo_application(exe_path):
    cwd = os.path.dirname(exe_path) or BASE_DIR
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    try:
        subprocess.Popen([exe_path], cwd=cwd, creationflags=flags)
        return "popen"
    except OSError as e:
        if os.name != "nt" or getattr(e, "winerror", None) != 740: raise
        rc = shell32.ShellExecuteW(None, "runas", exe_path, None, cwd, 1)
        if int(rc) <= 32: raise RuntimeError(f"HWiNFO elevated launch failed, code={int(rc)}") from e
        return "runas"

def restart_hwinfo_application_if_needed(force=False, reason="scheduled_check"):
    if not force and not _get_hwinfo_auto_restart_enabled(): return False
    processes = _find_hwinfo_processes()
    uptime_seconds, started_at = _get_hwinfo_wall_clock_age_seconds(processes)
    max_uptime = _get_hwinfo_auto_restart_max_uptime_seconds()
    if not force and (not processes or uptime_seconds is None or uptime_seconds < max_uptime): return False

    exe_path = _get_setting_str("hwinfo.executable_path", "").strip().strip('"')
    if not exe_path: return False

    for item in processes:
        try: item["proc"].terminate()
        except Exception: pass
    
    try: psutil.wait_procs([item["proc"] for item in processes if item.get("proc")], timeout=8)
    except Exception: pass

    try:
        WORKER_STATE["last_hwinfo_launch_mode"] = _launch_hwinfo_application(exe_path)
        WORKER_STATE["last_hwinfo_app_restart_at"] = time.time()
        WORKER_STATE["last_hwinfo_app_restart_reason"] = str(reason)
        return True
    except Exception as e:
        log_hwinfo_error(f"HWiNFO restart error: {e}")
        return False

def ensure_worker_processes_running():
    from panel_globals import WORKER_STATE, WORKER_RESTART_COOLDOWN_SECONDS
    now = time.time()
    proc = WORKER_STATE.get("hwinfo_proc")
    dead_code = None
    try:
        dead_code = proc.poll() if proc is not None else None
    except Exception:
        dead_code = "unknown"
    if proc is None or dead_code is not None:
        if (now - float(WORKER_STATE.get("last_hwinfo_restart", 0))) >= WORKER_RESTART_COOLDOWN_SECONDS:
            from panel_runtime_helpers import _startupinfo_hidden
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hwinfo_worker.py")
            err_path = os.path.join(BASE_DIR, "logs", "hwinfo_worker_stderr.txt")
            os.makedirs(os.path.dirname(err_path), exist_ok=True)
            err_file = open(err_path, "a", encoding="utf-8")
            kwargs = {"cwd": BASE_DIR, "shell": False, "stderr": err_file, "stdout": err_file}
            si = _startupinfo_hidden()
            if si is not None: kwargs["startupinfo"] = si
            if hasattr(subprocess, "CREATE_NO_WINDOW"): kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
            WORKER_STATE["hwinfo_proc"] = subprocess.Popen([sys.executable, script_path], **kwargs)
            WORKER_STATE["last_hwinfo_restart"] = now
            log(f"HWiNFO worker process started pid={WORKER_STATE['hwinfo_proc'].pid} previous_exit={dead_code}")

def hwinfo_application_supervisor_loop():
    while True:
        try:
            if _get_hwinfo_auto_restart_enabled():
                processes = _find_hwinfo_processes()
                age, started_at = _get_hwinfo_wall_clock_age_seconds(processes)
                if age is not None and age >= _get_hwinfo_auto_restart_max_uptime_seconds():
                    restart_hwinfo_application_if_needed(False, f"wall_clock_age_{age/3600:.1f}h")
        except Exception as e:
            log_hwinfo_error(f"HWiNFO supervisor error: {e}")
        time.sleep(300.0)


def get_hwinfo_app_status():
    processes = _find_hwinfo_processes()
    if not processes: return 'not running'
    age, _ = _get_hwinfo_wall_clock_age_seconds(processes)
    if age is None: return 'running'
    return 'running (uptime: ' + _format_duration_short(age) + ')'


