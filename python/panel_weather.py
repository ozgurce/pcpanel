import time
import re
import urllib.parse
import urllib.request
import json
import asyncio
from aiohttp import web
from panel_globals import (
    SENSOR_CACHE_LOCK, SYSTEM_CACHE, WEATHER_FETCH_LOCK
)
from panel_bootstrap import (
    _get_meteo_latitude, _get_meteo_longitude, _get_meteo_location_label,
    _get_meteo_location_query, _get_meteo_geocoding_url, _get_meteo_language,
    _get_meteo_forecast_url, _get_meteo_timezone, _get_weather_refresh_interval_seconds
)
from panel_logging import log_error
from panel_state import mark_system_cache_changed

WEATHER_NEXT_FETCH_TS = 0.0
WEATHER_LOCATION_CACHE = {"coords": None, "label": None, "expires_at": 0.0}

METEO_WEATHER_CODE_LABELS_EN = {
    0: "Clear", 1: "Mostly Clear", 2: "Partly Cloudy", 3: "Cloudy",
    45: "Fog", 48: "Rime Fog", 51: "Light Drizzle", 53: "Drizzle",
    55: "Heavy Drizzle", 56: "Light Freezing Drizzle", 57: "Freezing Drizzle",
    61: "Light Rain", 63: "Rain", 65: "Heavy Rain", 66: "Light Freezing Rain",
    67: "Freezing Rain", 71: "Light Snow", 73: "Snow", 75: "Heavy Snow",
    77: "Snow Grains", 80: "Rain Showers", 81: "Heavy Rain Showers",
    82: "Violent Rain Showers", 85: "Snow Showers", 86: "Heavy Snow Showers",
    95: "Thunderstorm", 96: "Thunderstorm With Hail", 99: "Severe Thunderstorm With Hail",
}

def _meteo_weather_label(code):
    try: return METEO_WEATHER_CODE_LABELS_EN.get(int(code), "Weather")
    except Exception: return "Weather"

def _meteo_request_json(url: str, params=None, timeout: float = 12.0):
    params = dict(params or {})
    query = urllib.parse.urlencode(params)
    if query: url = f"{url}{'&' if '?' in url else '?'}{query}"
    req = urllib.request.Request(url, headers={"User-Agent": "pc-control-panel/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))

def _resolve_meteo_location(force_refresh: bool = False):
    now = time.time()
    if not force_refresh and WEATHER_LOCATION_CACHE["coords"] and now < WEATHER_LOCATION_CACHE["expires_at"]:
        return WEATHER_LOCATION_CACHE["coords"][0], WEATHER_LOCATION_CACHE["coords"][1], WEATHER_LOCATION_CACHE["label"]
    
    lat, lon, label = _get_meteo_latitude(), _get_meteo_longitude(), _get_meteo_location_label()
    query = _get_meteo_location_query()
    
    if query and (lat is None or lon is None):
        res = _meteo_request_json(_get_meteo_geocoding_url(), {"name": query, "count": 1, "language": _get_meteo_language()})
        if res.get("results"):
            best = res["results"][0]
            lat, lon, label = best["latitude"], best["longitude"], best["name"]
    
    WEATHER_LOCATION_CACHE.update({"coords": (lat, lon), "label": label, "expires_at": now + 86400.0})
    return lat, lon, label

def update_weather_cache_once(force=False):
    global WEATHER_NEXT_FETCH_TS
    now = time.time()
    with WEATHER_FETCH_LOCK:
        if not force and now < WEATHER_NEXT_FETCH_TS: return
        try:
            lat, lon, label = _resolve_meteo_location(force_refresh=force)
            res = _meteo_request_json(_get_meteo_forecast_url(), {
                "latitude": lat, "longitude": lon, "current": "temperature_2m,weather_code",
                "daily": "temperature_2m_max,temperature_2m_min", "timezone": _get_meteo_timezone()
            })
            curr = res.get("current", {})
            daily = res.get("daily", {})
            with SENSOR_CACHE_LOCK:
                SYSTEM_CACHE.update({
                    "weather_ok": True, "weather_location": label,
                    "weather_summary": _meteo_weather_label(curr.get("weather_code")),
                    "weather_current_c": curr.get("temperature_2m"),
                    "weather_min_c": daily.get("temperature_2m_min", [None])[0],
                    "weather_max_c": daily.get("temperature_2m_max", [None])[0],
                    "last_update": time.time()
                })
            mark_system_cache_changed()
            WEATHER_NEXT_FETCH_TS = now + _get_weather_refresh_interval_seconds()
        except Exception as e:
            log_error(f"Weather update error: {e}")

def weather_updater_loop():
    while True:
        update_weather_cache_once()
        time.sleep(300)

async def meteo_weather(r):
    try:
        force = str(r.query.get('force') or '').strip().lower() in {'1', 'true', 'yes'}
        await asyncio.to_thread(update_weather_cache_once, force)
        with SENSOR_CACHE_LOCK:
            return web.json_response(dict(SYSTEM_CACHE))
    except Exception as exc:
        return web.json_response({'ok': False, 'error': str(exc)}, status=500)

