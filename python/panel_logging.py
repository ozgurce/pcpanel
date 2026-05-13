# File Version: 1.0
import os
import time
import threading
from app_logging import AsyncLineLogger
from panel_globals import LOG_FILE, ERR_FILE, TUYA_LOG_FILE, STARTUP_PROFILE_FILE, STARTUP_PROFILE_LOCK

# Initialize Logger
# Note: In a real app, you might want to load max_lines from settings, 
# but for the logger instance itself, we need a stable reference.
LOGGER = AsyncLineLogger(LOG_FILE, ERR_FILE, max_lines=1500)

STARTUP_PROFILE_T0 = 0.0

def log(text: str):
    # We'll check settings via a helper to avoid circularity if possible, 
    # or just log everything and let the logger handle it if it becomes too complex.
    # For now, keeping it simple.
    LOGGER.log(text)

def log_error(text: str):
    LOGGER.error(text)

def log_hwinfo_error(text: str):
    LOGGER.error(f"[HWINFO] {text}")

def log_tuya_error(text: str):
    LOGGER._enqueue(TUYA_LOG_FILE, f"[ERROR] {text}")

def log_tuya(text: str):
    LOGGER._enqueue(TUYA_LOG_FILE, text)

def log_ws_debug(text: str):
    LOGGER.log(f"WS {text}")

def log_perf(text: str):
    LOGGER.log(f"PERF {text}")

def reset_startup_profile():
    global STARTUP_PROFILE_T0
    STARTUP_PROFILE_T0 = time.perf_counter()
    try:
        os.makedirs(os.path.dirname(STARTUP_PROFILE_FILE), exist_ok=True)
        with STARTUP_PROFILE_LOCK:
            with open(STARTUP_PROFILE_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n=== startup {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n")
    except Exception:
        pass

def startup_mark(step: str):
    try:
        elapsed_ms = 0.0
        if STARTUP_PROFILE_T0:
            elapsed_ms = (time.perf_counter() - STARTUP_PROFILE_T0) * 1000.0
        line = f"{time.strftime('%H:%M:%S')} | {elapsed_ms:8.1f} ms | {step}"
        with STARTUP_PROFILE_LOCK:
            with open(STARTUP_PROFILE_FILE, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        log(f"STARTUP {elapsed_ms:0.1f}ms {step}")
    except Exception:
        pass
