# File Version: 1.0
import ctypes
import os
import sys
import threading
import webview

from settings_runtime import get_setting

from win_utils import (
    find_window_by_title,
    force_window_to_monitor,
    get_monitors,
    keep_window_alive,
    pick_monitor,
    print_monitor_summary,
)

DEFAULT_SPOTIFY_URL = "https://open.spotify.com/intl-tr/"
DEFAULT_WINDOW_TITLE = "Spotify Ekrani"

WEBVIEW_STARTED = threading.Event()
MAIN_WINDOW = None


def _get_spotify_settings():
    url = str(get_setting("external_windows.spotify.url", DEFAULT_SPOTIFY_URL) or "").strip() or DEFAULT_SPOTIFY_URL
    window_title = str(get_setting("external_windows.spotify.window_title", DEFAULT_WINDOW_TITLE) or "").strip() or DEFAULT_WINDOW_TITLE
    target_monitor = str(get_setting("external_windows.spotify.target_monitor_device", "") or "").strip()
    return url, window_title, target_monitor


def startup(*args):
    global MAIN_WINDOW
    if args:
        MAIN_WINDOW = args[0]
    WEBVIEW_STARTED.set()


def on_closed():
    os._exit(0)


def open_window(mon, window_title, spotify_url):
    global MAIN_WINDOW
    window = webview.create_window(
        title=window_title,
        url=spotify_url,
        x=mon["logical_left"],
        y=mon["logical_top"],
        width=mon["logical_width"],
        height=mon["logical_height"],
        frameless=True,
        on_top=True,
        easy_drag=False,
        resizable=False,
        confirm_close=False,
        minimized=False,
        text_select=True,
        background_color="#000000",
    )
    MAIN_WINDOW = window

    try:
        window.events.closed += on_closed
    except Exception:
        pass

    webview.start(startup, window, debug=False, private_mode=False)


def main():
    try:
        spotify_url, window_title, target_monitor_id_match = _get_spotify_settings()
        monitors = get_monitors(force_refresh=True)
        mon = pick_monitor(monitors, target_monitor_id_match)
        print_monitor_summary(mon)

        def after_start():
            if not WEBVIEW_STARTED.wait(10):
                return
            hwnd = find_window_by_title(window_title, timeout=10)
            if hwnd:
                try:
                    DWMWA_WINDOW_CORNER_PREFERENCE = 33
                    DWMWCP_DONOTROUND = 1
                    ctypes.windll.dwmapi.DwmSetWindowAttribute(
                        hwnd,
                        DWMWA_WINDOW_CORNER_PREFERENCE,
                        ctypes.byref(ctypes.c_int(DWMWCP_DONOTROUND)),
                        ctypes.sizeof(ctypes.c_int)
                    )
                except Exception:
                    pass

                force_window_to_monitor(hwnd, mon, horizontal_bleed=1, bottom_inset=0, disable_shadow=False)
                threading.Thread(
                    target=keep_window_alive,
                    args=(hwnd, mon),
                    kwargs={"horizontal_bleed": 1, "bottom_inset": 0, "interval_seconds": 2.0, "disable_shadow": False},
                    daemon=True,
                ).start()

        threading.Thread(target=after_start, daemon=True).start()
        open_window(mon, window_title, spotify_url)

    except Exception as e:
        print("HATA:", e)
        input("Kapatmak icin Enter...")
        sys.exit(1)


if __name__ == "__main__":
    main()
