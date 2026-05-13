# File Version: 1.0
import os
import time
import json
import asyncio
import urllib.parse
import base64
import html
import aiohttp
from aiohttp import web

from panel_globals import (
    JS_FILE_PATH, LIQUID_THEMES_JS_FILE_PATH, SETTINGS_I18N_JS_FILE_PATH,
    SETTINGS_I18N_TR_JS_FILE_PATH, SETTINGS_I18N_EN_JS_FILE_PATH,
    SETTINGS_THEME_LIGHT_CSS_FILE_PATH, SETTINGS_THEME_DARK_CSS_FILE_PATH,
    SETTINGS_HTML_FILE_PATH, NO_CACHE_HEADERS
)
from panel_assets import _load_text_asset_response, _load_html_response
from panel_commands import run_command
from panel_bootstrap import (
    _get_setting_str, _get_shared_http_session, refresh_runtime_settings_snapshot
)
from panel_logging import log_error
import win_utils
from settings_runtime import load_settings, save_settings, reset_settings

async def serve_js(r):
    return _load_text_asset_response(JS_FILE_PATH, "JavaScript asset", "application/javascript")


async def serve_liquid_themes_js(r):
    return _load_text_asset_response(LIQUID_THEMES_JS_FILE_PATH, "Liquid theme JavaScript asset", "application/javascript")


async def serve_settings_i18n_js(r):
    return _load_text_asset_response(SETTINGS_I18N_JS_FILE_PATH, "Settings i18n JavaScript asset", "application/javascript")

async def serve_settings_i18n_tr_js(r):
    return _load_text_asset_response(
        SETTINGS_I18N_TR_JS_FILE_PATH,
        "Settings i18n TR JavaScript asset",
        "application/javascript"
    )


async def serve_settings_i18n_en_js(r):
    return _load_text_asset_response(
        SETTINGS_I18N_EN_JS_FILE_PATH,
        "Settings i18n EN JavaScript asset",
        "application/javascript"
    )


async def serve_settings_theme_light_css(r):
    return _load_text_asset_response(
        SETTINGS_THEME_LIGHT_CSS_FILE_PATH,
        "Settings light CSS asset",
        "text/css"
    )


async def serve_settings_theme_dark_css(r):
    return _load_text_asset_response(
        SETTINGS_THEME_DARK_CSS_FILE_PATH,
        "Settings dark CSS asset",
        "text/css"
    )

async def command(r):
    result = await run_command(r.path, r)
    json_routes = (
        "/setvolume", "/mute", "/spotify", "/shorts", "/kill/spotify", "/kill/shorts",
        "/dnsredir", "/case_lights/on", "/case_lights/off", "/restart_app",
        "/shutdown", "/restart", "/sleep"
    )
    if r.path in json_routes:
        return web.Response(text=result if isinstance(result, str) else json.dumps(result), content_type="application/json")
    return web.Response(text=str(result))


async def settings_root(r):
    return _load_html_response(SETTINGS_HTML_FILE_PATH, "Settings HTML UI")


