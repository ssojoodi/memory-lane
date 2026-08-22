# Memory Lane

Memory Lane is a local-first Omarchy shell plugin for revisiting photographs and
recording the stories behind them. It never uploads or modifies original files.

## Features

- Private scanning of user-approved folders
- Randomized presentation with occasional resurfacing of annotated photos
- Fast keyboard navigation with session history
- Local drafts and timestamped reflections
- Metadata-stripped preview images
- One-click access to the original photograph

## Install from this checkout

```bash
bash scripts/install-local.sh
```

The installer copies runtime files to
`~/.config/omarchy/plugins/sojoodi.memory-lane`, validates the plugin, enables
it, and adds its photo icon to the right side of the bar.

Run the same command after making local changes. To remove the plugin UI:

```bash
omarchy plugin remove sojoodi.memory-lane --yes
```

Notes remain in `~/.local/share/memory-lane/` unless removed separately.

## Controls

| Key | Action |
| --- | --- |
| `Left` / `Right` | Previous / next photo |
| `S` | Skip and advance |
| `P` | Change prompt |
| `O` | Open original |
| `Ctrl+Enter` | Save while editing |
| `Escape` | Close |

## Privacy and storage

- Database: `${XDG_DATA_HOME:-~/.local/share}/memory-lane/memory-lane.sqlite3`
- Previews: `${XDG_CACHE_HOME:-~/.cache}/memory-lane/previews/`
- Source photos are opened read-only and never moved, renamed, or rewritten.
- The runtime makes no network requests.
- Scanning begins only after folder approval and never follows symlinks.

See [docs/privacy.md](docs/privacy.md) and [docs/design.md](docs/design.md) for
more detail.

## Development

Runtime dependencies are included with Omarchy 4: Python 3, SQLite, libvips,
`imv`, and `omarchy-file-select`.

Run the full checks with:

```bash
python3 -m unittest discover -s tests/python
node tests/js/memory-lane-model-test.js
bash tests/contract/plugin-test.sh
```

## License

[MIT](LICENSE)
