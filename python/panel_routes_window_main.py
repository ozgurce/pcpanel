# File Version: 1.0
import os
import sys
import time
import json
import threading
import asyncio
import ctypes
import urllib.request
import psutil
import webview
from aiohttp import web

from panel_globals import (
    BASE_DIR, PORT, RUNTIME_DIR, WEBVIEW_DATA_DIR,
    SERVER_READY, WEBVIEW_STARTED,
    SERVER_START_FAILED, PANEL_WEBVIEW_WINDOW,
    WINDOW_TITLE_BASE, SENSOR_CACHE_LOCK, SYSTEM_CACHE,
    WORKER_STATE, REFRESH_LOCK, HATA_HTML_FILE_PATH,
    SITEMAP_HTML_FILE_PATH, HTML_FILE_PATH, HTML_VERTICAL_FILE_PATH,
    BOOT_TIME_SEC, FALLBACK_STARTUP_ERROR_MIN_INTERVAL_SECONDS,
    URL_MODE
)
from panel_bootstrap import (
    _get_setting_str, _get_setting_int, _get_setting_float, _get_setting_bool,
    _get_window_str, _get_window_bool, _get_window_int,
    _get_window_monitor_device, _get_keep_window_alive_min_interval_seconds,
    _close_shared_http_sessions
)
from panel_logging import log, log_error, log_hwinfo_error
from panel_state import (
    mark_system_cache_changed, shutdown_runtime_resources,
    clear_webview_cache, startup_mark, reset_startup_profile
)
from panel_runtime_helpers import (
    safe_execute, hide_current_process_windows,
    restore_default_process_scheduling
)
import win_utils

# Rotalar icin handler'lar
from panel_assets import root, root_dikey, serve_resimler_no_cache, serve_fonts_no_cache
from panel_settings_smartthings import (
    serve_js, serve_liquid_themes_js, serve_settings_i18n_js,
    serve_settings_i18n_tr_js, serve_settings_i18n_en_js,
    serve_settings_theme_light_css, serve_settings_theme_dark_css,
    command, settings_root, api_settings_get, api_settings_post,
    api_settings_reset, api_monitors, smartthings_climate_status,
    smartthings_climate_level, smartthings_climate_power,
    smartthings_oauth_callback
)
from panel_system import status
from panel_websocket_status import websocket_status
from panel_ws_logs_routes import (
    hata_root, hata_data, tuya_pc_debug, api_logs_clear,
    api_tuya_logs_clear, api_hwinfo_restart, sitemap_root,
    sitemap_data, health, api_health_report,
    tuya_devices_status, tuya_toggle, tuya_set_brightness, api_tuya_check, api_tuya_reset
)
from panel_misc_actions import (
    check_refresh, trigger_refresh, shift_refresh_now
)
from panel_weather import meteo_weather, update_weather_cache_once
from panel_media import media_seek, run_media_coro, _seek_current_media_async, ensure_media_loop
from panel_audio_controls import sync_target_volume_from_system
from panel_network import get_network_speed_mbps

FALLBACK_STARTUP_ERROR_LAST_WRITE_TS = 0.0
app = web.Application()
_ROUTES_REGISTERED = False

