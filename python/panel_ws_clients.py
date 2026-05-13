# File Version: 1.0
import asyncio
import threading
from panel_globals import (
    WS_CLIENTS_LOCK, WS_CLIENTS
)
from panel_logging import log_ws_debug

WS_BROADCAST_SEMAPHORE = asyncio.Semaphore(10)
def register_ws_client(ws):
    with WS_CLIENTS_LOCK:
        WS_CLIENTS.add(ws)
        count = len(WS_CLIENTS)
    log_ws_debug(f"client kaydoldu, aktif={count}")


def unregister_ws_client(ws):
    with WS_CLIENTS_LOCK:
        WS_CLIENTS.discard(ws)
        count = len(WS_CLIENTS)
    log_ws_debug(f"client ayrildi, aktif={count}")


def get_ws_clients_snapshot():
    with WS_CLIENTS_LOCK:
        return list(WS_CLIENTS)


async def _safe_ws_send_json(ws, payload):
    try:
        async with WS_BROADCAST_SEMAPHORE:
            await asyncio.wait_for(ws.send_json(payload), timeout=1.5)
        return True
    except Exception as exc:
        msg_type = "?"
        try:
            msg_type = str((payload or {}).get("type") or "?")
        except Exception:
            pass
        log_ws_debug(f"send failed type={msg_type}: {exc}")
        return False

# Export underscore helpers too, because the split modules intentionally share legacy private helper names.
__all__ = [name for name in globals() if not name.startswith("__")]
