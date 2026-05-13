# File Version: 1.0
# Main orchestrator: imports topic modules and starts the app.

import importlib
import sys

MODULE_NAMES = (
    "panel_bootstrap",
    "panel_state",
    "panel_runtime_helpers",
    "panel_logging",
    "panel_runtime_globals",
    "panel_tuya",
    "panel_ws_clients",
    "panel_hwinfo_process",
    "panel_hwinfo_snapshot",
    "panel_loops_shift_status",
    "panel_audio_controls",
    "panel_hwinfo_reader",
    "panel_media",
    "panel_weather",
    "panel_network",
    "panel_system",
    "panel_commands",
    "panel_assets",
    "panel_websocket_status",
    "panel_ws_logs_routes",
    "panel_settings_smartthings",
    "panel_misc_actions",
    "panel_routes_window_main",
    "panelmkapa",
)


def _bootstrap_modules():
    modules = []
    for name in MODULE_NAMES:
        try:
            mod = importlib.import_module(name)
            modules.append(mod)
        except Exception as e:
            print(f"Failed to import {name}: {e}")

    # Simple route registration hook
    for module in modules:
        hook = getattr(module, "register_routes", None)
        if callable(hook):
            hook()
        hook2 = getattr(module, "register_monitor_routes", None)
        if callable(hook2):
            hook2()
    return modules


_modules = _bootstrap_modules()

if __name__ == "__main__":
    from panel_bootstrap import restore_default_process_scheduling
    from panel_hwinfo_snapshot import run_hwinfo_worker_mode
    from panel_routes_window_main import main
    from panel_logging import log, log_error

    restore_default_process_scheduling(include_children=False)
    try:
        if "--hwinfo-worker" in sys.argv:
            run_hwinfo_worker_mode()
        else:
            log("Panel main process started")
            main()
    except Exception as e:
        try:
            log_error(f"Panel main process error: {type(e).__name__}: {e}")
        finally:
            from panel_bootstrap import _write_fallback_startup_error
            _write_fallback_startup_error(e)
        raise