def register_routes():
    global _ROUTES_REGISTERED
    if _ROUTES_REGISTERED: return app
    _ROUTES_REGISTERED = True
    app.on_cleanup.append(_close_shared_http_sessions)
    app.router.add_get("/", root)
    app.router.add_get("/dikey", root_dikey)
    app.router.add_get("/script.js", serve_js)
    app.router.add_get("/js/script.js", serve_js)
    app.router.add_get("/liquid_themes.js", serve_liquid_themes_js)
    app.router.add_get("/js/liquid_themes.js", serve_liquid_themes_js)
    app.router.add_get("/settings_i18n.js", serve_settings_i18n_js)
    app.router.add_get("/js/settings_i18n.js", serve_settings_i18n_js)
    app.router.add_get("/settings_i18n_tr.js", serve_settings_i18n_tr_js)
    app.router.add_get("/js/settings_i18n_tr.js", serve_settings_i18n_tr_js)
    app.router.add_get("/settings_i18n_en.js", serve_settings_i18n_en_js)
    app.router.add_get("/js/settings_i18n_en.js", serve_settings_i18n_en_js)
    app.router.add_get("/settings-theme-light.css", serve_settings_theme_light_css)
    app.router.add_get("/settings-theme-dark.css", serve_settings_theme_dark_css)
    app.router.add_get("/status", status)
    app.router.add_get("/weather/meteo", meteo_weather)
    app.router.add_get("/weather/mgm", meteo_weather)
    app.router.add_get("/health", health)
    app.router.add_get("/hata", hata_root)
    app.router.add_get("/hata/data", hata_data)
    app.router.add_get("/sitemap", sitemap_root)
    app.router.add_get("/sitemap/data", sitemap_data)
    app.router.add_get("/settings", settings_root)
    app.router.add_get("/api/settings", api_settings_get)
    app.router.add_get("/api/health/report", api_health_report)
    app.router.add_post("/api/logs/clear", api_logs_clear)
    app.router.add_post("/api/tuya/logs/clear", api_tuya_logs_clear)
    app.router.add_post("/api/hwinfo/restart", api_hwinfo_restart)
    app.router.add_post("/api/settings", api_settings_post)
    app.router.add_post("/api/settings/reset", api_settings_reset)
    app.router.add_post("/api/shift/refresh", shift_refresh_now)
    app.router.add_get("/api/monitors", api_monitors)
    app.router.add_get("/callback", smartthings_oauth_callback)
    app.router.add_get("/smartthings/oauth/callback", smartthings_oauth_callback)
    app.router.add_get("/smartthings/climate/status", smartthings_climate_status)
    app.router.add_post("/smartthings/climate/level", smartthings_climate_level)
    app.router.add_post("/smartthings/climate/power", smartthings_climate_power)
    app.router.add_get("/ws/status", websocket_status)
    app.router.add_get("/media/seek", media_seek)
    app.router.add_get("/tuya/status", tuya_devices_status)
    app.router.add_get("/tuya/pc_debug", tuya_pc_debug)
    app.router.add_get("/tuya/toggle/{device_key}", tuya_toggle)
    app.router.add_get("/tuya/brightness/{device_key}", tuya_set_brightness)
    app.router.add_post("/api/tuya/check", api_tuya_check)
    app.router.add_post("/api/tuya/reset", api_tuya_reset)
    app.router.add_get("/check_refresh", check_refresh)
    app.router.add_get("/trigger_refresh", trigger_refresh)
    app.router.add_get("/resimler/{path:.*}", serve_resimler_no_cache)
    app.router.add_get("/fonts/{path:.*}", serve_fonts_no_cache)
    app.router.add_get("/assets/images/{path:.*}", serve_resimler_no_cache)
    app.router.add_get("/assets/fonts/{path:.*}", serve_fonts_no_cache)
    for r in ["/shutdown", "/restart", "/sleep", "/lock", "/restart_app", "/spotify", "/shorts", "/kill/spotify", "/kill/shorts", "/taskmgr", "/case_lights/on", "/case_lights/off", "/tiktok", "/admincmd", "/chrome", "/settings", "/mute", "/volup", "/voldown", "/playpause", "/next", "/prev", "/setvolume"]:
        app.router.add_get(r, command)
    app.router.add_post("/dnsredir", command)
    app.router.add_get("/dnsredir", command)
    return app

def build_panel_url(local=True):
    configured_layout = _get_window_str("layout_mode", URL_MODE or "landscape").strip().lower()
    path = "/dikey" if configured_layout in {"dikey", "portrait"} else "/"
    host = "127.0.0.1" if local else "0.0.0.0"
    return f"http://{host}:{PORT}{path}?nocache={int(time.time())}"

def build_panel_health_url(local=True):
    host = "127.0.0.1" if local else "0.0.0.0"
    return f"http://{host}:{PORT}/health?nocache={int(time.time())}"

def wait_for_local_server(url=None, timeout=20):
    probe_url = str(url or build_panel_health_url(local=True))
    end = time.time() + timeout
    while time.time() < end:
        try:
            with urllib.request.urlopen(probe_url, timeout=1.0) as r:
                if 200 <= getattr(r, "status", 200) < 500: return True
        except Exception: pass
        time.sleep(0.12)
    return False

def choose_monitor(monitors):
    if not monitors: raise RuntimeError("Monitor not found")
    target_device = _get_window_monitor_device().lower()
    if target_device:
        try: return win_utils.pick_monitor(monitors, target_device)
        except Exception: pass
    for mon in monitors:
        if bool(mon.get("primary")): return mon
    return monitors[0]

def _is_fullscreen_foreground(panel_hwnd, mon):
    try:
        fg = ctypes.windll.user32.GetForegroundWindow()
        if not fg or fg == panel_hwnd: return False
        rect = win_utils.RECT()
        if not ctypes.windll.user32.GetWindowRect(fg, ctypes.byref(rect)): return False
        w, h = rect.right - rect.left, rect.bottom - rect.top
        if w >= mon["width"] and h >= mon["height"]: return True
        for m in win_utils.get_monitors():
            if w >= m["width"] and h >= m["height"]: return True
        return False
    except Exception: return False

