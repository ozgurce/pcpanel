import threading
import time
import asyncio
from panel_globals import (
    SENSOR_CACHE_LOCK, SYSTEM_CACHE_EVENT, SYSTEM_CACHE,
    PUBLIC_STATUS_CACHE_LOCK, PUBLIC_STATUS_CACHE,
    LYRICS_STATE_LOCK
)

def get_lyrics_state_snapshot():
    from panel_globals import CURRENT_TRACK_KEY, CURRENT_LYRICS, LYRICS_FETCHING
    with LYRICS_STATE_LOCK:
        return CURRENT_TRACK_KEY, CURRENT_LYRICS, LYRICS_FETCHING

def set_lyrics_state(*, track_key=None, lyrics=None, fetching=None):
    import panel_globals
    with LYRICS_STATE_LOCK:
        if track_key is not None: panel_globals.CURRENT_TRACK_KEY = track_key
        if lyrics is not None: panel_globals.CURRENT_LYRICS = lyrics
        if fetching is not None: panel_globals.LYRICS_FETCHING = bool(fetching)

def mark_system_cache_changed():
    try:
        SYSTEM_CACHE_EVENT.set()
    except Exception:
        pass

def _wait_system_cache_event(timeout_seconds):
    try:
        timeout = max(0.05, float(timeout_seconds or 0.05))
    except Exception:
        timeout = 0.05
    fired = SYSTEM_CACHE_EVENT.wait(timeout)
    if fired:
        try:
            SYSTEM_CACHE_EVENT.clear()
        except Exception:
            pass
    return fired

def get_mute_ws_burst_until():
    from panel_globals import MUTE_WS_BURST_UNTIL_TS
    return MUTE_WS_BURST_UNTIL_TS

def set_mute_ws_burst_until(ts):
    import panel_globals
    panel_globals.MUTE_WS_BURST_UNTIL_TS = float(ts or 0.0)

async def _wait_system_cache_event_async(timeout_seconds):
    return await asyncio.to_thread(_wait_system_cache_event, timeout_seconds)

def shutdown_runtime_resources():
    # Implementation placeholder
    pass

def clear_webview_cache():
    # Implementation placeholder
    pass

def startup_mark(label):
    # Implementation placeholder
    pass

def reset_startup_profile():
    # Implementation placeholder
    pass

def start_runtime_threads():
    # Implementation placeholder
    pass

import threading
import os
import sys

def start_runtime_threads():
    from panel_logging import log
    from panel_tuya import start_runtime_threads as start_tuya_threads
    from panel_hwinfo_process import hwinfo_application_supervisor_loop
    from panel_weather import weather_updater_loop
    from tuya_runtime import tuya_updater_loop
    from panel_loops_shift_status import (
        media_updater_loop, volume_updater_loop, mute_updater_loop,
        network_updater_loop, uptime_updater_loop, shift_updater_loop
    )

    log("Starting background runtime threads...")

    # Start Tuya/HWiNFO core
    start_tuya_threads()

    # Define loops to start
    loops = [
        ("hwinfo_supervisor", hwinfo_application_supervisor_loop),
        ("weather", weather_updater_loop),
        ("tuya_updater", tuya_updater_loop),
        ("media", media_updater_loop),
        ("volume", volume_updater_loop),
        ("mute", mute_updater_loop),
        ("network", network_updater_loop),
        ("uptime", uptime_updater_loop),
        ("shift", shift_updater_loop),
    ]

    for name, target in loops:
        t = threading.Thread(target=target, daemon=True, name=name)
        t.start()
        log(f"Thread started: {name}")

