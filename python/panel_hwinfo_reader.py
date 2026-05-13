import ctypes
import ctypes.wintypes
import time
import re
from panel_globals import SENSOR_CACHE_LOCK
from panel_logging import log_hwinfo_error
from panel_runtime_helpers import safe_execute

# HWiNFO Shared Memory Constants
HWiNFO_SHARED_MEM_PATHS = (r"Global\HWiNFO_SENS_SM2", r"Local\HWiNFO_SENS_SM2")
HWiNFO_SHARED_MEM_MUTEXES = (r"Global\HWiNFO_SM2_MUTEX", r"Local\HWiNFO_SM2_MUTEX")
HWiNFO_HEADER_MAGIC = 0x53695748

class HWiNFOHeader(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("magic", ctypes.c_uint32), ("version", ctypes.c_uint32),
        ("version2", ctypes.c_uint32), ("last_update", ctypes.c_int64),
        ("sensor_section_offset", ctypes.c_uint32), ("sensor_element_size", ctypes.c_uint32),
        ("sensor_element_count", ctypes.c_uint32), ("entry_section_offset", ctypes.c_uint32),
        ("entry_element_size", ctypes.c_uint32), ("entry_element_count", ctypes.c_uint32),
    ]

class HWiNFOSensor(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("id", ctypes.c_uint32), ("instance", ctypes.c_uint32),
        ("name_original", ctypes.c_char * 128), ("name_user", ctypes.c_char * 128),
    ]

class HWiNFOEntry(ctypes.Structure):
    _pack_ = 1
    _fields_ = [
        ("type", ctypes.c_uint32), ("sensor_index", ctypes.c_uint32),
        ("id", ctypes.c_uint32), ("name_original", ctypes.c_char * 128),
        ("name_user", ctypes.c_char * 128), ("unit", ctypes.c_char * 16),
        ("value", ctypes.c_double), ("value_min", ctypes.c_double),
        ("value_max", ctypes.c_double), ("value_avg", ctypes.c_double),
    ]

kernel32 = ctypes.windll.kernel32
FILE_MAP_READ = 0x0004
SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0x00000000
INFINITE = 0xFFFFFFFF

# Make ctypes return null/valid pointer values correctly on 64-bit Python.
kernel32.OpenMutexW.restype = ctypes.wintypes.HANDLE
kernel32.OpenFileMappingW.restype = ctypes.wintypes.HANDLE
kernel32.MapViewOfFile.restype = ctypes.c_void_p
kernel32.UnmapViewOfFile.argtypes = [ctypes.c_void_p]

def _cstr(buf) -> str:
    raw = bytes(buf).split(b"\x00", 1)[0]
    for enc in ("utf-8", "mbcs", "latin-1"):
        try:
            return raw.decode(enc, errors="ignore").strip()
        except Exception:
            pass
    return raw.decode(errors="ignore").strip()

def _norm(text):
    return re.sub(r"\s+", " ", str(text or "").strip().lower())

def _num(value):
    try:
        value = float(value)
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return round(value, 1)
    except Exception:
        return None

_LAST_HWINFO_OPEN_ERROR = {"text": "", "ts": 0.0}

def _log_hwinfo_open_error_once(text, interval=5.0):
    now = time.time()
    if text != _LAST_HWINFO_OPEN_ERROR.get("text") or (now - float(_LAST_HWINFO_OPEN_ERROR.get("ts") or 0.0)) >= interval:
        _LAST_HWINFO_OPEN_ERROR.update({"text": text, "ts": now})
        log_hwinfo_error(text)

