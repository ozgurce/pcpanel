# File Version: 1.0
import os
import time
import json
import threading
import ctypes
import sys
from panel_globals import (
    RUNTIME_DIR, HWINFO_LIVE_JSON, HWINFO_SNAPSHOT_MAX_AGE_SECONDS,
    HWINFO_SNAPSHOT_EVENT_NAME, HWINFO_SNAPSHOT_MIN_STAT_SECONDS,
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, WORKER_STATE
)
from panel_bootstrap import (
    _get_performance_interval_seconds, _get_fps_refresh_interval_seconds
)
from panel_logging import log, log_hwinfo_error
from panel_state import mark_system_cache_changed

# Internal cache for snapshot reading
HWINFO_SNAPSHOT_READ_CACHE = {"mtime_ns": None, "size": None, "payload": None, "checked_at": 0.0}

def _read_latest_hwinfo_snapshot():
    now = time.time()
    if (HWINFO_SNAPSHOT_READ_CACHE["payload"] and 
        (now - HWINFO_SNAPSHOT_READ_CACHE["checked_at"]) < HWINFO_SNAPSHOT_MIN_STAT_SECONDS):
        return HWINFO_SNAPSHOT_READ_CACHE["payload"]
    
    try:
        st = os.stat(HWINFO_LIVE_JSON)
        if (now - st.st_mtime) > HWINFO_SNAPSHOT_MAX_AGE_SECONDS: return None
        
        with open(HWINFO_LIVE_JSON, "r", encoding="utf-8") as f:
            payload = json.load(f)
            HWINFO_SNAPSHOT_READ_CACHE.update({"payload": payload, "checked_at": now})
            return payload
    except Exception: return None

def _write_hwinfo_snapshot(payload):
    tmp_path = None
    try:
        os.makedirs(RUNTIME_DIR, exist_ok=True)
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        tmp_path = f"{HWINFO_LIVE_JSON}.{os.getpid()}.{threading.get_ident()}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(data)

        last_error = None
        for delay in (0.02, 0.05, 0.10, 0.20, 0.35):
            try:
                os.replace(tmp_path, HWINFO_LIVE_JSON)
                return True
            except PermissionError as e:
                last_error = e
                time.sleep(delay)

        # On Windows, readers that do not share delete access can briefly block
        # os.replace(). A direct rewrite is the least bad fallback for runtime
        # cache data; readers already tolerate transient invalid/missing JSON.
        for delay in (0.05, 0.10, 0.20):
            try:
                with open(HWINFO_LIVE_JSON, "w", encoding="utf-8") as f:
                    f.write(data)
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
                return True
            except PermissionError as e:
                last_error = e
                time.sleep(delay)

        if last_error is not None:
            raise last_error
        os.replace(tmp_path, HWINFO_LIVE_JSON)
        return True
    except Exception as e:
        log_hwinfo_error(f"Snapshot write error: {e}")
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        return False

def _apply_hwinfo_payload_to_cache(hw_data, now=None):
    if not isinstance(hw_data, dict): return
    from panel_globals import SYSTEM_CACHE
    with SENSOR_CACHE_LOCK:
        SYSTEM_CACHE.update(hw_data)
        SYSTEM_CACHE["last_update"] = now or time.time()
    mark_system_cache_changed()

def _wait_hwinfo_snapshot_event(timeout_seconds):
    # This is a simplified version; real win32 event waiting would be better
    time.sleep(timeout_seconds)

def run_hwinfo_worker_mode():
    from panel_hwinfo_reader import read_hwinfo_metrics
    from panel_bootstrap import _get_hwinfo_worker_refresh_interval_seconds
    log("HWiNFO worker started")
    last_empty_log = 0.0
    while True:
        try:
            data = read_hwinfo_metrics()
            if not data and (time.time() - last_empty_log) >= 5.0:
                last_empty_log = time.time()
                log_hwinfo_error("HWiNFO worker is running but produced empty data.")
            ts = time.time()
            _write_hwinfo_snapshot({"ts": ts, "pid": os.getpid(), "data": data})
            # Worker heartbeat should mean "worker loop is alive".
            # The reader thread may not run yet, so update it here too.
            try:
                WORKER_STATE["last_hwinfo_seen"] = ts
            except Exception:
                pass
            time.sleep(_get_hwinfo_worker_refresh_interval_seconds())
        except Exception as e:
            log_hwinfo_error(f"Worker loop error: {type(e).__name__}: {e}")
            time.sleep(2.0)
