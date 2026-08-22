#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$root"
python3 - <<'PY'
import json
from pathlib import Path
m=json.loads(Path("manifest.json").read_text())
assert m["id"] == "sojoodi.memory-lane" and not m["id"].startswith("omarchy.")
for entry in m["entryPoints"].values(): assert Path(entry).is_file(), entry
PY
if find . -type l -print -quit | grep -q .; then echo "Symlinks are not allowed" >&2; exit 1; fi
python3 -m py_compile backend/memory_lane_backend.py backend/memory_lane/*.py
if rg -n 'urllib|requests|http.client|https?://' backend Service.qml MemoryLane.qml BarWidget.qml; then
  echo "Network-capable runtime source detected" >&2; exit 1
fi
omarchy plugin validate .
