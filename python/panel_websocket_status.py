import time
import json
import asyncio
import aiohttp
from aiohttp import web

from panel_bootstrap import _get_performance_interval_seconds
from panel_logging import log_ws_debug, log_perf
from panel_state import _wait_system_cache_event_async, get_mute_ws_burst_until
from panel_ws_clients import register_ws_client, unregister_ws_client, _safe_ws_send_json
from panel_system import get_cached_system_info
from panel_ws_logs_routes import _handle_ws_command_message

def _build_status_delta(previous_payload, current_payload):
    if not isinstance(previous_payload, dict):
        return dict(current_payload or {})
    delta = {}
    for key, value in (current_payload or {}).items():
        if previous_payload.get(key) != value:
            delta[key] = value
    return delta


async def websocket_status_sender(ws):
    last_payload = None
    last_sent_lyrics = None
    try:
        while not ws.closed:
            loop_started = time.perf_counter()
            payload = get_cached_system_info()
            outgoing_type = "status"

            # Performans / bantgenisligi:
            # `lyrics` alani buyuk olabildigi icin surekli gondermiyoruz.
            # Degismediyse frontend tarafinda mevcut lyrics'i koruyacagiz.
            lyrics = payload.get("lyrics", None)
            delta_payload = _build_status_delta(last_payload, payload)
            if lyrics is not None and lyrics == last_sent_lyrics:
                delta_payload.pop("lyrics", None)
            else:
                last_sent_lyrics = lyrics

            if last_payload is None:
                outgoing_type = "full_status"
                delta_payload = dict(payload)

            if delta_payload:
                send_started = time.perf_counter()
                ok = await _safe_ws_send_json(ws, {"type": outgoing_type, "payload": delta_payload})
                if not ok:
                    break
                send_elapsed_ms = (time.perf_counter() - send_started) * 1000.0
                log_ws_debug(f"sent type={outgoing_type} keys={len(delta_payload)}")
                if send_elapsed_ms >= 120.0:
                    log_perf(f"ws_send type={outgoing_type} keys={len(delta_payload)} elapsed_ms={send_elapsed_ms:.1f}")
                last_payload = dict(payload)

            # Yayin hizi ayari performance.websocket_broadcast_interval_ms ustunden yonetilir.
            now = time.time()
            ws_interval = _get_performance_interval_seconds("websocket_broadcast_interval_ms", 250, 50)
            loop_elapsed_ms = (time.perf_counter() - loop_started) * 1000.0
            if loop_elapsed_ms >= 200.0:
                log_perf(f"ws_loop keys={len(delta_payload)} elapsed_ms={loop_elapsed_ms:.1f}")
            if now < get_mute_ws_burst_until():
                wait_timeout = min(0.3, ws_interval)
            else:
                wait_timeout = ws_interval if payload.get("media_is_playing") else (ws_interval * 2.0)
            await _wait_system_cache_event_async(wait_timeout)
    except Exception as exc:
        log_ws_debug(f"sender sonlandi: {exc}")


async def websocket_status(r):
    ws = web.WebSocketResponse(heartbeat=25.0, autoping=True)
    await ws.prepare(r)
    register_ws_client(ws)

    sender_task = asyncio.create_task(websocket_status_sender(ws))
    try:
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                raw_text = (msg.data or "").strip()
                lowered = raw_text.lower()
                log_ws_debug(f"mesaj alindi: {lowered[:80] if lowered else '<bos>'}")
                if lowered == "refresh":
                    await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})       
                    continue
                try:
                    incoming = json.loads(raw_text)
                except Exception:
                    incoming = None
                if isinstance(incoming, dict):
                    if incoming.get("type") == "refresh":
                        await _safe_ws_send_json(ws, {"type": "status", "payload": get_cached_system_info()})   
                    elif incoming.get("type") == "command":
                        await _handle_ws_command_message(ws, incoming)
            elif msg.type == aiohttp.WSMsgType.ERROR:
                log_ws_debug("ws error frame alindi")
                break
    finally:
        unregister_ws_client(ws)
        sender_task.cancel()
        try:
            await sender_task
        except Exception:
            pass

    return ws

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.     
__all__ = [name for name in globals() if not name.startswith("__")]
