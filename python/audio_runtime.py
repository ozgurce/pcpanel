# File Version: 1.0

import ctypes
import queue
import threading
import uuid

WM_APPCOMMAND = 0x319
APPCOMMAND_VOLUME_MUTE = 0x80000
APPCOMMAND_VOLUME_DOWN = 0x90000
APPCOMMAND_VOLUME_UP = 0xA0000
APPCOMMAND_MEDIA_NEXTTRACK = 0xB0000
APPCOMMAND_MEDIA_PREVIOUSTRACK = 0xC0000
APPCOMMAND_MEDIA_PLAY_PAUSE = 0xE0000

CLSCTX_ALL = 23
E_RENDER = 0
E_MULTIMEDIA = 1
COINIT_MULTITHREADED = 0x0
RPC_E_CHANGED_MODE = 0x80010106
S_OK = 0
S_FALSE = 1

user32 = ctypes.windll.user32
ole32 = ctypes.OleDLL("ole32")
ole32.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
ole32.CoInitializeEx.restype = ctypes.c_long
ole32.CoUninitialize.argtypes = []
ole32.CoUninitialize.restype = None


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

    def __init__(self, guid_string: str):
        super().__init__()
        u = uuid.UUID(guid_string)
        self.Data1 = u.time_low
        self.Data2 = u.time_mid
        self.Data3 = u.time_hi_version
        self.Data4[:] = u.bytes[8:]