def _open_hwinfo_shared_blob() -> bytes:
    last_error = None
    for mapping_name, mutex_name in zip(HWiNFO_SHARED_MEM_PATHS, HWiNFO_SHARED_MEM_MUTEXES):
        mutex = None
        mapping = None
        header_view = None
        data_view = None
        try:
            mutex = kernel32.OpenMutexW(SYNCHRONIZE, False, mutex_name)
            mapping = kernel32.OpenFileMappingW(FILE_MAP_READ, False, mapping_name)
            if not mapping:
                last_error = f"{mapping_name} not found"
                continue

            header_view = kernel32.MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, ctypes.sizeof(HWiNFOHeader))
            if not header_view:
                raise ConnectionError(f"HWiNFO header map failed for {mapping_name}.")
            header = HWiNFOHeader.from_buffer_copy(ctypes.string_at(header_view, ctypes.sizeof(HWiNFOHeader)))
            kernel32.UnmapViewOfFile(header_view)
            header_view = None

            if header.magic != HWiNFO_HEADER_MAGIC:
                raise ValueError(f"Invalid HWiNFO shared memory magic for {mapping_name}: 0x{header.magic:08x}")

            size = header.entry_section_offset + header.entry_element_count * header.entry_element_size
            if size <= ctypes.sizeof(HWiNFOHeader) or size > 32 * 1024 * 1024:
                raise ValueError(f"Invalid HWiNFO shared memory size for {mapping_name}: {size}")

            data_view = kernel32.MapViewOfFile(mapping, FILE_MAP_READ, 0, 0, size)
            if not data_view:
                raise ConnectionError(f"HWiNFO data map failed for {mapping_name}.")
            return ctypes.string_at(data_view, size)
        except Exception as e:
            last_error = f"{mapping_name}: {type(e).__name__}: {e}"
        finally:
            if header_view:
                kernel32.UnmapViewOfFile(header_view)
            if data_view:
                kernel32.UnmapViewOfFile(data_view)
            if mapping:
                kernel32.CloseHandle(mapping)
            if mutex:
                kernel32.CloseHandle(mutex)
    raise ConnectionError("HWiNFO shared memory not found/opened. Tried Global and Local mappings. Last error: " + str(last_error))

def _parse_hwinfo_blob(blob):
    header = HWiNFOHeader.from_buffer_copy(blob[:ctypes.sizeof(HWiNFOHeader)])
    sensors = []
    for i in range(header.sensor_element_count):
        off = header.sensor_section_offset + i * header.sensor_element_size
        if off + ctypes.sizeof(HWiNFOSensor) > len(blob):
            break
        s = HWiNFOSensor.from_buffer_copy(blob[off:off + ctypes.sizeof(HWiNFOSensor)])
        sensors.append({
            "name": _cstr(s.name_user) or _cstr(s.name_original),
            "id": int(s.id),
            "instance": int(s.instance),
        })

    rows = []
    for i in range(header.entry_element_count):
        off = header.entry_section_offset + i * header.entry_element_size
        if off + ctypes.sizeof(HWiNFOEntry) > len(blob):
            break
        e = HWiNFOEntry.from_buffer_copy(blob[off:off + ctypes.sizeof(HWiNFOEntry)])
        sensor = sensors[e.sensor_index] if e.sensor_index < len(sensors) else {"name": ""}
        label = _cstr(e.name_user) or _cstr(e.name_original)
        unit = _cstr(e.unit)
        value = _num(e.value)
        if value is None:
            continue
        rows.append({
            "sensor": sensor.get("name", ""),
            "label": label,
            "unit": unit,
            "value": value,
            "type": int(e.type),
            "text": _norm(f"{sensor.get('name', '')} {label} {unit}"),
        })
    return rows

def _pick(rows, unit=None, include=(), prefer=(), exclude=(), lo=None, hi=None):
    candidates = []
    for r in rows:
        text = r["text"]
        if unit and _norm(r.get("unit")) != _norm(unit):
            continue
        if include and not all(re.search(p, text, re.I) for p in include):
            continue
        if exclude and any(re.search(p, text, re.I) for p in exclude):
            continue
        val = r["value"]
        if lo is not None and val < lo:
            continue
        if hi is not None and val > hi:
            continue
        score = 0
        for idx, p in enumerate(prefer):
            if re.search(p, text, re.I):
                score += 100 - idx
        candidates.append((score, r))
    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]["value"]

