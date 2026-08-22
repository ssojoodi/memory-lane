# Memory Lane

Photos pile up, and the stories behind them are easy to lose. Memory Lane helps
by resurfacing them one at a time so you can record the moments, people, and
places that matter. It is a local-first Omarchy shell plugin that never uploads
or modifies original files.

## Features

- Private scanning of user-approved folders
- Randomized presentation with occasional resurfacing of annotated photos
- Fast keyboard navigation with session history
- Local drafts and timestamped reflections
- Metadata-stripped preview images
- One-click access to the original photograph

## Install

Install and enable Memory Lane directly from its public repository:

```bash
omarchy plugin add https://github.com/ssojoodi/memory-lane.git --enable
```

Remove the plugin UI with:

```bash
omarchy plugin remove sojoodi.memory-lane --yes
```

Notes remain in `~/.local/share/memory-lane/` unless removed separately.

## Development install

```bash
bash scripts/install-local.sh
```

The installer copies runtime files to
`~/.config/omarchy/plugins/sojoodi.memory-lane`, validates the plugin, enables
it, and adds its photo icon to the right side of the bar.

Run the same command after making local changes.

## Controls

| Key | Action |
| --- | --- |
| `Left` / `Right` | Previous / next photo |
| `S` | Skip and advance |
| `P` | Change prompt |
| `O` | Reveal original in Files |
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

## Dependencies

Memory Lane targets Omarchy 4 and uses Python 3, SQLite, libvips, Nautilus, and
`omarchy-file-select`. These runtime dependencies are included with Omarchy 4.

## Development

Run the full checks with:

```bash
python3 -m unittest discover -s tests/python
node tests/js/memory-lane-model-test.js
bash tests/contract/plugin-test.sh
```

## License

[MIT](LICENSE)