def _panel_keep_window_alive_should_reposition(hwnd, mon):
    return not _is_fullscreen_foreground(hwnd, mon)

def keep_window_alive(hwnd, mon):
    interval_ms = _get_window_int("keep_window_alive_interval_ms", 2000)
    panel_width = max(400, _get_window_int("panel_width", int(mon["logical_width"])))
    panel_height = max(300, _get_window_int("panel_height", int(mon["logical_height"])))
    fit_to_monitor = _get_window_bool("fit_to_monitor", True)
    use_fs_repo = fit_to_monitor or (panel_width >= int(mon["logical_width"]) and panel_height >= int(mon["logical_height"]))
    return win_utils.keep_window_alive(
        hwnd, mon, horizontal_bleed=1, bottom_inset=0,
        interval_seconds=max(_get_keep_window_alive_min_interval_seconds(), float(interval_ms) / 1000.0),
        on_loop=lambda h, m: hide_current_process_windows(except_hwnd=h),
        disable_shadow=True,
        should_reposition=(lambda _h, _m: True) if fit_to_monitor else (_panel_keep_window_alive_should_reposition if use_fs_repo else (lambda _h, _m: False)),
    )

def _get_pids_listening_on_port(port: int):
    pids = set()
    try:
        for conn in psutil.net_connections(kind="inet"):
            try:
                laddr = getattr(conn, "laddr", None)
                if not laddr or getattr(laddr, "port", None) != int(port): continue
                if str(getattr(conn, "status", "") or "").upper() != "LISTEN": continue
                pid = getattr(conn, "pid", None)
                if pid and int(pid) != os.getpid(): pids.add(int(pid))
            except Exception: continue
    except Exception: return []
    return sorted(pids)

def ensure_server_port_available(port: int, timeout_seconds: float = 6.0):
    initial_pids = _get_pids_listening_on_port(port)
    if not initial_pids: return True
    deadline = time.time() + max(1.0, float(timeout_seconds or 0))
    while time.time() < deadline:
        pids = _get_pids_listening_on_port(port)
        if not pids: return True
        for pid in pids:
            try:
                proc = psutil.Process(pid)
                log(f"Closing process using port {port}: pid={pid}")
                proc.terminate()
            except Exception as e: log_error(f"Error terminating pid={pid}: {e}")
        time.sleep(0.6)
        remaining = _get_pids_listening_on_port(port)
        if not remaining: return True
        for pid in remaining:
            try:
                proc = psutil.Process(pid)
                if proc.is_running(): proc.kill()
            except Exception: pass
        time.sleep(0.6)
    return False

def server_thread():
    async def _start():
        global SERVER_START_FAILED
        startup_mark("server_thread._start.begin")
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", PORT).start()
        SERVER_START_FAILED = None
        SERVER_READY.set()
        while True: await asyncio.sleep(3600)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try: loop.run_until_complete(_start())
    except Exception as e:
        SERVER_START_FAILED = e
        log_error(f"Server error: {e}")
        SERVER_READY.set()
    finally: loop.close()

def get_panel_webview_hwnd():
    # PANEL_WEBVIEW_WINDOW import ile kopyalaninca None'da kalabiliyor.
    # Bu yuzden her seferinde panel_globals uzerinden canli referansi oku.
    try:
        import panel_globals as _pg
        window = getattr(_pg, "PANEL_WEBVIEW_WINDOW", None)
    except Exception:
        window = None
    if not window:
        return None

    native = getattr(window, "native", None)
    for attr_path in (("Handle",), ("handle",), ("window", "Handle"), ("window", "handle")):
        obj = native
        try:
            for part in attr_path:
                obj = getattr(obj, part, None)
            if obj is None:
                continue
            for cand_name in ("ToInt64", "ToInt32"):
                cand = getattr(obj, cand_name, None)
                if callable(cand):
                    hwnd = int(cand())
                    if hwnd > 0:
                        return hwnd
            hwnd = int(obj)
            if hwnd > 0:
                return hwnd
        except Exception:
            pass
    return None