def _pick_ram_slots(rows):
    slots = []
    seen = set()
    for r in rows:
        t = r["text"]
        if _norm(r.get("unit")) in ("°c", "c", "℃") and re.search(r"\b(dimm|spd|ddr[45]|memory module|memory temperature|spd hub)\b", t, re.I):
            if 0 <= r["value"] <= 120:
                key = (r.get("sensor") or "", r.get("label") or "", r["value"])
                if key in seen:
                    continue
                seen.add(key)
                slots.append({"name": r["label"] or r["sensor"], "temp": r["value"], "temp_c": r["value"]})
    return slots[:8]

def _disk_letters_from_text(text):
    letters = []
    txt = str(text or "")
    # HWiNFO often reports disk groups like: [C:], [D:], [C:, E:] or [C, D].
    # The panel expects direct C/D/E keys, so accept both bare letters and letter-colon forms.
    for m in re.finditer(r"\[([^\]]+)\]", txt, re.I):
        for item in re.split(r"\s*,\s*", m.group(1)):
            item = item.strip().upper().rstrip(":")
            if len(item) == 1 and item.isalpha():
                letters.append(item)
    for m in re.finditer(r"\b([A-Z]):(?:\\|\]|\s|$)", txt, re.I):
        letters.append(m.group(1).upper())
    return list(dict.fromkeys(letters))

def _pick_disks(rows):
    disks = {}
    for r in rows:
        t = r["text"]
        if _norm(r.get("unit")) not in ("°c", "c", "℃"):
            continue
        if not re.search(r"\b(drive|ssd|nvme|hdd|s\.m\.a\.r\.t|disk)\b", t, re.I):
            continue
        name = r["sensor"] or r["label"] or "disk"
        item = {"name": name, "temp": r["value"], "temp_c": r["value"]}
        disks[name] = item
        for letter in _disk_letters_from_text(name):
            disks[letter] = dict(item)
    return disks


def _contains_any(text, patterns):
    return any(re.search(p, text, re.I) for p in patterns)

def _pick_cpu_temp(rows):
    # Prefer explicit CPU package/Tctl values, then any sane CPU temperature.
    val = _pick(rows, unit="°C", include=(r"(cpu|işlemci|processor|ryzen|tctl|tdie|ccd|package)",),
                prefer=(r"tctl/tdie", r"tctl", r"tdie", r"cpu package", r"package", r"ccd", r"die", r"core temperatures"),
                exclude=(r"gpu|ekran kart|graphics|ssd|nvme|drive|disk|dimm|spd|memory|vrm|mos|chipset"), lo=0, hi=120)
    if val is not None:
        return val
    candidates = []
    for r in rows:
        if _norm(r.get("unit")) not in ("°c", "c", "℃"):
            continue
        t = r["text"]
        if _contains_any(t, (r"tctl", r"tdie", r"\bccd\b", r"core temperatures", r"cpu package", r"işlemci", r"processor")) and not _contains_any(t, (r"gpu", r"ssd", r"nvme", r"drive", r"disk", r"dimm", r"spd")):
            candidates.append((0 if re.search(r"tctl|tdie|package", t, re.I) else 1, r["value"]))
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1] if candidates else None

def _pick_gpu_temp(rows):
    val = _pick(rows, unit="°C", include=(r"(gpu|graphics|ekran kart|nvidia|radeon)",),
                prefer=(r"gpu temperature", r"gpu sıcak", r"hot spot", r"gpu"),
                exclude=(r"memory junction|vram"), lo=0, hi=130)
    if val is not None:
        return val
    for r in rows:
        if _norm(r.get("unit")) in ("°c", "c", "℃") and _contains_any(r["text"], (r"gpu", r"graphics", r"nvidia", r"radeon", r"hot spot", r"ekran kart")):
            return r["value"]
    return None

def _pick_cpu_power(rows):
    val = _pick(rows, unit="W", include=(r"(cpu|işlemci|processor|ryzen|ppt|package)",),
                prefer=(r"cpu package power", r"package power", r"cpu ppt", r"ppt", r"cpu power", r"işlemci"),
                exclude=(r"gpu|graphics|ekran kart"), lo=0, hi=1000)
    if val is not None:
        return val
    for r in rows:
        if _norm(r.get("unit")) == "w" and _contains_any(r["text"], (r"\bppt\b", r"cpu", r"package power", r"işlemci")) and not _contains_any(r["text"], (r"gpu", r"graphics")):
            return r["value"]
    return None

