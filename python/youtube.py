# Ver. 0.7
import ctypes
import os
import sys
import threading
import time

_WEBVIEW2_STABILITY_ARGS = (
    "--force-color-profile=srgb",
    "--disable-features=CalculateNativeWinOcclusion,DirectCompositionVideoOverlays,UseHDRTransferFunction",
)
_existing_webview2_args = os.environ.get("WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS", "")
_merged_webview2_args = _existing_webview2_args
for _arg in _WEBVIEW2_STABILITY_ARGS:
    if _arg not in _merged_webview2_args:
        _merged_webview2_args = f"{_merged_webview2_args} {_arg}".strip()
os.environ["WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS"] = _merged_webview2_args

import webview

from settings_runtime import get_setting

from win_utils import (
    find_window_by_title,
    force_window_to_monitor,
    get_monitors,
    pick_monitor,
    print_monitor_summary,
)

DEFAULT_YOUTUBE_URL = "https://www.youtube.com/shorts/"
DEFAULT_WINDOW_TITLE = "YouTube Ekrani"

WEBVIEW_STARTED = threading.Event()


def _get_youtube_settings():
    url = str(get_setting("external_windows.youtube.url", DEFAULT_YOUTUBE_URL) or "").strip() or DEFAULT_YOUTUBE_URL
    window_title = str(get_setting("external_windows.youtube.window_title", DEFAULT_WINDOW_TITLE) or "").strip() or DEFAULT_WINDOW_TITLE
    target_monitor = str(get_setting("external_windows.youtube.target_monitor_device", "") or "").strip()
    return url, window_title, target_monitor
MAIN_WINDOW = None
MAIN_HWND = None


STYLE_JS = r"""
(() => {
    const styleId = 'ozgur-shorts-fix-lite';
    let style = document.getElementById(styleId);
    if (!style) {
        style = document.createElement('style');
        style.id = styleId;
        (document.head || document.documentElement).appendChild(style);
    }
    style.textContent = `
        html, body {
            margin: 0 !important; padding: 0 !important;
            overflow: hidden !important; background: #000 !important;
            width: 100vw !important; height: 100vh !important;
        }
        ::-webkit-scrollbar { display: none !important; }
        video {
            display: block !important;
            contain: none !important;
            transform: none !important;
            will-change: auto !important;
            background: #000 !important;
        }
        :fullscreen video,
        :-webkit-full-screen video,
        .html5-video-player.ytp-fullscreen video,
        .html5-video-player[fullscreen] video {
            width: 100% !important;
            height: 100% !important;
            max-width: 100vw !important;
            max-height: 100vh !important;
            object-fit: contain !important;
            object-position: center center !important;
            left: 0 !important;
            top: 0 !important;
        }
        :fullscreen .html5-video-container,
        :-webkit-full-screen .html5-video-container,
        .html5-video-player.ytp-fullscreen .html5-video-container,
        .html5-video-player[fullscreen] .html5-video-container {
            width: 100vw !important;
            height: 100vh !important;
            left: 0 !important;
            top: 0 !important;
            overflow: hidden !important;
            background: #000 !important;
        }
    `;
    const video =
        document.querySelector('ytd-reel-video-renderer[is-active] video') ||
        document.querySelector('ytd-shorts video') ||
        document.querySelector('video');
    if (video) { try { video.loop = false; } catch (e) {} }
    return 'style-ok';
})()
"""

