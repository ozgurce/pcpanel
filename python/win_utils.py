# File Version: 1.0

import ctypes
from ctypes import wintypes
import os
import threading
import time

user32 = ctypes.windll.user32
shell32 = ctypes.windll.shell32
shcore = getattr(ctypes.windll, 'shcore', None)
dwmapi = getattr(ctypes.windll, 'dwmapi', None)

SW_RESTORE = 9
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
SWP_FRAMECHANGED = 0x0020
SWP_NOOWNERZORDER = 0x0200
HWND_TOPMOST = -1
GWL_EXSTYLE = -20
WS_EX_APPWINDOW = 0x00040000
WS_EX_TOOLWINDOW = 0x00000080
CCHDEVICENAME = 32
EDD_GET_DEVICE_INTERFACE_NAME = 0x00000001

if ctypes.sizeof(ctypes.c_void_p) == 8:
    GetWindowLongPtr = user32.GetWindowLongPtrW
    SetWindowLongPtr = user32.SetWindowLongPtrW
else:
    GetWindowLongPtr = user32.GetWindowLongW
    SetWindowLongPtr = user32.SetWindowLongW

try:
    user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
except Exception:
    try:
        user32.SetProcessDPIAware()
    except Exception:
        pass


class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long), ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wintypes.DWORD)]


class MONITORINFOEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wintypes.DWORD),
        ("rcMonitor", RECT),
        ("rcWork", RECT),
        ("dwFlags", wintypes.DWORD),
        ("szDevice", wintypes.WCHAR * CCHDEVICENAME),
    ]


class DISPLAY_DEVICEW(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("DeviceName", wintypes.WCHAR * 32),
        ("DeviceString", wintypes.WCHAR * 128),
        ("StateFlags", wintypes.DWORD),
        ("DeviceID", wintypes.WCHAR * 128),
        ("DeviceKey", wintypes.WCHAR * 128),
    ]


_MONITOR_CACHE_LOCK = threading.Lock()
_MONITOR_CACHE = {"expires_at": 0.0, "monitors": []}


def get_monitors(force_refresh: bool = False, cache_ttl_seconds: float = 10.0):
    now = time.time()
    with _MONITOR_CACHE_LOCK:
        if not force_refresh and _MONITOR_CACHE["monitors"] and now < _MONITOR_CACHE["expires_at"]:
            return [dict(x) for x in _MONITOR_CACHE["monitors"]]

    monitors = []
    cb_type = ctypes.WINFUNCTYPE(ctypes.c_int, wintypes.HMONITOR, wintypes.HDC, ctypes.POINTER(RECT), wintypes.LPARAM)

    def _cb(hmon, hdc, lprc, data):
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        user32.GetMonitorInfoW(hmon, ctypes.byref(info))

        dpi_x = ctypes.c_uint(96)
        dpi_y = ctypes.c_uint(96)
        try:
            if shcore:
                shcore.GetDpiForMonitor(hmon, 0, ctypes.byref(dpi_x), ctypes.byref(dpi_y))
        except Exception:
            pass

        scale = max(1.0, float(dpi_x.value) / 96.0)
        left = int(info.rcMonitor.left)
        top = int(info.rcMonitor.top)
        width = int(info.rcMonitor.right - info.rcMonitor.left)
        height = int(info.rcMonitor.bottom - info.rcMonitor.top)

        mi_ex = MONITORINFOEXW()
        mi_ex.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hmon, ctypes.byref(mi_ex))
        adapter_name = mi_ex.szDevice

        mon = DISPLAY_DEVICEW()
        mon.cb = ctypes.sizeof(DISPLAY_DEVICEW)
        ok = user32.EnumDisplayDevicesW(adapter_name, 0, ctypes.byref(mon), EDD_GET_DEVICE_INTERFACE_NAME)

        monitors.append({
            "handle": hmon,
            "adapter_name": adapter_name,
            "device_id": mon.DeviceID if ok else "",
            "device_key": mon.DeviceKey if ok else "",
            "monitor_name": mon.DeviceString if ok else "",
            "left": left,
            "top": top,
            "width": width,
            "height": height,
            "logical_left": int(round(left / scale)),
            "logical_top": int(round(top / scale)),
            "logical_width": max(1, int(round(width / scale))),
            "logical_height": max(1, int(round(height / scale))),
            "scale": scale,
            "primary": bool(info.dwFlags & 1),
        })
        return 1

    user32.EnumDisplayMonitors(None, None, cb_type(_cb), 0)
    with _MONITOR_CACHE_LOCK:
        _MONITOR_CACHE["monitors"] = [dict(x) for x in monitors]
        _MONITOR_CACHE["expires_at"] = now + max(1.0, float(cache_ttl_seconds))
    return monitors


def pick_monitor(monitors, match_text):
    q = (match_text or "").strip().lower()
    if not monitors:
        raise RuntimeError("Hedef monitor bulunamadi")
    if not q:
        for m in monitors:
            if m.get("primary"):
                return m
        return monitors[0]
    for m in monitors:
        hay = " | ".join([m.get("device_id", ""), m.get("device_key", ""), m.get("monitor_name", ""), m.get("adapter_name", "")]).lower()
        if q in hay:
            return m
    raise RuntimeError(f"Hedef monitor bulunamadi: {match_text}")


