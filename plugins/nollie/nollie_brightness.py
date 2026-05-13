#!/usr/bin/env python3
"""Set NollieRGB canvas brightness to 0 and restore previous values."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time
from pathlib import Path

import hid


HID_SET_EFFECT = 250
HID_GET_EFFECT = 249
HID_EFFECT_CH_PARAM = 2
HID_EFFECT_CANVAS_LEN = 4
HID_EFFECT_START_CANVAS_LEN = 5

TX_LEN = 64
RX_LEN = 64
READ_TIMEOUT_MS = 120
STATE_PATH = Path(__file__).resolve().parents[2] / "json" / "nollie" / "nollie_brightness_state.json"

DEVICE_CANDIDATES = [
    {"name": "Nollie8", "vendor_id": 5845, "product_id": 10760, "interface_number": 2},
    {"name": "Nollie8_old_2025", "vendor_id": 5845, "product_id": 7937, "interface_number": 0},
    {"name": "Nollie8_old", "vendor_id": 5842, "product_id": 7937, "interface_number": 0},
    {"name": "Prism8", "vendor_id": 5845, "product_id": 11272, "interface_number": 2},
    {"name": "G857D", "vendor_id": 6790, "product_id": 58136, "interface_number": 2},
]

GENERAL_CONFIG_KEYS = (
    "fx_mode",
    "fx_brightness",
    "fx_step",
    "fx_size",
    "fx_canvas_ch_len",
    "fx_vmap_process",
    "fx_delay",
    "fx_color_1",
    "fx_color_2",
    "fx_color_3",
)


class NollieBrightnessError(RuntimeError):
    pass


def _candidate_for(info: dict) -> dict | None:
    for candidate in DEVICE_CANDIDATES:
        if (
            info.get("vendor_id") == candidate["vendor_id"]
            and info.get("product_id") == candidate["product_id"]
            and info.get("interface_number") == candidate["interface_number"]
        ):
            return candidate
    return None


def find_device() -> tuple[dict, dict]:
    for info in hid.enumerate():
        candidate = _candidate_for(info)
        if candidate:
            return info, candidate

    known = ", ".join(f"{d['name']} VID={d['vendor_id']:04x} PID={d['product_id']:04x}" for d in DEVICE_CANDIDATES)
    raise NollieBrightnessError(f"Nollie cihazı bulunamadı. Aranan cihazlar: {known}")


def open_device(info: dict) -> hid.device:
    device = hid.device()
    try:
        device.open_path(info["path"])
    except OSError as exc:
        raise NollieBrightnessError(
            "Cihaz açılamadı. NollieRGB veya OpenRGB açıksa kapatıp tekrar deneyin."
        ) from exc
    return device


def send_packet(device: hid.device, payload: list[int]) -> None:
    if len(payload) > TX_LEN:
        raise NollieBrightnessError(f"Paket çok uzun: {len(payload)} byte")
    packet = [0] + payload + [0] * (TX_LEN - len(payload))
    written = device.write(packet)
    if written <= 0:
        raise NollieBrightnessError("HID yazma başarısız oldu.")


def read_packet(device: hid.device, timeout_ms: int = READ_TIMEOUT_MS) -> list[int]:
    for attempt in range(3):
        data = device.read(RX_LEN, timeout_ms)
        if data:
            return list(data) + [0] * (RX_LEN - len(data))
        if attempt < 2:
            time.sleep(0.02)
    raise NollieBrightnessError("Cihazdan cevap alınamadı.")


def query_u8(device: hid.device, subcommand: int) -> int:
    send_packet(device, [HID_GET_EFFECT, subcommand])
    return read_packet(device)[0]


def get_canvas_indices(device: hid.device, include_boot: bool = True) -> list[int]:
    normal_count = query_u8(device, HID_EFFECT_CANVAS_LEN)
    if normal_count > 14:
        raise NollieBrightnessError(f"Beklenmeyen normal canvas sayısı: {normal_count}")

    indices = list(range(normal_count))

    if include_boot:
        boot_count = query_u8(device, HID_EFFECT_START_CANVAS_LEN)
        if boot_count > 2:
            raise NollieBrightnessError(f"Beklenmeyen boot canvas sayısı: {boot_count}")
        indices.extend(range(14, 14 + boot_count))

    return indices


def get_general_config(device: hid.device, canvas_index: int) -> dict:
    send_packet(device, [HID_GET_EFFECT, HID_EFFECT_CH_PARAM, canvas_index])
    data = read_packet(device)
    return {
        "fx_mode": data[3],
        "fx_brightness": data[4],
        "fx_step": data[5],
        "fx_size": data[6],
        "fx_canvas_ch_len": data[7],
        "fx_vmap_process": data[8],
        "fx_delay": data[9],
        "fx_color_1": data[10:13],
        "fx_color_2": data[13:16],
        "fx_color_3": data[16:19],
    }


def set_general_config(device: hid.device, canvas_index: int, config: dict) -> None:
    missing = [key for key in GENERAL_CONFIG_KEYS if key not in config]
    if missing:
        raise NollieBrightnessError(f"Eksik config alanı: {', '.join(missing)}")

    payload = [
        HID_SET_EFFECT,
        HID_EFFECT_CH_PARAM,
        canvas_index,
        int(config["fx_mode"]),
        int(config["fx_brightness"]),
        int(config["fx_step"]),
        int(config["fx_size"]),
        int(config["fx_canvas_ch_len"]),
        int(config["fx_vmap_process"]),
        int(config["fx_delay"]),
        *[int(x) for x in config["fx_color_1"]],
        *[int(x) for x in config["fx_color_2"]],
        *[int(x) for x in config["fx_color_3"]],
    ]
    send_packet(device, payload)


def read_all_configs(device: hid.device, include_boot: bool) -> dict[str, dict]:
    return {str(index): get_general_config(device, index) for index in get_canvas_indices(device, include_boot)}


def save_state(
    info: dict,
    candidate: dict,
    configs: dict[str, dict],
    include_boot: bool,
    overwrite: bool,
    state_path: Path = STATE_PATH,
) -> None:
    if state_path.exists() and not overwrite:
        current_has_light = any(config.get("fx_brightness", 0) > 0 for config in configs.values())
        if not current_has_light:
            return

    state = {
        "saved_at": dt.datetime.now().isoformat(timespec="seconds"),
        "device": {
            "name": candidate["name"],
            "vendor_id": info.get("vendor_id"),
            "product_id": info.get("product_id"),
            "interface_number": info.get("interface_number"),
            "serial_number": info.get("serial_number"),
            "product_string": info.get("product_string"),
        },
        "include_boot": include_boot,
        "configs": configs,
    }
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")


def set_all_brightness(device: hid.device, configs: dict[str, dict], brightness: int) -> None:
    for index_text, config in configs.items():
        updated = dict(config)
        updated["fx_brightness"] = brightness
        set_general_config(device, int(index_text), updated)


def restore(device: hid.device, state_path: Path = STATE_PATH) -> int:
    if not state_path.exists():
        raise NollieBrightnessError(f"Kayıt dosyası yok: {state_path}")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    configs = state.get("configs") or {}
    if not configs:
        raise NollieBrightnessError("Kayıt dosyasında geri yüklenecek brightness yok.")

    for index_text, config in configs.items():
        set_general_config(device, int(index_text), config)
    return len(configs)


def print_status(configs: dict[str, dict]) -> None:
    for index_text, config in sorted(configs.items(), key=lambda item: int(item[0])):
        print(f"canvas {index_text}: brightness={config['fx_brightness']}")


def main() -> int:
    parser = argparse.ArgumentParser(description="NollieRGB brightness off/restore helper")
    parser.add_argument("action", choices=("off", "restore", "status", "toggle"))
    parser.add_argument("--no-boot", action="store_true", help="Boot canvas brightness değerlerini dahil etme")
    parser.add_argument("--overwrite-state", action="store_true", help="Var olan kayıt dosyasını off sırasında yenile")
    parser.add_argument("--state-path", default=str(STATE_PATH), help="Brightness kayıt dosyası yolu")
    args = parser.parse_args()

    try:
        info, candidate = find_device()
        device = open_device(info)
        try:
            include_boot = not args.no_boot
            state_path = Path(args.state_path)

            if args.action == "status":
                print_status(read_all_configs(device, include_boot))
                return 0

            if args.action == "restore":
                count = restore(device, state_path=state_path)
                print(f"{count} canvas eski brightness değerine döndü.")
                return 0

            configs = read_all_configs(device, include_boot)
            if args.action == "toggle" and all(config["fx_brightness"] == 0 for config in configs.values()):
                count = restore(device, state_path=state_path)
                print(f"{count} canvas eski brightness değerine döndü.")
                return 0

            save_state(info, candidate, configs, include_boot, args.overwrite_state, state_path=state_path)
            set_all_brightness(device, configs, 0)
            print(f"{len(configs)} canvas brightness=0 yapıldı. Geri almak için: python nollie_brightness.py restore")
            return 0
        finally:
            device.close()
    except NollieBrightnessError as exc:
        print(f"Hata: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
