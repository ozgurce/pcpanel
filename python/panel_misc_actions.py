# File Version: 1.0
import os
import time
import threading
import asyncio
import subprocess
from aiohttp import web
from panel_globals import (
    REFRESH_LOCK, REFRESH_REQUESTED
)
from panel_bootstrap import NO_CACHE_HEADERS
from panel_logging import log_error, log_perf
from panel_ws_clients import get_ws_clients_snapshot, unregister_ws_client, _safe_ws_send_json

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LocalAppData%\Google\Chrome\Application\chrome.exe"),
]

def _refresh_shift_cache_now(force=False):
    # This should be in panel_loops_shift_status
    from panel_loops_shift_status import _refresh_shift_cache_now
    return _refresh_shift_cache_now(force=force)

async def check_refresh(r):
    import panel_globals
    with REFRESH_LOCK:
        refresh_now = panel_globals.REFRESH_REQUESTED
        panel_globals.REFRESH_REQUESTED = False
    return web.json_response({"refresh": refresh_now})


async def trigger_refresh(r):
    import panel_globals
    with REFRESH_LOCK:
        panel_globals.REFRESH_REQUESTED = True

    perf_started = time.perf_counter()
    dead_clients = []
    for ws in get_ws_clients_snapshot():
        try:
            if ws.closed:
                dead_clients.append(ws)
                continue
            ok = await _safe_ws_send_json(ws, {"type": "reload"})
            if not ok:
                dead_clients.append(ws)
        except Exception:
            dead_clients.append(ws)

    for ws in dead_clients:
        unregister_ws_client(ws)

    log_perf(f"refresh yayinlandi clients={len(get_ws_clients_snapshot())} dead={len(dead_clients)} elapsed_ms={((time.perf_counter() - perf_started) * 1000.0):.1f}")
    return web.json_response({"ok": True, "ws_clients": len(get_ws_clients_snapshot())})


async def shift_refresh_now(_request):
    try:
        result = await asyncio.to_thread(_refresh_shift_cache_now, True)
        status_code = 200 if result.get("ok") else 500
        return web.json_response(result, status=status_code, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"Shift manual refresh error: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


def _find_chrome():
    for chrome_path in CHROME_CANDIDATES:
        try:
            if os.path.exists(chrome_path):
                return chrome_path
        except Exception as e:
            log_error(f"Chrome path check error ({chrome_path}): {e}")
    return None


def open_url(url: str):
    chrome_path = _find_chrome()
    try:
        if chrome_path:
            subprocess.Popen([chrome_path, url])
            return
        subprocess.Popen(["cmd", "/c", "start", "", url], shell=False)
    except Exception as e:
        log_error(f"URL open error: {e}")


def open_chrome():
    chrome_path = _find_chrome()
    try:
        if chrome_path:
            subprocess.Popen([chrome_path])
            return
        subprocess.Popen(["cmd", "/c", "start", "chrome"], shell=False)
    except Exception as e:
        log_error(f"Chrome launch error: {e}")


def open_spotify():
    try:
        os.startfile("spotify:")
        return
    except Exception:
        pass
    try:
        subprocess.Popen(["cmd", "/c", "start", "", "spotify:"], shell=False)
    except Exception as e:
        log_error(f"Spotify launch error: {e}")

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.     
__all__ = [name for name in globals() if not name.startswith("__")]
