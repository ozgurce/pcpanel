# File Version: 1.0
import subprocess
import os
import time
import json
import asyncio
import sys
import threading
from aiohttp import web

from panel_globals import (
    BASE_DIR, DNSREDIR_CMD_DEFAULT,
    RESTART_GUARD_FILE, RESTART_GUARD_WINDOW_SECONDS, RESTART_GUARD_MAX_ATTEMPTS,
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, APP_RESTART_LOCK
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_bool, NO_CACHE_HEADERS
)
from panel_logging import log, log_error
from panel_audio_controls import (
    mute, volume_up, volume_down, play_pause, next_track, prev_track,
    set_system_volume_percent, get_system_mute_state_exact, get_system_volume_percent
)
from panel_misc_actions import open_url, open_chrome, open_spotify
from panel_runtime_helpers import run_case_lights, _popen_hidden
from panel_state import shutdown_runtime_resources, mark_system_cache_changed, set_mute_ws_burst_until
import win_utils

def run_dnsredir_cmd():
    if not DNSREDIR_CMD_DEFAULT or not os.path.exists(DNSREDIR_CMD_DEFAULT):
        return {"ok": False, "error": f"DNS Redir command file not found: {DNSREDIR_CMD_DEFAULT}"}
    _popen_hidden([DNSREDIR_CMD_DEFAULT], cwd=os.path.dirname(DNSREDIR_CMD_DEFAULT))
    return {"ok": True}

def launch_spotify_script():
    open_spotify()
    return {"ok": True}

def kill_spotify_script():
    subprocess.run(["taskkill", "/F", "/IM", "Spotify.exe", "/T"], capture_output=True)
    return {"ok": True}

def launch_youtube_script():
    open_url("https://youtube.com")
    return {"ok": True}

def kill_youtube_script():
    # Chrome tab killing is complex, skipping for now
    return {"ok": True, "message": "Not implemented"}

