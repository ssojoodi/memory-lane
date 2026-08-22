#!/usr/bin/env bash
set -euo pipefail
source_dir="$(cd "$(dirname "$0")/.." && pwd)"
plugin_dir="${XDG_CONFIG_HOME:-$HOME/.config}/omarchy/plugins/sojoodi.memory-lane"
install -d -m 700 "$plugin_dir"
install -d -m 700 "$plugin_dir/backend/memory_lane" "$plugin_dir/migrations"
rm -f -- "$plugin_dir/content/prompts.json"
rmdir "$plugin_dir/content" "$plugin_dir/ui" 2>/dev/null || true
install -m 644 "$source_dir/manifest.json" "$source_dir/BarWidget.qml" "$source_dir/MemoryLane.qml" "$source_dir/MemoryLaneModel.js" "$source_dir/Service.qml" "$plugin_dir/"
install -m 755 "$source_dir/backend/memory_lane_backend.py" "$plugin_dir/backend/"
install -m 644 "$source_dir"/backend/memory_lane/*.py "$plugin_dir/backend/memory_lane/"
install -m 644 "$source_dir/migrations/001_initial.sql" "$plugin_dir/migrations/"
omarchy plugin validate "$plugin_dir"
omarchy-shell shell rescanPlugins
omarchy plugin enable sojoodi.memory-lane right
echo "Memory Lane installed and enabled. Click the photo icon in the right side of the bar."