async def api_settings_get(r):
    try:
        data = load_settings() or {}
        include_monitors = str(r.query.get("include_monitors", "") or "").strip().lower() in {"1", "true", "yes"}
        if include_monitors:
            try:
                monitors = await asyncio.to_thread(win_utils.get_monitors, True)
                data["monitors"] = _normalize_monitor_payload(monitors)
            except Exception as mon_err:
                data["monitors"] = []
                data["monitors_error"] = str(mon_err)
        return web.json_response({"ok": True, "settings": data}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"Settings could not be read: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


async def api_settings_post(r):
    try:
        payload = await r.json()
        if not isinstance(payload, dict):
            raise ValueError("Invalid settings payload")
        saved = save_settings(payload) or {}
        refresh_runtime_settings_snapshot(True)
        try:
            monitors = await asyncio.to_thread(win_utils.get_monitors, True)
            saved["monitors"] = _normalize_monitor_payload(monitors)
        except Exception as mon_err:
            saved["monitors"] = []
            saved["monitors_error"] = str(mon_err)
        return web.json_response({"ok": True, "settings": saved}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"Settings could not be saved: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


async def api_settings_reset(r):
    try:
        saved = reset_settings() or {}
        refresh_runtime_settings_snapshot(True)
        try:
            monitors = await asyncio.to_thread(win_utils.get_monitors, True)
            saved["monitors"] = _normalize_monitor_payload(monitors)
        except Exception as mon_err:
            saved["monitors"] = []
            saved["monitors_error"] = str(mon_err)
        return web.json_response({"ok": True, "settings": saved}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"Settings could not be reset: {e}")
        return web.json_response({"ok": False, "error": str(e)}, status=500, headers=NO_CACHE_HEADERS)


def _normalize_monitor_payload(monitors):
    out = []
    for idx, mon in enumerate(monitors or []):
        if isinstance(mon, dict):
            item = dict(mon)
        else:
            item = {}
            for key in ("name", "device_name", "width", "height", "x", "y", "left", "top", "right", "bottom"):  
                if hasattr(mon, key):
                    item[key] = getattr(mon, key)
        item.setdefault("index", idx)
        if not item.get("name"):
            item["name"] = item.get("monitor_name") or item.get("adapter_name") or f"Monitor {idx}"
        if not item.get("device"):
            item["device"] = item.get("device_id") or item.get("device_name") or item.get("adapter_name") or item.get("name")
        width = item.get("width") or item.get("logical_width")
        height = item.get("height") or item.get("logical_height")
        label = item.get("label") or item.get("name") or item.get("device") or f"Monitor {idx}"
        if width and height:
            label = f"{label} - {width}x{height}"
        item["label"] = str(label)
        out.append(item)
    return out


async def api_monitors(r):
    try:
        monitors = await asyncio.to_thread(win_utils.get_monitors)
        return web.json_response({"ok": True, "monitors": _normalize_monitor_payload(monitors)}, headers=NO_CACHE_HEADERS)
    except Exception as e:
        log_error(f"Monitor list could not be retrieved: {e}")
        return web.json_response({"ok": False, "error": str(e), "monitors": []}, status=500, headers=NO_CACHE_HEADERS)



# ===== SmartThings climate proxy =====
def _get_smartthings_setting(path, default=""):
    value = _get_setting_str(f"api.smartthings.{path}", "").strip()
    return value or str(default or "")


def _get_smartthings_setting_float(path, default=0.0):
    try:
        return float(_get_smartthings_setting(path, default))
    except Exception:
        return float(default)


def _get_smartthings_config():
    base_url = _get_smartthings_setting("base_url", "https://api.smartthings.com/v1").rstrip("/")
    device_id = _get_smartthings_setting("device_id", "")
    access_token = _get_smartthings_setting("oauth_access_token", "") or _get_smartthings_setting("api_key", "")
    return {
        "base_url": base_url,
        "device_id": device_id,
        "access_token": access_token,
        "client_id": _get_smartthings_setting("oauth_client_id", ""),
        "client_secret": _get_smartthings_setting("oauth_client_secret", ""),
        "refresh_token": _get_smartthings_setting("oauth_refresh_token", ""),
        "expires_at": _get_smartthings_setting_float("oauth_access_token_expires_at", 0.0),
        "redirect_uri": _get_smartthings_setting("oauth_redirect_uri", ""),
    }


def _smartthings_has_refresh_credentials(config=None):
    cfg = config or _get_smartthings_config()
    return bool(cfg.get("client_id") and cfg.get("client_secret") and cfg.get("refresh_token"))


def _smartthings_token_expired_or_expiring(config=None, within_seconds=120.0):
    cfg = config or _get_smartthings_config()
    expires_at = float(cfg.get("expires_at") or 0.0)
    if expires_at <= 0:
        return not bool(cfg.get("access_token"))
    return time.time() >= max(0.0, expires_at - float(within_seconds))


def _persist_smartthings_oauth_tokens(access_token: str, refresh_token: str = "", expires_in: float | int | None = None):
    try:
        settings_data = load_settings(force_reload=True)
        api_cfg = settings_data.setdefault("api", {})
        if not isinstance(api_cfg, dict):
            api_cfg = {}
            settings_data["api"] = api_cfg
        st_cfg = api_cfg.setdefault("smartthings", {})
        if not isinstance(st_cfg, dict):
            st_cfg = {}
            api_cfg["smartthings"] = st_cfg

        st_cfg["api_key"] = str(access_token or "")
        st_cfg["oauth_access_token"] = str(access_token or "")
        if refresh_token:
            st_cfg["oauth_refresh_token"] = str(refresh_token)
        if expires_in is not None:
            st_cfg["oauth_access_token_expires_at"] = int(time.time() + max(0, int(float(expires_in))))
        save_settings(settings_data)
        refresh_runtime_settings_snapshot(True)
    except Exception as exc:
        log_error(f"SmartThings token save error: {exc}")


def _clear_smartthings_oauth_cache(reason: str = ""):
    try:
        settings_data = load_settings(force_reload=True)
        api_cfg = settings_data.setdefault("api", {})
        if not isinstance(api_cfg, dict):
            api_cfg = {}
            settings_data["api"] = api_cfg
        st_cfg = api_cfg.setdefault("smartthings", {})
        if not isinstance(st_cfg, dict):
            st_cfg = {}
            api_cfg["smartthings"] = st_cfg

        st_cfg["oauth_access_token"] = ""
        st_cfg["oauth_access_token_expires_at"] = 0
        save_settings(settings_data)
        refresh_runtime_settings_snapshot(True)
        if reason:
            log_error(f"SmartThings OAuth cache cleared: {reason}")
    except Exception as exc:
        log_error(f"SmartThings OAuth cache clear error: {exc}")


def _smartthings_refresh_token_invalid(data) -> bool:
    if not isinstance(data, dict):
        return False
    error = str(data.get("error") or "").strip().lower()
    description = str(data.get("error_description") or "").strip().lower()
    return error == "invalid_grant" or "invalid refresh token" in description


async def _smartthings_exchange_authorization_code(code: str, redirect_uri: str = ""):
    config = _get_smartthings_config()
    code = str(code or "").strip()
    redirect_uri = str(redirect_uri or config.get("redirect_uri") or "").strip()
    if not code:
        return {"ok": False, "error": "SmartThings authorization code is missing"}
    if not config.get("client_id") or not config.get("client_secret") or not redirect_uri:
        return {"ok": False, "error": "SmartThings OAuth client or redirect URI is missing"}

    token_url = "https://api.smartthings.com/oauth/token"
    form = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": config.get("client_id") or "",
        "code": code,
        "redirect_uri": redirect_uri,
    })
    raw_basic = f"{config.get('client_id') or ''}:{config.get('client_secret') or ''}".encode("utf-8")
    basic_token = base64.b64encode(raw_basic).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        session = _get_shared_http_session("smartthings")
        async with session.post(token_url, headers=headers, data=form, timeout=timeout) as resp:
            text = await resp.text()
            try:
                data = json.loads(text) if text else {}
            except Exception:
                data = {"raw": text[:500]}
            if resp.status < 200 or resp.status >= 300:
                return {"ok": False, "error": f"SmartThings authorization code exchange HTTP {resp.status}", "http_status": resp.status, "response": data}
            access_token = str((data or {}).get("access_token") or "").strip()
            refresh_token = str((data or {}).get("refresh_token") or "").strip()
            expires_in = (data or {}).get("expires_in")
            if not access_token or not refresh_token:
                return {"ok": False, "error": "SmartThings authorization response is missing token fields", "response": data}
            _persist_smartthings_oauth_tokens(access_token, refresh_token=refresh_token, expires_in=expires_in) 
            return {"ok": True, "expires_in": expires_in}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "http_status": None}


