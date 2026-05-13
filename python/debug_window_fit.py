# File Version: 1.0
import time
import win_utils

mons = win_utils.get_monitors(force_refresh=True)
print("MONITORS:")
for i,m in enumerate(mons):
    print(i, m.get("adapter_name"), m.get("monitor_name"), "phys", m.get("left"), m.get("top"), m.get("width"), m.get("height"), "logical", m.get("logical_left"), m.get("logical_top"), m.get("logical_width"), m.get("logical_height"), "scale", m.get("scale"), "primary", m.get("primary"))
