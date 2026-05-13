# File Version: 1.1
import os
import ctypes
import time
import asyncio
import threading
import datetime
import urllib.parse
import re
import aiohttp
from aiohttp import web

from panel_globals import (
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, LYRICS_CACHE, LYRICS_CACHE_MAX_ITEMS,
    LYRICS_CACHE_LOCK, LYRICS_STATE_LOCK, MEDIA_LOOP_READY
)
from panel_state import (
    get_lyrics_state_snapshot, set_lyrics_state, mark_system_cache_changed
)
from panel_logging import log, log_error
from panel_bootstrap import _get_shared_http_session

# Optional imports
try:
    from winsdk.windows.media.control import GlobalSystemMediaTransportControlsSessionManager
    WINSDK_AVAILABLE = True
except Exception:
    WINSDK_AVAILABLE = False

try:
    import pygetwindow as gw
    PYGETWINDOW_AVAILABLE = True
except Exception:
    PYGETWINDOW_AVAILABLE = False

MEDIA_LOOP = None
MEDIA_SESSION_MANAGER = None

def _coinit_media_thread():
    if os.name != "nt": return None
    try:
        ole = ctypes.OleDLL("ole32")
        ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        ole.CoInitializeEx.restype = ctypes.c_long
        hr = int(ole.CoInitializeEx(None, 0)) & 0xFFFFFFFF
        if hr in (0, 1): return ole
        if hr == 0x80010106: return None
        log_error(f"Media COM initialization failed HRESULT=0x{hr:08X}")
    except Exception as exc:
        log_error(f"Media COM initialization error: {exc}")
    return None

def _lyrics_cache_get(track_key):
    with LYRICS_CACHE_LOCK:
        cached = LYRICS_CACHE.get(track_key)
        if cached: LYRICS_CACHE.move_to_end(track_key)
        return cached

def _lyrics_cache_set(track_key, lyrics):
    if not track_key: return
    with LYRICS_CACHE_LOCK:
        LYRICS_CACHE[track_key] = lyrics
        LYRICS_CACHE.move_to_end(track_key)
        while len(LYRICS_CACHE) > LYRICS_CACHE_MAX_ITEMS:
            LYRICS_CACHE.popitem(last=False)

def _clean_lyrics_query(value):
    text = str(value or "").strip()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*[-–—]\s*(official|lyrics?|audio|video|remaster(?:ed)?|live|visualizer).*$", "", text, flags=re.I)
    text = re.sub(r"\((?:official|lyrics?|audio|video|remaster(?:ed)?|live|visualizer)[^)]*\)", "", text, flags=re.I)
    text = re.sub(r"\[(?:official|lyrics?|audio|video|remaster(?:ed)?|live|visualizer)[^\]]*\]", "", text, flags=re.I)
    return re.sub(r"\s+", " ", text).strip()

def _lyrics_headers():
    return {
        "User-Agent": "pc-control-panel/1.1 (https://github.com/ozgurce/pcpanel)",
        "Accept": "application/json",
    }

def _pick_lyrics_from_payload(data):
    if isinstance(data, dict):
        return data.get("syncedLyrics") or data.get("plainLyrics") or ""
    return ""

def _best_lyrics_search_result(items):
    if not isinstance(items, list):
        return None
    for item in items:
        if isinstance(item, dict) and (item.get("syncedLyrics") or item.get("plainLyrics")):
            return item
    return None

async def fetch_lyrics_for_track(title, artist):
    track_key = f"{title}-{artist}"
    set_lyrics_state(track_key=track_key, lyrics="nihil infinitum est", fetching=True)
    try:
        session = _get_shared_http_session("lyrics")
        if session is None:
            raise RuntimeError("lyrics HTTP session is not available")
        timeout = aiohttp.ClientTimeout(total=12, connect=5, sock_read=8)
        clean_title = _clean_lyrics_query(title)
        clean_artist = _clean_lyrics_query(artist)
        params = {
            "track_name": clean_title or str(title or "").strip(),
            "artist_name": clean_artist or str(artist or "").strip(),
        }
        url = "https://lrclib.net/api/get?" + urllib.parse.urlencode(params)
        lyrics = ""
        async with session.get(url, timeout=timeout, headers=_lyrics_headers()) as resp:
            if resp.status == 200:
                data = await resp.json()
                lyrics = _pick_lyrics_from_payload(data)
            elif resp.status not in (404, 400):
                text = await resp.text()
                raise RuntimeError(f"LRCLIB get HTTP {resp.status}: {text[:160]}")

        if not lyrics:
            query = " ".join(part for part in (clean_title, clean_artist) if part).strip()
            if query:
                search_url = "https://lrclib.net/api/search?" + urllib.parse.urlencode({"q": query})
                async with session.get(search_url, timeout=timeout, headers=_lyrics_headers()) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        lyrics = _pick_lyrics_from_payload(_best_lyrics_search_result(data))
                    elif resp.status not in (404, 400):
                        text = await resp.text()
                        raise RuntimeError(f"LRCLIB search HTTP {resp.status}: {text[:160]}")

        if lyrics:
            set_lyrics_state(lyrics=lyrics, fetching=False)
            _lyrics_cache_set(track_key, lyrics)
        else:
            set_lyrics_state(lyrics="nihil infinitum est", fetching=False)
    except Exception as e:
        log_error(f"Lyrics fetch error ({type(e).__name__}): {e!r}")
    finally:
        set_lyrics_state(fetching=False)

def _timeline_seconds(value):
    try:
        if value is None: return 0.0
        if isinstance(value, datetime.timedelta): return max(0.0, float(value.total_seconds()))
        if hasattr(value, "duration"): return max(0.0, float(value.duration) / 10000000.0)
        return max(0.0, float(value))
    except Exception: return 0.0