def open_panel_window(url, mon):
    try:
        fit_to_monitor = _get_window_bool("fit_to_monitor", True)
        # WebView2 koordinatlari DPI ayarina gore degisebiliyor. Ilk acilista
        # olabildigince hedef rect'e yakin ac, sonra Win32 ile fiziksel rect'e kilitle.
        if fit_to_monitor:
            panel_width = int(mon.get("width") or mon.get("logical_width") or 1280)
            panel_height = int(mon.get("height") or mon.get("logical_height") or 800)
            panel_x = int(mon.get("left") or mon.get("logical_left") or 0)
            panel_y = int(mon.get("top") or mon.get("logical_top") or 0)
        else:
            panel_width = max(400, _get_window_int("panel_width", int(mon["logical_width"])))
            panel_height = max(300, _get_window_int("panel_height", int(mon["logical_height"])))
            panel_x = int(mon["logical_left"] + (int(mon["logical_width"]) - panel_width) / 2)
            panel_y = int(mon["logical_top"] + (int(mon["logical_height"]) - panel_height) / 2)
        window = webview.create_window(
            title=WINDOW_TITLE_BASE, url=url,
            x=panel_x,
            y=panel_y,
            width=panel_width, height=panel_height,
            frameless=True, on_top=_get_window_bool("always_on_top", True),
            resizable=False, confirm_close=_get_window_bool("confirm_close", False),
            text_select=False,
        )
        import panel_globals
        panel_globals.PANEL_WEBVIEW_WINDOW = window
        window.events.closed += lambda *a: (shutdown_runtime_resources(), os._exit(0))
        clear_webview_cache()
        webview.start(lambda *a: WEBVIEW_STARTED.set(), window, debug=False, private_mode=True, storage_path=WEBVIEW_DATA_DIR)
        os._exit(0)
    except Exception as e:
        log_error(f"Webview launch error: {e}")
        raise

def main():
    reset_startup_profile()
    ensure_media_loop()
    sync_target_volume_from_system()
    delay = max(0.0, _get_setting_float("startup.initial_delay_seconds", 0.0))
    if delay > 0: time.sleep(delay)
    try:
        from panel_hwinfo_snapshot import _read_latest_hwinfo_snapshot
        snapshot = _read_latest_hwinfo_snapshot()
        if snapshot and isinstance(snapshot.get("data"), dict):
            with SENSOR_CACHE_LOCK: SYSTEM_CACHE.update(snapshot["data"])
    except Exception: pass
    ensure_server_port_available(PORT)
    threading.Thread(target=server_thread, daemon=True).start()
    SERVER_READY.wait(8)
    local_url = build_panel_url(local=True)
    if not wait_for_local_server(timeout=20): raise RuntimeError(f"Server failed: {local_url}")
    mon = choose_monitor(win_utils.get_monitors(force_refresh=True))
    def after_start():
        if not WEBVIEW_STARTED.wait(10): return
        from panel_state import start_runtime_threads
        start_runtime_threads()
        restore_default_process_scheduling(include_children=True)
        hwnd = None
        for _ in range(40):
            hwnd = get_panel_webview_hwnd() or win_utils.find_window_by_title(WINDOW_TITLE_BASE, timeout=0.25, process_id=os.getpid()) or win_utils.find_window_by_title(WINDOW_TITLE_BASE, timeout=0.25, process_id=None)
            if hwnd:
                break
            time.sleep(0.25)
        if hwnd:
            try: ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(ctypes.c_int(1)), 4)
            except Exception: pass
            panel_width = max(400, _get_window_int("panel_width", int(mon["logical_width"])))
            panel_height = max(300, _get_window_int("panel_height", int(mon["logical_height"])))
            force_fit = _get_window_bool("fit_to_monitor", True)
            if force_fit or (panel_width >= int(mon["logical_width"]) and panel_height >= int(mon["logical_height"])):
                # WebView2 bazen ilk açılışta DPI/scale yüzünden küçük veya kayık oturuyor.
                # Birkaç kez fiziksel monitor rect'ine zorlamak daha stabil.
                for delay_s in (0.0, 0.15, 0.35, 0.75, 1.25, 2.0, 3.0):
                    if delay_s:
                        time.sleep(delay_s)
                    win_utils.force_window_to_monitor(hwnd, mon, horizontal_bleed=0, bottom_inset=0)
                    try:
                        log(f"Window fit forced: hwnd={hwnd} rect={mon.get('left')},{mon.get('top')} {mon.get('width')}x{mon.get('height')}")
                    except Exception:
                        pass
            else:
                if _get_window_bool("hide_from_taskbar", True): win_utils.hide_from_taskbar(hwnd)
                win_utils.disable_window_shadow(hwnd)
            threading.Thread(target=keep_window_alive, args=(hwnd, mon), daemon=True).start()
    threading.Thread(target=after_start, daemon=True).start()
    open_panel_window(local_url, mon)

if __name__ == "__main__":
    restore_default_process_scheduling(include_children=False)
    main()

__all__ = [name for name in globals() if not name.startswith("__")]