EVENT_DRIVEN_SHORTS_JS = r"""
(() => {
    try {
        // Onceki bridge'i tamamen temizle
        if (window.__ozgurShortsBridge) {
            const old = window.__ozgurShortsBridge;
            clearInterval(old.checkInterval);
            clearInterval(old.watchdog);
            if (old.observer) old.observer.disconnect();
            if (old.currentVideo && old._endedHandler) {
                old.currentVideo.removeEventListener('ended', old._endedHandler);
            }
            if (old._ytNavHandler) {
                document.removeEventListener('yt-navigate-finish', old._ytNavHandler);
            }
        }

        const st = {
            lastAdvanceAt: 0,
            currentVideo: null,
            checkInterval: null,
            watchdog: null,
            _endedHandler: null,
            _ytNavHandler: null,
        };
        window.__ozgurShortsBridge = st;

        const findVideo = () =>
            document.querySelector('ytd-reel-video-renderer[is-active] video') ||
            document.querySelector('ytd-shorts video') ||
            document.querySelector('video');

        const dispatchArrowDown = () => {
            const ev = new KeyboardEvent('keydown', {
                key: 'ArrowDown', code: 'ArrowDown',
                keyCode: 40, which: 40,
                bubbles: true, cancelable: true
            });
            document.dispatchEvent(ev);
            const player =
                document.querySelector('#shorts-player') ||
                document.querySelector('ytd-shorts');
            if (player) player.dispatchEvent(ev);
        };

        // FIX: transitioning flag'i kaldir - sadece zaman damgasi cooldown kullan.
        // transitioning=true takilinca watchdog yeni videoyu baglamiyor, bridge oluyordu.
        const goNext = () => {
            const now = Date.now();
            if (now - st.lastAdvanceAt < 1800) return;
            st.lastAdvanceAt = now;
            dispatchArrowDown();
        };

        const bindVideo = (video) => {
            if (!video) return;
            if (st.currentVideo === video) {
                video.loop = false;
                return;
            }

            // Eski event listener ve interval'i temizle
            if (st.currentVideo && st._endedHandler) {
                st.currentVideo.removeEventListener('ended', st._endedHandler);
                st._endedHandler = null;
            }
            if (st.checkInterval) {
                clearInterval(st.checkInterval);
                st.checkInterval = null;
            }

            st.currentVideo = video;
            video.loop = false;

            // PRIMARY: ended eventi - en guvenilir yontem
            st._endedHandler = () => { goNext(); };
            video.addEventListener('ended', st._endedHandler);

            // SECONDARY: polling fallback
            // ended bazen YouTube tarafindan tetiklenmiyor (loop modu, kisa video vb.)
            st.checkInterval = setInterval(() => {
                if (!video.isConnected) {
                    clearInterval(st.checkInterval);
                    st.checkInterval = null;
                    return;
                }
                const dur = video.duration;
                if (Number.isFinite(dur) && dur > 0.5 && (dur - video.currentTime) < 0.8) {
                    goNext();
                }
            }, 200);
        };

        // FIX: Watchdog'da transitioning kontrolu YOK.
        // Manuel gecisten sonra yeni videoyu her zaman yakalayabilmeli.
        st.watchdog = setInterval(() => {
            const v = findVideo();
            if (v && v !== st.currentVideo) bindVideo(v);
        }, 800);

        // FIX: YouTube SPA navigasyon eventi - sayfa ici gecislerde bridge'i yenile.
        // Manuel gecis yapilinca bu event atiyor, cooldown sifirlanip yeni video baglanir.
        st._ytNavHandler = () => {
            setTimeout(() => {
                st.lastAdvanceAt = 0; // Manuel gecis sonrasi cooldown'u sifirla
                const v = findVideo();
                if (v) bindVideo(v);
            }, 600);
        };
        document.addEventListener('yt-navigate-finish', st._ytNavHandler);

        bindVideo(findVideo());
        return 'v7-active';
    } catch (e) { return String(e); }
})()
"""


def _eval_js(window, js):
    try:
        result = window.evaluate_js(js)
        return str(result) if result is not None else ''
    except Exception:
        return ''


def install_shorts_bridge(window):
    _eval_js(window, STYLE_JS)
    return _eval_js(window, EVENT_DRIVEN_SHORTS_JS)


def fallback_watchdog_loop():
    """Bridge kaybolursa (tam sayfa yenileme vb.) otomatik yeniden yukler."""
    if not WEBVIEW_STARTED.wait(15):
        return
    while True:
        time.sleep(15)
        try:
            win = MAIN_WINDOW
            if win:
                result = _eval_js(win, "window.__ozgurShortsBridge ? 'ok' : 'missing';")
                if 'missing' in result:
                    install_shorts_bridge(win)
        except Exception:
            pass


def startup(*args):
    global MAIN_WINDOW
    WEBVIEW_STARTED.set()
    win = args[0] if args else MAIN_WINDOW
    if win:
        MAIN_WINDOW = win
        time.sleep(1.0)
        install_shorts_bridge(win)


def on_closed():
    os._exit(0)


def open_window(mon, window_title, youtube_url):
    global MAIN_WINDOW
    window = webview.create_window(
        title=window_title,
        url=youtube_url,
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
    global MAIN_HWND
    try:
        youtube_url, window_title, target_monitor_id_match = _get_youtube_settings()
        monitors = get_monitors(force_refresh=True)
        mon = pick_monitor(monitors, target_monitor_id_match)
        print_monitor_summary(mon)

        def after_start():
            global MAIN_HWND
            if not WEBVIEW_STARTED.wait(10):
                return
            hwnd = find_window_by_title(window_title, timeout=10)
            if hwnd:
                MAIN_HWND = hwnd
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
                force_window_to_monitor(hwnd, mon, horizontal_bleed=0, bottom_inset=0, disable_shadow=True)
                win = MAIN_WINDOW
                if win is not None:
                    install_shorts_bridge(win)

        threading.Thread(target=after_start, daemon=True).start()
        threading.Thread(target=fallback_watchdog_loop, daemon=True).start()
        open_window(mon, window_title, youtube_url)

    except Exception as e:
        print("HATA:", e)
        input("Kapatmak icin Enter...")
        sys.exit(1)


if __name__ == "__main__":
    main()
