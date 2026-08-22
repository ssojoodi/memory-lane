# Design

Memory Lane is a small, local-first Omarchy shell plugin. Its V1 goal is a fast,
keyboard-friendly loop for revisiting photographs and recording memories.

## Runtime

- `BarWidget.qml` opens the overlay from the Omarchy bar.
- `MemoryLane.qml` owns presentation and the current browsing session.
- `Service.qml` is a thin JSON-lines transport to the Python process.
- `backend/memory_lane/server.py` validates requests and performs actions.
- `backend/memory_lane/selection.py` owns photo-selection policy.
- SQLite stores approved roots, indexed photos, drafts, reflections, and events.

The QML layer is the sole owner of session navigation state. Each session entry
contains its photo payload, editable note, reflection, and preview path. Async
operations carry a request token so stale responses cannot replace newer UI
state.

Backend requests and responses are limited to 16 KiB per JSON line. Memory text
is limited to 8 KiB of UTF-8, and folder-chooser output is collected in chunks
with the same 16 KiB ceiling before it reaches application state.

## Photo selection

The preferred pool is intentionally varied:

- 80% fresh photos without a reflection, using the configured cooldown.
- 20% annotated photos that have not appeared for seven days.

When those pools are exhausted, selection falls back first to any photo not
skipped today and then to any available photo.

## Interaction

- `Left` and `Right` navigate within the current session.
- `S` skips the current photo and advances.
- `P` changes the prompt; the prompt controls also move backward and forward.
- `O` closes the overlay and reveals the original photograph in Files.
- `Escape` closes the overlay.
- `Ctrl+Enter` saves while the note editor is focused.

Saving or skipping immediately advances. Drafts are preserved when navigating or
closing. Previously saved reflections appear with their local date and time.

## Privacy boundaries

- Scanning starts only after the user approves a folder.
- Symlinks are not followed.
- Original photographs are read-only.
- Generated previews have metadata stripped and use private file permissions.
- Notes and indexes stay in private XDG data directories.
- The runtime contains no network client.

See [privacy.md](privacy.md) for the concise user-facing privacy model.
