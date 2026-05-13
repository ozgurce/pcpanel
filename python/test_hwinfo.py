import json
from panel_hwinfo_reader import read_hwinfo_metrics

print(json.dumps(read_hwinfo_metrics(), ensure_ascii=False, indent=2))