async def _get_media_info_async():
    global MEDIA_SESSION_MANAGER
    if not WINSDK_AVAILABLE: return {"title": "nihil infinitum est", "is_playing": False}
    try:
        if MEDIA_SESSION_MANAGER is None:
            MEDIA_SESSION_MANAGER = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = MEDIA_SESSION_MANAGER.get_current_session()
        if session is None: return {"title": "nihil infinitum est", "is_playing": False}
        props = await session.try_get_media_properties_async()
        pb_info = session.get_playback_info()

        position = 0.0
        duration = 0.0
        try:
            timeline = session.get_timeline_properties()
            position = _timeline_seconds(getattr(timeline, "position", None))
            start_time = _timeline_seconds(getattr(timeline, "start_time", None))
            end_time = _timeline_seconds(getattr(timeline, "end_time", None))
            duration = max(0.0, end_time - start_time)
            if position >= start_time and start_time > 0:
                position = max(0.0, position - start_time)
            if duration > 0 and position > duration:
                position = duration
        except Exception as timeline_exc:
            log_error(f"Media timeline read error: {timeline_exc}")

        source_app = session.source_app_user_model_id or ""
        title = props.title or "No track info"
        artist = props.artist or ""
        return {
            "title": title,
            "artist": artist,
            "is_playing": pb_info.playback_status == 4 if pb_info else False,
            "source_app": source_app,
            "position": position,
            "duration": duration,
            "track_token": f"{source_app}|{title}|{artist}|{round(duration, 1)}",
        }
    except Exception as e:
        MEDIA_SESSION_MANAGER = None
        log_error(f"Media read error: {e}")
        return {"title": "nihil infinitum est", "is_playing": False}

def ensure_media_loop():
    global MEDIA_LOOP
    if MEDIA_LOOP and MEDIA_LOOP_READY.is_set(): return
    def _loop_thread():
        global MEDIA_LOOP
        ole = _coinit_media_thread()
        MEDIA_LOOP = asyncio.new_event_loop()
        asyncio.set_event_loop(MEDIA_LOOP)
        MEDIA_LOOP_READY.set()
        try: MEDIA_LOOP.run_forever()
        finally:
            if ole: ole.CoUninitialize()
    threading.Thread(target=_loop_thread, daemon=True).start()
    MEDIA_LOOP_READY.wait(timeout=3.0)

def run_media_coro(coro, timeout=4.0):
    ensure_media_loop()
    if not MEDIA_LOOP: return None
    try: return asyncio.run_coroutine_threadsafe(coro, MEDIA_LOOP).result(timeout=timeout)
    except Exception as e:
        log_error(f"Media loop coro error: {e}")
        return None

async def _seek_current_media_async(position_seconds: float):
    if not WINSDK_AVAILABLE: return {'ok': False, 'error': 'WinSDK unavailable'}
    try:
        manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
        session = manager.get_current_session()
        if not session: return {'ok': False, 'error': 'No session'}
        target_ticks = int(round(max(0.0, float(position_seconds)) * 10000000.0))
        ok = await session.try_change_playback_position_async(target_ticks)
        return {'ok': ok}
    except Exception as e:
        return {'ok': False, 'error': str(e)}

async def media_seek(r):
    try:
        pos = float(r.query.get('position', 0))
        result = await asyncio.to_thread(run_media_coro, _seek_current_media_async(pos), 5.0)
        return web.json_response(result or {'ok': False, 'error': 'Timeout'})
    except Exception as e:
        return web.json_response({'ok': False, 'error': str(e)}, status=400)



def update_media_and_lyrics_cache():
    info = run_media_coro(_get_media_info_async())
    if not info:
        return {"next_interval": 1.0}

    title = info.get("title", "nihil infinitum est")
    artist = info.get("artist", "")
    is_playing = info.get("is_playing", False)
    position = max(0.0, float(info.get("position") or 0.0))
    duration = max(0.0, float(info.get("duration") or 0.0))
    source_app = str(info.get("source_app") or "")
    track_token = str(info.get("track_token") or f"{source_app}|{title}|{artist}|{round(duration, 1)}")

    track_key = f"{title}-{artist}"

    current_track_key, _, _ = get_lyrics_state_snapshot()

    if track_key != current_track_key:
        cached_lyrics = _lyrics_cache_get(track_key)
        if cached_lyrics:
            set_lyrics_state(track_key=track_key, lyrics=cached_lyrics, fetching=False)
        else:
            set_lyrics_state(track_key=track_key, lyrics="nihil infinitum est", fetching=False)
            if title != "nihil infinitum est" and title != "No track info":
                ensure_media_loop()
                asyncio.run_coroutine_threadsafe(fetch_lyrics_for_track(title, artist), MEDIA_LOOP)

    with SENSOR_CACHE_LOCK:
        SYSTEM_CACHE["media_title"] = title
        SYSTEM_CACHE["media_artist"] = artist
        SYSTEM_CACHE["media_is_playing"] = is_playing
        SYSTEM_CACHE["media_position"] = position
        SYSTEM_CACHE["media_duration"] = duration
        SYSTEM_CACHE["media_source_app"] = source_app
        SYSTEM_CACHE["media_track_token"] = track_token
        _, lyrics, fetching = get_lyrics_state_snapshot()
        SYSTEM_CACHE["lyrics"] = lyrics
        SYSTEM_CACHE["lyrics_fetching"] = fetching
        SYSTEM_CACHE["last_update"] = time.time()

    mark_system_cache_changed()

    return {"next_interval": 0.5 if is_playing else 1.5}