def _extract_smartthings_main_status(data):
    try:
        main = (((data or {}).get("components") or {}).get("main") or {})
    except Exception:
        main = {}
    try:
        level = (((main.get("switchLevel") or {}).get("level") or {}).get("value"))
    except Exception:
        level = None
    try:
        power = (((main.get("switch") or {}).get("switch") or {}).get("value"))
    except Exception:
        power = None
    return level, power


async def _smartthings_refresh_access_token(force=False):
    config = _get_smartthings_config()
    if not _smartthings_has_refresh_credentials(config):
        return {"ok": False, "error": "SmartThings OAuth refresh settings are incomplete"}
    if (not force) and config.get("access_token") and (not _smartthings_token_expired_or_expiring(config)):     
        return {"ok": True, "access_token": config.get("access_token"), "refresh_token": config.get("refresh_token")}

    token_url = "https://api.smartthings.com/oauth/token"
    form = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "client_id": config.get("client_id") or "",
        "refresh_token": config.get("refresh_token") or "",
    })
    raw_basic = f"{config.get('client_id') or ''}:{config.get('client_secret') or ''}".encode("utf-8")
    basic_token = base64.b64encode(raw_basic).decode("ascii")
    headers = {
        "Authorization": f"Basic {basic_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    try:
        timeout = aiohttp.ClientTimeout(total=12)
        session = _get_shared_http_session("smartthings")
        async with session.post(token_url, headers=headers, data=form, timeout=timeout) as resp:
            text = await resp.text()
            try:
                data = json.loads(text) if text else {}
            except Exception:
                data = {"raw": text[:500]}
            if resp.status < 200 or resp.status >= 300:
                if _smartthings_refresh_token_invalid(data):
                    _clear_smartthings_oauth_cache("refresh token invalid_grant")
                    return {
                        "ok": False,
                        "error": "SmartThings refresh token is invalid. Re-authorize SmartThings in settings.", 
                        "http_status": resp.status,
                        "response": data,
                        "reauthorize_required": True,
                    }
                return {"ok": False, "error": f"SmartThings token refresh HTTP {resp.status}", "http_status": resp.status, "response": data}
            access_token = str((data or {}).get("access_token") or "").strip()
            refresh_token = str((data or {}).get("refresh_token") or config.get("refresh_token") or "").strip() 
            expires_in = (data or {}).get("expires_in")
            if not access_token:
                return {"ok": False, "error": "SmartThings token refresh response is missing access_token", "response": data}
            _persist_smartthings_oauth_tokens(access_token, refresh_token=refresh_token, expires_in=expires_in) 
            return {
                "ok": True,
                "access_token": access_token,
                "refresh_token": refresh_token,
                "expires_in": expires_in,
                "response": data,
            }
    except Exception as exc:
        return {"ok": False, "error": str(exc), "http_status": None}


async def _smartthings_send_request(method, url, token, payload=None):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    timeout = aiohttp.ClientTimeout(total=8)
    session = _get_shared_http_session("smartthings")
    async with session.request(method, url, headers=headers, json=payload, timeout=timeout) as resp:
        text = await resp.text()
        try:
            data = json.loads(text) if text else None
        except Exception:
            data = {"raw": text[:500]}
        return resp.status, data


async def _smartthings_request(method, suffix, payload=None):
    config = _get_smartthings_config()
    if not config.get("device_id"):
        return {"ok": False, "error": "SmartThings settings are incomplete", "level": None, "power": None, "http_status": None}
    if _smartthings_has_refresh_credentials(config) and _smartthings_token_expired_or_expiring(config):
        refresh_result = await _smartthings_refresh_access_token(force=False)
        if refresh_result.get("ok"):
            config["access_token"] = refresh_result.get("access_token") or config.get("access_token")
        elif not config.get("access_token"):
            return {
                "ok": False,
                "error": refresh_result.get("error") or "SmartThings token refresh failed",
                "http_status": refresh_result.get("http_status"),
                "response": refresh_result.get("response"),
                "reauthorize_required": bool(refresh_result.get("reauthorize_required")),
            }
    if not config.get("access_token"):
        return {"ok": False, "error": "SmartThings access token is missing", "http_status": None}

    url = f"{config.get('base_url')}/devices/{urllib.parse.quote(config.get('device_id') or '', safe='')}/{suffix.lstrip('/')}"
    try:
        status_code, data = await _smartthings_send_request(method, url, config.get("access_token"), payload=payload)
        if status_code == 401 and _smartthings_has_refresh_credentials(config):
            refresh_result = await _smartthings_refresh_access_token(force=True)
            if refresh_result.get("ok"):
                status_code, data = await _smartthings_send_request(method, url, refresh_result.get("access_token"), payload=payload)
            else:
                return {
                    "ok": False,
                    "error": refresh_result.get("error") or "SmartThings token refresh failed",
                    "http_status": refresh_result.get("http_status"),
                    "response": refresh_result.get("response"),
                    "reauthorize_required": bool(refresh_result.get("reauthorize_required")),
                }
        if status_code < 200 or status_code >= 300:
            return {"ok": False, "error": f"SmartThings HTTP {status_code}", "http_status": status_code, "response": data}
        return {"ok": True, "http_status": status_code, "response": data}
    except Exception as e:
        return {"ok": False, "error": str(e), "http_status": None}


async def smartthings_climate_status(_request):
    result = await _smartthings_request("GET", "status")
    if not result.get("ok"):
        return web.json_response(result, status=502, headers=NO_CACHE_HEADERS)
    level, power = _extract_smartthings_main_status(result.get("response"))
    return web.json_response({"ok": True, "level": level, "power": power}, headers=NO_CACHE_HEADERS)


async def smartthings_climate_level(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    try:
        level = int(float((body or {}).get("level")))
    except Exception:
        return web.json_response({"ok": False, "error": "Invalid level"}, status=400, headers=NO_CACHE_HEADERS) 
    level = max(0, min(100, level))
    payload = {"commands": [{"component": "main", "capability": "switchLevel", "command": "setLevel", "arguments": [level]}]}
    result = await _smartthings_request("POST", "commands", payload)
    if not result.get("ok"):
        return web.json_response(result, status=502, headers=NO_CACHE_HEADERS)
    return web.json_response({"ok": True, "level": level}, headers=NO_CACHE_HEADERS)


async def smartthings_climate_power(request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    command = str((body or {}).get("command") or "").strip().lower()
    if command not in {"on", "off"}:
        return web.json_response({"ok": False, "error": "Invalid power command"}, status=400, headers=NO_CACHE_HEADERS)
    payload = {"commands": [{"component": "main", "capability": "switch", "command": command, "arguments": []}]}
    result = await _smartthings_request("POST", "commands", payload)
    if not result.get("ok"):
        return web.json_response(result, status=502, headers=NO_CACHE_HEADERS)
    return web.json_response({"ok": True, "power": command}, headers=NO_CACHE_HEADERS)


async def smartthings_oauth_callback(request):
    code = (request.query.get("code") or "").strip()
    error = (request.query.get("error") or "").strip()
    if error:
        desc = (request.query.get("error_description") or "").strip()
        body = f"<html><body><h3>SmartThings authorization failed</h3><p>{html.escape(error)} {html.escape(desc)}</p></body></html>"
        return web.Response(text=body, content_type="text/html", status=400)
    result = await _smartthings_exchange_authorization_code(code)
    if not result.get("ok"):
        body = f"<html><body><h3>SmartThings token exchange failed</h3><p>{html.escape(str(result.get('error') or 'Unknown error'))}</p></body></html>"
        return web.Response(text=body, content_type="text/html", status=502)
    return web.Response(
        text="<html><body><h3>SmartThings authorization complete</h3><p>Tokens saved. You can close this tab.</p></body></html>",
        content_type="text/html",
    )

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.     
__all__ = [name for name in globals() if not name.startswith("__")]
