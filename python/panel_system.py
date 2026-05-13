import os
import time
import threading
from aiohttp import web
from panel_globals import (
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, BOOT_TIME_SEC, BASE_DIR
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_int, _get_setting_float, _get_setting_bool
)
from panel_logging import log, log_error, log_hwinfo_error
from panel_state import mark_system_cache_changed
from panel_hwinfo_snapshot import _read_latest_hwinfo_snapshot
from panel_audio_controls import (
    sync_target_volume_from_system, get_cached_volume_percent,
    get_system_mute_state_exact
)
from panel_network import get_network_speed_mbps

def get_uptime_string():
    try:
        uptime_sec = max(0, int(time.time() - BOOT_TIME_SEC))
        days, rem = divmod(uptime_sec, 86400)
        hours, rem = divmod(rem, 3600)
        minutes, _ = divmod(rem, 60)
        if days > 0:
            return f"{days}:{hours:01}:{minutes:02}"
        if hours > 0:
            return f"{hours:01}:{minutes:02}"
        return f"{minutes}"
    except Exception:
        return "-"

def _get_uptime_refresh_interval_seconds():
    return 60.0 # Default fallback



def _get_memory_stats():
    """Return RAM usage without requiring psutil."""
    try:
        import psutil
        vm = psutil.virtual_memory()
        total = float(getattr(vm, "total", 0) or 0)
        used = float(getattr(vm, "used", 0) or 0)
        return {
            "ram_percent": round(float(getattr(vm, "percent", 0.0) or 0.0), 1),
            "ram_used_gb": round(used / (1024 ** 3), 1) if used else None,
            "ram_total_gb": round(total / (1024 ** 3), 1) if total else None,
        }
    except Exception:
        pass
    try:
        import ctypes
        import ctypes.wintypes
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.wintypes.DWORD),
                ("dwMemoryLoad", ctypes.wintypes.DWORD),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total = float(stat.ullTotalPhys or 0)
            avail = float(stat.ullAvailPhys or 0)
            used = max(0.0, total - avail)
            return {
                "ram_percent": round(float(stat.dwMemoryLoad), 1),
                "ram_used_gb": round(used / (1024 ** 3), 1) if used else None,
                "ram_total_gb": round(total / (1024 ** 3), 1) if total else None,
            }
    except Exception as exc:
        try: log_error(f"RAM stats read error: {type(exc).__name__}: {exc}")
        except Exception: pass
    return {}


def collect_system_snapshot_sync(
    sync_volume=False,
    read_hwinfo=True,
    read_network=True,
    read_mute=True,
    read_uptime=True,
):
    with SENSOR_CACHE_LOCK:
        current_cache = dict(SYSTEM_CACHE)

    hwinfo = current_cache
    try:
        if read_hwinfo:
            snapshot = _read_latest_hwinfo_snapshot() or {}
            snapshot_data = snapshot.get("data")
            if isinstance(snapshot_data, dict) and snapshot_data:
                hwinfo.update(snapshot_data)
            else:
                # Fallback: if the worker/cache path is not ready yet, read HWiNFO directly.
                # test_hwinfo.py already proved this path works on your machine.
                try:
                    from panel_hwinfo_reader import read_hwinfo_metrics
                    direct_data = read_hwinfo_metrics()
                    if isinstance(direct_data, dict) and direct_data:
                        hwinfo.update(direct_data)
                        try:
                            from panel_hwinfo_snapshot import _apply_hwinfo_payload_to_cache
                            _apply_hwinfo_payload_to_cache(direct_data, now=time.time())
                        except Exception:
                            pass
                except Exception as direct_exc:
                    log_hwinfo_error(f"Direct HWiNFO fallback read error: {type(direct_exc).__name__}: {direct_exc}")
    except Exception as e:
        log_hwinfo_error(f"HWiNFO sensor read error: {type(e).__name__}: {e}")

    volume_percent = sync_target_volume_from_system() if sync_volume else get_cached_volume_percent()
    if read_network:
        download_speed_mbps, upload_speed_mbps = get_network_speed_mbps()
    else:
        download_speed_mbps = SYSTEM_CACHE.get("download_speed_mbps")
        upload_speed_mbps = SYSTEM_CACHE.get("upload_speed_mbps")

    uptime = get_uptime_string() if read_uptime else SYSTEM_CACHE.get("uptime")
    is_muted = get_system_mute_state_exact() if read_mute else SYSTEM_CACHE.get("is_muted")
    memory_stats = _get_memory_stats()
    try:
        if memory_stats:
            with SENSOR_CACHE_LOCK:
                SYSTEM_CACHE.update(memory_stats)
    except Exception:
        pass
    
    return {
        **hwinfo,
        **memory_stats,
        "uptime": uptime,
        "volume_percent": volume_percent,
        "download_speed_mbps": download_speed_mbps,
        "upload_speed_mbps": upload_speed_mbps,
        "is_muted": is_muted,
    }

def get_cached_system_info():
    from panel_loops_shift_status import build_public_status_payload
    # Always merge the latest HWiNFO snapshot into the payload.
    # This keeps the panel working even if the background cache-reader thread is late or failed.
    try:
        snapshot = collect_system_snapshot_sync(
            sync_volume=False,
            read_hwinfo=True,
            read_network=False,
            read_mute=False,
            read_uptime=False,
        )
        return build_public_status_payload(snapshot)
    except Exception as e:
        log_hwinfo_error(f"Status payload HWiNFO merge error: {e}")
        return build_public_status_payload()

async def system_info():
    return get_cached_system_info()

async def status(r):
    return web.json_response(get_cached_system_info())

__all__ = [name for name in globals() if not name.startswith("__")]
