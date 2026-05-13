# File Version: 1.0
import os
import traceback

try:
    from panel_hwinfo_snapshot import run_hwinfo_worker_mode

    if __name__ == "__main__":
        run_hwinfo_worker_mode()
except Exception:
    try:
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        with open(os.path.join(log_dir, "errors.txt"), "a", encoding="utf-8") as f:
            f.write("\n[HWINFO] Worker fatal error:\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass
    raise