def _pick_gpu_power(rows):
    val = _pick(rows, unit="W", include=(r"(gpu|graphics|ekran kart|nvidia|radeon|board power)",),
                prefer=(r"total board power", r"board power", r"gpu power", r"gpu chip power"), lo=0, hi=1000)
    if val is not None:
        return val
    for r in rows:
        if _norm(r.get("unit")) == "w" and _contains_any(r["text"], (r"gpu", r"graphics", r"board power", r"nvidia", r"radeon", r"ekran kart")):
            return r["value"]
    return None



def _temp_rows(rows):
    out = []
    for r in rows:
        try:
            if _norm(r.get("unit")) in ("°c", "c", "℃") and 0 <= float(r.get("value")) <= 160:
                out.append(r)
        except Exception:
            continue
    return out


def _score_temp_row(row, include=(), prefer=(), exclude=(), sensor_prefer=(), label_prefer=()):
    text = _norm(row.get("text") or "")
    sensor = _norm(row.get("sensor") or "")
    label = _norm(row.get("label") or "")
    if exclude and any(re.search(p, text, re.I) for p in exclude):
        return None
    if include and not any(re.search(p, text, re.I) for p in include):
        return None
    score = 0
    for idx, p in enumerate(prefer):
        if re.search(p, text, re.I):
            score += 300 - idx * 10
    for idx, p in enumerate(label_prefer):
        if re.search(p, label, re.I):
            score += 500 - idx * 10
    for idx, p in enumerate(sensor_prefer):
        if re.search(p, sensor, re.I):
            score += 120 - idx * 5
    # Avoid anonymous Temp1/Temp2 unless nothing better exists.
    if re.fullmatch(r"temp(?:erature)?\s*\d+", label, re.I):
        score -= 80
    return score


def _pick_motherboard_temp(rows):
    candidates = []
    for r in _temp_rows(rows):
        score = _score_temp_row(
            r,
            include=(r"motherboard|mainboard|mobo|anakart|system|chipset|pch|nuvoton|ite|asus|ec|super\s*i/?o|t_sensor",),
            prefer=(r"motherboard", r"mainboard", r"mobo", r"anakart", r"system", r"chipset", r"pch", r"t_sensor"),
            label_prefer=(r"^motherboard$", r"^mainboard$", r"^system$", r"^chipset$", r"^pch$", r"^t_sensor$"),
            sensor_prefer=(r"asus", r"nuvoton", r"ite", r"ec", r"super\s*i/?o"),
            exclude=(r"cpu|processor|işlemci|gpu|graphics|ekran kart|dimm|spd|ddr|memory|bellek|drive|ssd|nvme|disk|vrm|v\s*r\s*mos|vr\s*mos|mosfet|mos",),
        )
        if score is not None:
            candidates.append((score, r))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]["value"]


def _pick_vrm_mos_temp(rows):
    candidates = []
    for r in _temp_rows(rows):
        score = _score_temp_row(
            r,
            include=(r"vrm|v\s*r\s*mos|vr\s*mos|vmos|mosfet|\bmos\b|cpu\s*vr|vcore\s*vr",),
            prefer=(r"vrm\s*mos", r"v\s*r\s*mos", r"vr\s*mos", r"vmos", r"vrm", r"mosfet", r"\bmos\b", r"cpu\s*vr", r"vcore\s*vr"),
            label_prefer=(r"vrm\s*mos", r"v\s*r\s*mos", r"vr\s*mos", r"vmos", r"vrm", r"mos"),
            sensor_prefer=(r"asus", r"nuvoton", r"ite", r"ec", r"super\s*i/?o"),
            exclude=(r"gpu|graphics|ekran kart|drive|ssd|nvme|disk|dimm|spd|ddr|memory\s+junction",),
        )
        if score is not None:
            candidates.append((score, r))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]["value"]


