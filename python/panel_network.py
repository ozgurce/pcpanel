# File Version: 1.0
import time
import psutil
import threading
from panel_logging import log_error

NET_SPEED_LOCK = threading.Lock()
NET_SPEED_LAST_BYTES = None
NET_SPEED_LAST_TS = None
NET_SPEED_DOWN_MBPS = 0.0
NET_SPEED_UP_MBPS = 0.0

def get_network_speed_mbps():
    global NET_SPEED_LAST_BYTES, NET_SPEED_LAST_TS, NET_SPEED_DOWN_MBPS, NET_SPEED_UP_MBPS
    try:
        now = time.time()
        counters = psutil.net_io_counters()
        current = (counters.bytes_recv, counters.bytes_sent)

        with NET_SPEED_LOCK:
            if NET_SPEED_LAST_BYTES is None:
                NET_SPEED_LAST_BYTES, NET_SPEED_LAST_TS = current, now
                return 0.0, 0.0

            dt = max(0.001, now - NET_SPEED_LAST_TS)
            down = (current[0] - NET_SPEED_LAST_BYTES[0]) * 8 / (1_000_000 * dt)
            up = (current[1] - NET_SPEED_LAST_BYTES[1]) * 8 / (1_000_000 * dt)

            NET_SPEED_LAST_BYTES, NET_SPEED_LAST_TS = current, now
            NET_SPEED_DOWN_MBPS, NET_SPEED_UP_MBPS = down, up
            return down, up
    except Exception as e:
        log_error(f"Network speed error: {e}")
        return NET_SPEED_DOWN_MBPS, NET_SPEED_UP_MBPS

def _get_network_refresh_interval_seconds():
    from panel_bootstrap import _get_network_refresh_interval_seconds as _get_val
    return _get_val()

def network_updater_loop():
    from panel_globals import SYSTEM_CACHE, SENSOR_CACHE_LOCK
    from panel_state import mark_system_cache_changed
    while True:
        d, u = get_network_speed_mbps()
        with SENSOR_CACHE_LOCK:
            SYSTEM_CACHE["download_speed_mbps"] = d
            SYSTEM_CACHE["upload_speed_mbps"] = u
        mark_system_cache_changed()
        time.sleep(_get_network_refresh_interval_seconds())

__all__ = [name for name in globals() if not name.startswith("__")]
