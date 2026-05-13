import argparse
import json
import os
import sys
import time
from monitorcontrol import get_monitors

POWER_ON = 1
POWER_OFF = 4  # soft off / standby

PYTHON_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(PYTHON_DIR)
JSON_DIR = os.path.join(BASE_DIR, "json")
STATE_PATH = os.path.join(JSON_DIR, "monitor_power_state.json")
CONFIG_PATH = os.path.join(JSON_DIR, "monitor_power_config.json")


def _load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, type(default)) else default
    except Exception:
        return default


def _save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def _load_state():
    return _load_json(STATE_PATH, {})


def _save_state(data):
    _save_json(STATE_PATH, data)


def _load_config():
    return _load_json(CONFIG_PATH, {})


def _save_config(data):
    _save_json(CONFIG_PATH, data)


def _caps_to_safe(caps):
    if not isinstance(caps, dict):
        return {}

    def keys_of(name):
        value = caps.get(name)
        if isinstance(value, dict):
            return sorted([str(k) for k in value.keys()])
        return []

    return {
        "model": str(caps.get("model") or ""),
        "type": str(caps.get("type") or ""),
        "mccs_ver": str(caps.get("mccs_ver") or ""),
        "window": str(caps.get("window") or ""),
        "vcpname": str(caps.get("vcpname") or ""),
        "inputs": sorted([str(x) for x in caps.get("inputs", [])]) if isinstance(caps.get("inputs"), list) else [],
        "vcp_keys": keys_of("vcp"),
        "cmd_keys": keys_of("cmds"),
    }


def _fingerprint(info):
    parts = [
        info.get("model", ""),
        info.get("type", ""),
        info.get("mccs_ver", ""),
        ",".join(info.get("inputs", [])),
        ",".join(info.get("vcp_keys", [])),
        ",".join(info.get("cmd_keys", [])),
    ]
    return "|".join(parts)


def _read_monitor_info(monitor):
    try:
        with monitor:
            caps = monitor.get_vcp_capabilities()
    except Exception:
        caps = {}

    info = _caps_to_safe(caps)
    info["fingerprint"] = _fingerprint(info)
    info["ddc"] = bool(caps)
    return info


def _enumerate_monitors():
    monitors = get_monitors()
    result = []
    for index, monitor in enumerate(monitors):
        info = _read_monitor_info(monitor)
        info["index"] = index
        info["repr"] = repr(monitor)
        result.append((index, monitor, info))
    return result


def _score_match(target, info):
    score = 0

    if target.get("fingerprint") and target.get("fingerprint") == info.get("fingerprint"):
        score += 100

    for key, points in [
        ("model", 25),
        ("type", 10),
        ("mccs_ver", 10),
        ("window", 8),
        ("vcpname", 8),
    ]:
        if target.get(key) and target.get(key) == info.get(key):
            score += points

    target_vcp = set(target.get("vcp_keys") or [])
    info_vcp = set(info.get("vcp_keys") or [])
    if target_vcp and target_vcp == info_vcp:
        score += 20
    elif target_vcp and target_vcp.issubset(info_vcp):
        score += 8

    target_inputs = set(target.get("inputs") or [])
    info_inputs = set(info.get("inputs") or [])
    if target_inputs and target_inputs == info_inputs:
        score += 10

    return score


def _resolve_monitor(index=None, require_saved=True):
    monitors = _enumerate_monitors()
    if not monitors:
        raise RuntimeError("Monitör bulunamadı.")

    if index is not None:
        if index < 0 or index >= len(monitors):
            raise RuntimeError(f"Geçersiz index: {index}")
        return monitors[index]

    config = _load_config()
    target = config.get("target")
    if not target:
        if require_saved:
            raise RuntimeError("Kayıtlı hedef monitör yok. Önce: py panelmkapa.py select --index 0")
        return monitors[0]

    scored = []
    for item in monitors:
        _, _, info = item
        scored.append((_score_match(target, info), item))

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_item = scored[0]

    if best_score <= 0:
        raise RuntimeError("Kayıtlı monitör şu an bulunamadı.")

    same_best = [item for score, item in scored if score == best_score]
    if len(same_best) > 1:
        names = ", ".join(str(item[0]) for item in same_best)
        raise RuntimeError(f"Monitör eşleşmesi belirsiz. Aday indexler: {names}. Tekrar select yap.")

    return best_item


def list_monitors(json_output=False):
    rows = []
    for index, monitor, info in _enumerate_monitors():
        rows.append(info)

    if json_output:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    if not rows:
        print("Monitör bulunamadı.")
        return 1

    config = _load_config()
    target = config.get("target")

    for info in rows:
        index = info["index"]
        score = _score_match(target, info) if target else 0
        selected = "  <-- kayıtlı hedef" if target and score > 0 and score == max(_score_match(target, r) for r in rows) else ""
        print(f"[{index}] model={info.get('model') or '?'} type={info.get('type') or '?'} ddc={info.get('ddc')} score={score}{selected}")
        print(f"    mccs={info.get('mccs_ver') or '?'} inputs={', '.join(info.get('inputs') or [])}")
        print(f"    fingerprint={info.get('fingerprint')}")
    return 0