def _pick_gpu_util(rows):
    candidates = []
    for r in rows:
        if _norm(r.get("unit")) != "%":
            continue
        text = _norm(r.get("text") or "")
        if not re.search(r"gpu|graphics|nvidia|radeon|ekran kart", text, re.I):
            continue
        if re.search(r"memory|vram|bus|video|encoder|decoder|copy|compute|fan|limit|voltage|power", text, re.I):
            continue
        val = r.get("value")
        if val is None or val < 0 or val > 100:
            continue
        score = 0
        label = _norm(r.get("label") or "")
        for idx, p in enumerate((r"^gpu core load$", r"gpu core load", r"gpu load", r"gpu usage", r"3d usage", r"3d", r"core load")):
            if re.search(p, label, re.I) or re.search(p, text, re.I):
                score += 500 - idx * 20
        candidates.append((score, r))
    if not candidates:
        return _pick(rows, unit="%", include=(r"(gpu|graphics|nvidia|radeon|ekran kart)",), prefer=(r"gpu core load", r"gpu load", r"3d usage", r"gpu usage"), exclude=(r"memory|vram|bus|video|encoder|decoder|copy|compute|fan|limit|voltage|power",), lo=0, hi=100)
    candidates.sort(key=lambda x: x[0], reverse=True)
    return candidates[0][1]["value"]


def _debug_temp_rows(rows, limit=60):
    items = []
    for r in _temp_rows(rows)[:limit]:
        items.append({"sensor": r.get("sensor"), "label": r.get("label"), "value": r.get("value"), "unit": r.get("unit")})
    return items

def read_hwinfo_metrics():
    try:
        blob = _open_hwinfo_shared_blob()
        if not blob:
            _log_hwinfo_open_error_once("HWiNFO shared memory returned empty data.")
            return {}
        rows = _parse_hwinfo_blob(blob)
        data = {
            "cpu_temp": _pick_cpu_temp(rows),
            "gpu_temp": _pick_gpu_temp(rows),
            "cpu_percent": _pick(rows, unit="%", include=(r"(cpu|işlemci|processor)",), prefer=(r"total cpu utility", r"total cpu usage", r"cpu total", r"core utility", r"cpu usage", r"işlemci"), exclude=(r"gpu|graphics|ekran kart",), lo=0, hi=100),
            "gpu_util": _pick_gpu_util(rows),
            "cpu_power": _pick_cpu_power(rows),
            "gpu_power": _pick_gpu_power(rows),
            "vram_percent": _pick(rows, unit="%", include=(r"(gpu|graphics|nvidia|radeon|ekran kart)", r"(memory|vram|bellek)"), prefer=(r"dedicated memory usage", r"vram", r"memory usage", r"bellek"), lo=0, hi=100),
            "motherboard_temp": _pick_motherboard_temp(rows),
            "vmos_temp": _pick_vrm_mos_temp(rows),
            "ram_slot_temps": _pick_ram_slots(rows),
            "disks_cde": _pick_disks(rows),
        }
        if data.get("motherboard_temp") is not None:
            data["mobo_temp"] = data.get("motherboard_temp")
        if data.get("vmos_temp") is not None:
            data["vrm_temp"] = data.get("vmos_temp")
            data["vrmos_temp"] = data.get("vmos_temp")
        # Tiny rolling debug sample for the health/debug screens; harmless if ignored by UI.
        data["hwinfo_temp_rows_debug"] = _debug_temp_rows(rows, 40)
        return {k: v for k, v in data.items() if v not in (None, [], {})}
    except Exception as e:
        _log_hwinfo_open_error_once(f"HWiNFO read error: {type(e).__name__}: {e}")
        return {}

def hwinfo_cache_reader_loop():
    from panel_globals import WORKER_STATE
    from panel_hwinfo_snapshot import _read_latest_hwinfo_snapshot, _apply_hwinfo_payload_to_cache
    while True:
        try:
            payload = _read_latest_hwinfo_snapshot()
            if payload:
                _apply_hwinfo_payload_to_cache(payload.get("data") or {}, now=payload.get("ts") or time.time())
                WORKER_STATE["last_hwinfo_seen"] = time.time()
        except Exception as e:
            log_hwinfo_error(f"Reader loop error: {e}")
        time.sleep(0.5)
