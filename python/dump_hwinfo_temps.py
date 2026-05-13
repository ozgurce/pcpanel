from panel_hwinfo_reader import _open_hwinfo_shared_blob, _parse_hwinfo_blob, read_hwinfo_metrics
blob = _open_hwinfo_shared_blob()
rows = _parse_hwinfo_blob(blob) if blob else []
print("=== PICKED METRICS ===")
print(read_hwinfo_metrics())
print("\n=== ALL TEMPERATURE ROWS ===")
for r in rows:
    unit = str(r.get("unit") or "")
    if unit.lower() in ("°c", "c", "℃") or "c" in unit.lower():
        print(f"{r.get('value'):>6} {r.get('unit'):<3} | sensor={r.get('sensor')} | label={r.get('label')}")