def print_monitor_summary(mon):
    print("Secilen monitor:")
    print(f'  device_id      : {mon["device_id"]}')
    print(f'  left/top       : {mon["left"]}, {mon["top"]}')
    print(f'  width/height   : {mon["width"]} x {mon["height"]}')
    print(f'  logical        : {mon["logical_left"]}, {mon["logical_top"]}, {mon["logical_width"]}, {mon["logical_height"]}')
    print(f'  scale          : {mon["scale"]}')
    print("")


def find_window_by_title(title, timeout=10, process_id=None):
    target = (title or "").strip().lower()
    deadline = time.time() + timeout
    enum_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    # Not: EnumWindows.argtypes burada bilincli olarak ayarlanmiyor.
    # PyGetWindow da kendi WINFUNCTYPE callback tipini uretiyor; burada
    # argtypes'i farkli bir callback sinifina sabitlemek
    # 'expected WinFunctionType instance instead of WinFunctionType'
    # hatasina yol acabiliyor.
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    pid_filter = int(process_id) if process_id is not None else None

    while time.time() < deadline:
        found = []

        def _enum(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if pid_filter is not None:
                pid = wintypes.DWORD(0)
                try:
                    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                    if int(pid.value) != pid_filter:
                        return True
                except Exception:
                    return True
            ln = user32.GetWindowTextLengthW(hwnd)
            if ln <= 0:
                return True
            buf = ctypes.create_unicode_buffer(ln + 1)
            user32.GetWindowTextW(hwnd, buf, len(buf))
            txt = buf.value.strip()
            if txt and target in txt.lower():
                found.append(hwnd)
            return True

        user32.EnumWindows(enum_type(_enum), 0)
        if found:
            return found[0]
        time.sleep(0.2)
    return None


def hide_from_taskbar(hwnd):
    try:
        exstyle = GetWindowLongPtr(hwnd, GWL_EXSTYLE)
        exstyle = (exstyle | WS_EX_TOOLWINDOW) & ~WS_EX_APPWINDOW
        SetWindowLongPtr(hwnd, GWL_EXSTYLE, exstyle)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE | SWP_FRAMECHANGED)
    except Exception:
        pass


def disable_window_shadow(hwnd):
    if not dwmapi:
        return
    try:
        DWMWA_NCRENDERING_POLICY = 2
        DWMNCRP_DISABLED = 1
        policy = ctypes.c_int(DWMNCRP_DISABLED)
        dwmapi.DwmSetWindowAttribute(hwnd, DWMWA_NCRENDERING_POLICY, ctypes.byref(policy), ctypes.sizeof(policy))
    except Exception:
        pass


def set_window_rect_to_monitor(hwnd, mon, horizontal_bleed=0, bottom_inset=0, left_offset=0, top_offset=0):
    # Fiziksel monitor rect'ini kullan. DPI kaynakli kayma/kuculme burada duzeltilir.
    x = int(mon.get("left", 0) - horizontal_bleed + left_offset)
    y = int(mon.get("top", 0) + top_offset)
    w = int(mon.get("width", mon.get("logical_width", 1280)) + (horizontal_bleed * 2))
    h = max(1, int(mon.get("height", mon.get("logical_height", 800)) - bottom_inset))
    try:
        user32.ShowWindow(hwnd, SW_RESTORE)
    except Exception:
        pass
    user32.SetWindowPos(
        hwnd, wintypes.HWND(HWND_TOPMOST), x, y, w, h,
        SWP_SHOWWINDOW | SWP_FRAMECHANGED | SWP_NOOWNERZORDER
    )


def force_window_to_monitor(hwnd, mon, horizontal_bleed=0, bottom_inset=0, hide_taskbar=True, disable_shadow=True):
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, SW_RESTORE)
        time.sleep(0.05)
    if hide_taskbar:
        hide_from_taskbar(hwnd)
    if disable_shadow:
        disable_window_shadow(hwnd)
    set_window_rect_to_monitor(hwnd, mon, horizontal_bleed=horizontal_bleed, bottom_inset=bottom_inset)


def keep_window_alive(
    hwnd,
    mon,
    horizontal_bleed=0,
    bottom_inset=0,
    interval_seconds=2.0,
    on_loop=None,
    disable_shadow=True,
    should_reposition=None,
):
    user32.IsWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.restype = wintypes.BOOL
    while True:
        try:
            if not user32.IsWindow(hwnd):
                os._exit(0)
                return
            reposition_allowed = True
            if should_reposition is not None:
                reposition_allowed = bool(should_reposition(hwnd, mon))
            if reposition_allowed:
                hide_from_taskbar(hwnd)
                if disable_shadow:
                    disable_window_shadow(hwnd)
                set_window_rect_to_monitor(hwnd, mon, horizontal_bleed=horizontal_bleed, bottom_inset=bottom_inset)
            if on_loop is not None:
                on_loop(hwnd, mon)
        except Exception:
            pass
        time.sleep(max(0.25, float(interval_seconds)))
