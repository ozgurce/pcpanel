import threading
import time
import ctypes
from panel_globals import (
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, TARGET_VOLUME_LOCK, AUDIO_CONTROLLER
)
from panel_state import mark_system_cache_changed
from panel_logging import log_error
from audio_runtime import (
    send_app_command, APPCOMMAND_VOLUME_MUTE, APPCOMMAND_VOLUME_UP,
    APPCOMMAND_VOLUME_DOWN, APPCOMMAND_MEDIA_PLAY_PAUSE,
    APPCOMMAND_MEDIA_NEXTTRACK, APPCOMMAND_MEDIA_PREVIOUSTRACK
)

TARGET_VOLUME_PERCENT = None

def mute():
    if not toggle_system_mute_exact():
        send_app_command(APPCOMMAND_VOLUME_MUTE)
    sync_target_volume_from_system()

def volume_up():
    send_app_command(APPCOMMAND_VOLUME_UP)
    sync_target_volume_from_system()

def volume_down():
    send_app_command(APPCOMMAND_VOLUME_DOWN)
    sync_target_volume_from_system()

def play_pause():
    send_app_command(APPCOMMAND_MEDIA_PLAY_PAUSE)

def next_track():
    send_app_command(APPCOMMAND_MEDIA_NEXTTRACK)

def prev_track():
    send_app_command(APPCOMMAND_MEDIA_PREVIOUSTRACK)

def get_system_volume_percent_exact():
    try:
        return AUDIO_CONTROLLER.get_volume_percent()
    except Exception as e:
        log_error(f"Exact volume read error: {e}")
        return None

def set_system_volume_percent_exact(target_percent):
    target = normalize_volume_percent(target_percent)
    if target is None:
        return None
    try:
        return AUDIO_CONTROLLER.set_volume_percent(target)
    except Exception as e:
        log_error(f"Exact volume write error: {e}")
        return None

def get_system_mute_state_exact():
    try:
        return AUDIO_CONTROLLER.get_mute_state()
    except Exception as e:
        log_error(f"Mute state read error: {e}")
        return None

def set_system_mute_exact(mute_on: bool):
    try:
        return bool(AUDIO_CONTROLLER.set_mute(mute_on))
    except Exception as e:
        log_error(f"Mute write error: {e}")
        return False

def toggle_system_mute_exact():
    try:
        return bool(AUDIO_CONTROLLER.toggle_mute())
    except Exception:
        current = get_system_mute_state_exact()
        return False if current is None else set_system_mute_exact(not current)

def get_system_volume_percent_legacy():
    try:
        vol = ctypes.c_uint()
        if ctypes.windll.winmm.waveOutGetVolume(0, ctypes.byref(vol)) != 0:
            return None
        left = vol.value & 0xFFFF
        right = (vol.value >> 16) & 0xFFFF
        return max(0, min(100, int(round(((left + right) / 2) / 65535 * 100))))
    except Exception as e:
        log_error(f"Legacy volume read error: {e}")
        return None

def get_system_volume_percent():
    exact = get_system_volume_percent_exact()
    return exact if exact is not None else get_system_volume_percent_legacy()

def normalize_volume_percent(v):
    try:
        return max(0, min(100, int(round(float(v)))))
    except Exception:
        return None

def sync_target_volume_from_system():
    global TARGET_VOLUME_PERCENT
    real_value = get_system_volume_percent()
    if real_value is not None:
        with TARGET_VOLUME_LOCK:
            TARGET_VOLUME_PERCENT = real_value
        changed = False
        with SENSOR_CACHE_LOCK:
            changed = SYSTEM_CACHE.get("volume_percent") != real_value
            SYSTEM_CACHE["volume_percent"] = real_value
            SYSTEM_CACHE["last_update"] = time.time()
        if changed:
            mark_system_cache_changed()
    return real_value

def get_cached_volume_percent():
    with TARGET_VOLUME_LOCK:
        if TARGET_VOLUME_PERCENT is not None:
            return TARGET_VOLUME_PERCENT
    with SENSOR_CACHE_LOCK:
        return SYSTEM_CACHE.get("volume_percent")

def set_system_volume_percent(target_percent):
    global TARGET_VOLUME_PERCENT
    target = normalize_volume_percent(target_percent)
    if target is None:
        return None

    exact_value = set_system_volume_percent_exact(target)
    if exact_value is not None:
        with TARGET_VOLUME_LOCK:
            TARGET_VOLUME_PERCENT = exact_value
        return exact_value

    with TARGET_VOLUME_LOCK:
        if TARGET_VOLUME_PERCENT is None:
            TARGET_VOLUME_PERCENT = get_system_volume_percent() or target
        delta = target - TARGET_VOLUME_PERCENT
        if delta:
            cmd = APPCOMMAND_VOLUME_UP if delta > 0 else APPCOMMAND_VOLUME_DOWN
            for _ in range(abs(delta)):
                send_app_command(cmd)
                time.sleep(0.004)
            TARGET_VOLUME_PERCENT = target
        return TARGET_VOLUME_PERCENT

def _get_audio_refresh_interval_seconds(setting_name):
    from panel_bootstrap import _get_performance_interval_seconds, _get_setting_bool
    interval = _get_performance_interval_seconds(setting_name, 250, 100)
    if _get_setting_bool("frontend.low_performance_mode", False):
        interval = max(interval, 5.0)
    return interval

__all__ = [name for name in globals() if not name.startswith("__")]