CLSID_MMDeviceEnumerator = GUID("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioEndpointVolume = GUID("5CDF2C82-841E-4546-9722-0CF74078229A")


class AudioEndpointController:
    def __init__(self, logger=None):
        self._logger = logger or (lambda msg: None)
        self._ops = queue.Queue()
        self._closed = threading.Event()
        self._thread = threading.Thread(target=self._worker, daemon=True, name="audio-endpoint-thread")
        self._thread.start()

    def _check_hr(self, hr, where="COM"):
        if hr != 0:
            raise OSError(f"{where} HRESULT=0x{ctypes.c_uint32(hr).value:08X}")

    def _vtbl_call(self, ptr, index, restype, argtypes, *args):
        vtbl = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        fn = ctypes.WINFUNCTYPE(restype, *argtypes)(vtbl[index])
        return fn(ptr, *args)

    def _release_com(self, ptr):
        try:
            if ptr:
                self._vtbl_call(ptr, 2, ctypes.c_ulong, [ctypes.c_void_p])
        except Exception:
            pass

    def _com_init_for_audio(self):
        hr = int(ole32.CoInitializeEx(None, COINIT_MULTITHREADED)) & 0xFFFFFFFF
        if hr in (S_OK, S_FALSE):
            return True
        if hr == RPC_E_CHANGED_MODE:
            self._logger("Audio COM farkli apartment mode ile zaten baslatilmis; CoUninitialize yapmadan devam ediliyor.")
            return False
        raise OSError(f"CoInitializeEx HRESULT=0x{hr:08X}")

    def _acquire_endpoint(self):
        enumerator = ctypes.c_void_p()
        device = ctypes.c_void_p()
        endpoint = ctypes.c_void_p()
        try:
            hr = ole32.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(enumerator))
            self._check_hr(hr, "CoCreateInstance")
            hr = self._vtbl_call(enumerator, 4, ctypes.c_long, [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p)], E_RENDER, E_MULTIMEDIA, ctypes.byref(device))
            self._check_hr(hr, "IMMDeviceEnumerator.GetDefaultAudioEndpoint")
            hr = self._vtbl_call(device, 3, ctypes.c_long, [ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.c_ulong, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)], ctypes.byref(IID_IAudioEndpointVolume), CLSCTX_ALL, None, ctypes.byref(endpoint))
            self._check_hr(hr, "IMMDevice.Activate")
            return enumerator, device, endpoint
        except Exception:
            self._release_com(endpoint)
            self._release_com(device)
            self._release_com(enumerator)
            raise

    def _worker(self):
        initialized = False
        enumerator = device = endpoint = None
        try:
            try:
                initialized = self._com_init_for_audio()
            except Exception as exc:
                self._logger(f"Audio COM baslatilamadi: {exc}")
            while True:
                func, args, reply_q = self._ops.get()
                try:
                    if func == "stop":
                        reply_q.put(None)
                        return
                    if not endpoint:
                        enumerator, device, endpoint = self._acquire_endpoint()
                    if func == "get_volume":
                        scalar = ctypes.c_float()
                        self._check_hr(self._vtbl_call(endpoint, 9, ctypes.c_long, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)], ctypes.byref(scalar)), "IAudioEndpointVolume.GetMasterVolumeLevelScalar")
                        reply_q.put(max(0, min(100, int(round(max(0.0, min(1.0, scalar.value)) * 100.0)))))
                    elif func == "set_volume":
                        target = max(0, min(100, int(round(float(args[0])))))
                        scalar = ctypes.c_float(target / 100.0)
                        self._check_hr(self._vtbl_call(endpoint, 7, ctypes.c_long, [ctypes.c_void_p, ctypes.c_float, ctypes.c_void_p], scalar, None), "IAudioEndpointVolume.SetMasterVolumeLevelScalar")
                        scalar2 = ctypes.c_float()
                        self._check_hr(self._vtbl_call(endpoint, 9, ctypes.c_long, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float)], ctypes.byref(scalar2)), "IAudioEndpointVolume.GetMasterVolumeLevelScalar")
                        reply_q.put(max(0, min(100, int(round(max(0.0, min(1.0, scalar2.value)) * 100.0)))))
                    elif func == "get_mute":
                        muted = ctypes.c_int()
                        self._check_hr(self._vtbl_call(endpoint, 15, ctypes.c_long, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)], ctypes.byref(muted)), "IAudioEndpointVolume.GetMute")
                        reply_q.put(bool(muted.value))
                    elif func == "set_mute":
                        self._check_hr(self._vtbl_call(endpoint, 14, ctypes.c_long, [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p], 1 if args[0] else 0, None), "IAudioEndpointVolume.SetMute")
                        reply_q.put(True)
                    elif func == "toggle_mute":
                        muted = ctypes.c_int()
                        self._check_hr(self._vtbl_call(endpoint, 15, ctypes.c_long, [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int)], ctypes.byref(muted)), "IAudioEndpointVolume.GetMute")
                        new_value = not bool(muted.value)
                        self._check_hr(self._vtbl_call(endpoint, 14, ctypes.c_long, [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p], 1 if new_value else 0, None), "IAudioEndpointVolume.SetMute")
                        reply_q.put(True)
                    else:
                        raise RuntimeError(f"Bilinmeyen audio op: {func}")
                except Exception as exc:
                    self._logger(f"Audio runtime hatasi ({func}): {exc}")
                    self._release_com(endpoint)
                    self._release_com(device)
                    self._release_com(enumerator)
                    enumerator = device = endpoint = None
                    try:
                        enumerator, device, endpoint = self._acquire_endpoint()
                    except Exception as reacquire_exc:
                        self._logger(f"Audio endpoint yeniden acilamadi: {reacquire_exc}")
                    reply_q.put(exc)
        finally:
            self._release_com(endpoint)
            self._release_com(device)
            self._release_com(enumerator)
            if initialized:
                try:
                    ole32.CoUninitialize()
                except Exception:
                    pass

    def _call(self, func, *args, timeout=3.0):
        if self._closed.is_set():
            return None if func != "set_mute" else False
        reply_q = queue.Queue(maxsize=1)
        self._ops.put((func, args, reply_q))
        try:
            result = reply_q.get(timeout=timeout)
        except queue.Empty:
            self._logger(f"Audio runtime zaman asimi ({func})")
            return None if func != "set_mute" else False
        if isinstance(result, Exception):
            return None if func != "set_mute" else False
        return result

    def close(self, timeout=1.0):
        if self._closed.is_set():
            return
        reply_q = queue.Queue(maxsize=1)
        try:
            self._ops.put(("stop", (), reply_q))
            reply_q.get(timeout=max(0.1, float(timeout or 0.1)))
        except Exception:
            pass
        finally:
            self._closed.set()
            if threading.current_thread() is not self._thread:
                try:
                    self._thread.join(timeout=max(0.1, float(timeout or 0.1)))
                except Exception:
                    pass

    def get_volume_percent(self):
        return self._call("get_volume")

    def set_volume_percent(self, target):
        return self._call("set_volume", target)

    def get_mute_state(self):
        return self._call("get_mute")

    def set_mute(self, mute_on: bool):
        result = self._call("set_mute", bool(mute_on))
        return bool(result)

    def toggle_mute(self):
        result = self._call("toggle_mute")
        return bool(result)


def send_app_command(cmd: int) -> None:
    hwnd = user32.GetForegroundWindow() or user32.GetDesktopWindow()
    user32.SendMessageW(hwnd, WM_APPCOMMAND, hwnd, cmd)
