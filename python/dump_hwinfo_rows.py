# File Version: 1.0
# Dumps raw HWiNFO rows so sensor name matching can be fixed precisely.
# Run: py dump_hwinfo_rows.py
import json
from panel_hwinfo_reader import _open_hwinfo_shared_blob, _parse_hwinfo_blob, read_hwinfo_metrics

rows = _parse_hwinfo_blob(_open_hwinfo_shared_blob())
metrics = read_hwinfo_metrics()
print('METRICS:')
print(json.dumps(metrics, ensure_ascii=False, indent=2))
print('\nROWS containing CPU/GPU/power/temp/load:')
for r in rows:
    text = (r.get('text') or '').lower()
    unit = str(r.get('unit') or '')
    if unit in ('°C', '℃', 'C', 'W', '%') or any(k in text for k in ('cpu','gpu','tctl','tdie','power','load','sıcak','işlemci','nvidia','radeon','package')):
        print(f"{r.get('sensor')} | {r.get('label')} | {r.get('unit')} | {r.get('value')}")