def _restart_guard_allows(reason=""):
    now = time.time()
    try:
        if os.path.exists(RESTART_GUARD_FILE):
            with open(RESTART_GUARD_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {}
    except Exception:
        data = {}
        
    attempts = []
    for item in data.get("attempts", []):
        try:
            ts = float((item or {}).get("ts") or 0.0)
        except Exception:
            continue
        if now - ts <= RESTART_GUARD_WINDOW_SECONDS:
            attempts.append({"ts": ts, "reason": str((item or {}).get("reason") or "")[:120]})
            
    if len(attempts) >= RESTART_GUARD_MAX_ATTEMPTS:
        return False
        
    attempts.append({"ts": now, "reason": str(reason or "")[:120]})
    try:
        os.makedirs(os.path.dirname(RESTART_GUARD_FILE), exist_ok=True)
        with open(RESTART_GUARD_FILE, "w", encoding="utf-8") as f:
            json.dump({"attempts": attempts}, f, ensure_ascii=False, separators=(",", ":"))
    except Exception:
        pass
    return True


def request_app_restart(reason="manual", delay_seconds=1.0):
    import panel_globals
    with APP_RESTART_LOCK:
        if panel_globals.APP_RESTARTING:
            return False
        if not _restart_guard_allows(reason):
            log_error("Application restart blocked by restart guard")
            return False
        panel_globals.APP_RESTARTING = True

    base_dir = BASE_DIR
    script_path = os.path.join(base_dir, "python", "panel_app.py")

    if getattr(sys, "frozen", False):
        relaunch_cmd = [sys.executable, *sys.argv[1:]]
    else:
        relaunch_cmd = [sys.executable, script_path, *sys.argv[1:]]

    current_pid = os.getpid()

    def _worker():
        try:
            log(f"Application restarting: {reason}")

            helper_delay = max(1.5, float(delay_seconds or 0))
            restart_log_path = os.path.join(base_dir, "logs", "restart_helper.txt")

            helper_code = r"""
import os
import sys
import time
import subprocess

BASE_DIR = {base_dir!r}
CURRENT_PID = {current_pid!r}
RELAUNCH_CMD = {relaunch_cmd!r}
DELAY = {helper_delay!r}
RESTART_LOG_PATH = {restart_log_path!r}

def _restart_log(message):
    try:
        os.makedirs(os.path.dirname(RESTART_LOG_PATH), exist_ok=True)
        with open(RESTART_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + " | " + str(message) + "\n")
    except Exception:
        pass

time.sleep(DELAY)
_restart_log("helper started")

try:
    import psutil
except Exception:
    psutil = None

def _norm_path(value):
    try:
        return os.path.normcase(os.path.abspath(str(value or "")))
    except Exception:
        return os.path.normcase(str(value or ""))

base_norm = _norm_path(BASE_DIR)

targets = []
if psutil is not None:
    for proc in psutil.process_iter(["pid", "name", "cmdline", "cwd"]):
        try:
            pid = int(proc.info.get("pid") or 0)
            if pid <= 0 or pid == os.getpid() or pid == CURRENT_PID:
                continue

            name = str(proc.info.get("name") or "").lower()
            if "python" not in name and name != "py.exe":
                continue

            cmdline = proc.info.get("cmdline") or []
            joined = " ".join(str(x) for x in cmdline).lower().replace("\\", "/")
            cwd_norm = _norm_path(proc.info.get("cwd") or "")

            is_pc_control = (base_norm in joined.replace("/", "\\")) or (cwd_norm == base_norm)
            is_panel_or_worker = ("panel_app.py" in joined) or ("hwinfo_worker.py" in joined)

            if is_pc_control and is_panel_or_worker:
                targets.append(proc)
        except Exception:
            pass

    _restart_log("found targets=" + ",".join(str(getattr(p, "pid", "?")) for p in targets))

    for proc in targets:
        try:
            proc.terminate()
        except Exception as e:
            _restart_log("terminate error pid=" + str(getattr(proc, "pid", "?")) + ": " + str(e))

    if targets:
        psutil.wait_procs(targets, timeout=3.0)

    for proc in targets:
        try:
            if proc.is_running():
                proc.kill()
                _restart_log("killed pid=" + str(getattr(proc, "pid", "?")))
        except Exception:
            pass
else:
    _restart_log("psutil not available in helper")

time.sleep(1.0)

try:
    creationflags = 0
    if os.name == "nt":
        creationflags = 0x08000000 # CREATE_NO_WINDOW

    _restart_log("launching " + str(RELAUNCH_CMD))
    proc = subprocess.Popen(RELAUNCH_CMD, cwd=BASE_DIR, creationflags=creationflags)
    _restart_log("relaunched pid=" + str(proc.pid))
except Exception as e:
    _restart_log("relaunch failed: " + str(e))
""".format(
                base_dir=base_dir,
                current_pid=current_pid,
                relaunch_cmd=relaunch_cmd,
                helper_delay=helper_delay,
                restart_log_path=restart_log_path,
            )

            _popen_hidden([sys.executable, "-c", helper_code], cwd=base_dir)

            time.sleep(0.75)
            shutdown_runtime_resources()
            os._exit(0)

        except Exception as e:
            import panel_globals
            panel_globals.APP_RESTARTING = False
            log_error(f"Application restart error: {e}")

    threading.Thread(target=_worker, daemon=True).start()
    return True


def _run_command_sync(path, request=None):
    try:
        if path == "/shutdown":
            log("System shutdown initiated via HTTP")
            res = subprocess.run(["shutdown", "/s", "/f", "/t", "0"], capture_output=True, text=True)
            if res.returncode != 0:
                log_error(f"Shutdown failed: {res.stderr}")
                return json.dumps({"ok": False, "error": res.stderr})
            return json.dumps({"ok": True})
        elif path == "/restart":
            log("System restart initiated via HTTP")
            res = subprocess.run(["shutdown", "/r", "/f", "/t", "0"], capture_output=True, text=True)
            if res.returncode != 0:
                log_error(f"Restart failed: {res.stderr}")
                return json.dumps({"ok": False, "error": res.stderr})
            return json.dumps({"ok": True})
        elif path == "/sleep":
            log("System sleep initiated via HTTP")
            res = subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], capture_output=True, text=True)
            if res.returncode != 0:
                log_error(f"Sleep failed: {res.stderr}")
                return json.dumps({"ok": False, "error": res.stderr})
            return json.dumps({"ok": True})
    except Exception as e:
        log_error(f"System command execution error ({path}): {e}")
        return json.dumps({"ok": False, "error": str(e)})

    if path == "/lock":
        try:
            win_utils.user32.LockWorkStation()
        except Exception as e:
            log_error(f"Lock error: {e}")
    elif path == "/spotify":
        return json.dumps(launch_spotify_script(), ensure_ascii=False)
    elif path == "/shorts":
        return json.dumps(launch_youtube_script(), ensure_ascii=False)
    elif path == "/kill/spotify":
        return json.dumps(kill_spotify_script(), ensure_ascii=False)
    elif path == "/kill/shorts":
        return json.dumps(kill_youtube_script(), ensure_ascii=False)
    elif path == "/taskmgr":
        try:
            os.startfile("taskmgr.exe")
        except Exception:
            try:
                win_utils.shell32.ShellExecuteW(None, "open", "taskmgr.exe", None, None, 1)
            except Exception as e:
                log_error(f"Task Manager launch error: {e}")
    elif path == "/tiktok":
        open_url("https://tiktok.com")
    elif path == "/admincmd":
        win_utils.shell32.ShellExecuteW(None, "runas", "cmd.exe", None, None, 1)
    elif path == "/chrome":
        open_chrome()
    elif path == "/dnsredir":
        return json.dumps(run_dnsredir_cmd(), ensure_ascii=False)
    elif path == "/case_lights/on":
        return json.dumps(run_case_lights("on"), ensure_ascii=False)
    elif path == "/case_lights/off":
        return json.dumps(run_case_lights("off"), ensure_ascii=False)
    elif path == "/restart_app":
        ok = request_app_restart(reason="HTTP /restart_app", delay_seconds=1.0)
        return json.dumps({"ok": ok, "message": "restart scheduled" if ok else "restart already in progress"}, ensure_ascii=False)
    elif path == "/settings":
        try:
            os.startfile("ms-settings:")
        except Exception:
            pass
    elif path == "/mute":
        mute()
        muted = get_system_mute_state_exact()
        volume_percent = get_system_volume_percent()

        with SENSOR_CACHE_LOCK:
            SYSTEM_CACHE["is_muted"] = muted
            SYSTEM_CACHE["volume_percent"] = volume_percent
            SYSTEM_CACHE["last_update"] = time.time()
        mark_system_cache_changed()
        set_mute_ws_burst_until(time.time() + 1.2)

        return json.dumps({
            "ok": muted is not None,
            "is_muted": muted,
            "volume_percent": volume_percent,
        })
    elif path == "/volup":
        volume_up()
    elif path == "/voldown":
        volume_down()
    elif path == "/playpause":
        play_pause()
    elif path == "/next":
        next_track()
    elif path == "/prev":
        prev_track()
    elif path == "/setvolume":
        value = request.query.get("value", "0") if request is not None else "0"
        set_value = set_system_volume_percent(value)
        with SENSOR_CACHE_LOCK:
            SYSTEM_CACHE["volume_percent"] = set_value
            SYSTEM_CACHE["last_update"] = time.time()
        mark_system_cache_changed()
        return json.dumps({"ok": set_value is not None, "volume_percent": set_value})
    return "OK"


async def run_command(path, request=None):
    return await asyncio.to_thread(_run_command_sync, path, request)

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.     
__all__ = [name for name in globals() if not name.startswith("__")]