def select_monitor(index):
    _, _, info = _resolve_monitor(index=index, require_saved=False)
    config = _load_config()
    config["target"] = {
        "selected_index_at_save": index,
        "saved_at": int(time.time()),
        "model": info.get("model", ""),
        "type": info.get("type", ""),
        "mccs_ver": info.get("mccs_ver", ""),
        "window": info.get("window", ""),
        "vcpname": info.get("vcpname", ""),
        "inputs": info.get("inputs", []),
        "vcp_keys": info.get("vcp_keys", []),
        "cmd_keys": info.get("cmd_keys", []),
        "fingerprint": info.get("fingerprint", ""),
    }
    _save_config(config)
    print(f"Kaydedildi: index {index}, model={info.get('model') or '?'}")
    print(f"Config: {CONFIG_PATH}")
    return 0


def identify_monitor(index=None, brightness=10, seconds=4):
    resolved_index, monitor, _ = _resolve_monitor(index=index, require_saved=(index is None))
    try:
        with monitor:
            old = monitor.get_luminance()
            print(f"Index {resolved_index}: eski parlaklık = {old}")
            monitor.set_luminance(int(brightness))
            print(f"Index {resolved_index} parlaklığı {brightness} yapıldı. Hangi ekran karardıysa o.")
            time.sleep(float(seconds))
            monitor.set_luminance(old)
            print("Parlaklık geri alındı.")
        return 0
    except Exception as e:
        print(f"HATA: identify başarısız: {e}")
        return 1


def set_power(index, mode):
    resolved_index, monitor, _ = _resolve_monitor(index=index, require_saved=(index is None))
    try:
        with monitor:
            monitor.set_power_mode(mode)
        print(f"OK: index {resolved_index} -> power {mode}")
        return 0
    except Exception as e:
        print(f"HATA: power komutu başarısız: {e}")
        return 1


def brightness_off(index):
    resolved_index, monitor, info = _resolve_monitor(index=index, require_saved=(index is None))
    state = _load_state()

    try:
        with monitor:
            old = monitor.get_luminance()
            state[str(info.get("fingerprint") or resolved_index)] = {
                "index": resolved_index,
                "model": info.get("model", ""),
                "luminance": old,
                "saved_at": int(time.time()),
            }
            _save_state(state)
            monitor.set_luminance(0)
        print(f"OK: index {resolved_index} parlaklık 0 yapıldı. Eski değer kaydedildi: {old}")
        return 0
    except Exception as e:
        print(f"HATA: brightness-off başarısız: {e}")
        return 1


def brightness_on(index, fallback=70):
    resolved_index, monitor, info = _resolve_monitor(index=index, require_saved=(index is None))
    state = _load_state()

    saved = state.get(str(info.get("fingerprint") or resolved_index)) or {}
    value = int(saved.get("luminance", fallback))

    try:
        with monitor:
            monitor.set_luminance(value)
        print(f"OK: index {resolved_index} parlaklık {value} yapıldı.")
        return 0
    except Exception as e:
        print(f"HATA: brightness-on başarısız: {e}")
        return 1


def main():
    parser = argparse.ArgumentParser(description="DDC/CI monitor power and brightness control with saved monitor identity.")
    parser.add_argument("command", choices=["list", "select", "identify", "on", "off", "brightness-on", "brightness-off"])
    parser.add_argument("--index", type=int, default=None, help="Monitör indexi. select için zorunlu, diğerlerinde verilmezse kayıtlı hedef kullanılır.")
    parser.add_argument("--seconds", type=float, default=4, help="identify süresi. Varsayılan: 4")
    parser.add_argument("--brightness", type=int, default=10, help="identify parlaklığı. Varsayılan: 10")
    parser.add_argument("--fallback", type=int, default=70, help="brightness-on kayıt bulamazsa kullanılacak değer.")
    parser.add_argument("--json", action="store_true", help="list çıktısını JSON ver.")

    args = parser.parse_args()

    try:
        if args.command == "list":
            return list_monitors(json_output=args.json)

        if args.command == "select":
            if args.index is None:
                print("select için --index gerekli. Örnek: py panelmkapa.py select --index 0")
                return 1
            return select_monitor(args.index)

        if args.command == "identify":
            return identify_monitor(args.index, args.brightness, args.seconds)

        if args.command == "off":
            return set_power(args.index, POWER_OFF)

        if args.command == "on":
            return set_power(args.index, POWER_ON)

        if args.command == "brightness-off":
            return brightness_off(args.index)

        if args.command == "brightness-on":
            return brightness_on(args.index, args.fallback)

        return 1

    except Exception as e:
        print(f"HATA: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
