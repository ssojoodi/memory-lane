# Upgrading existing local storage

The hardened version rejects linked, foreign-owned, nonregular, or nonprivate
state/cache files. It never silently repairs permissions, follows a suspicious
path, deletes a journal, or falls back to displaying an unchecked original.

An older installation can have a private database directory but 0644 SQLite
WAL/SHM files. Those files will now fail validation. Do not install and repeatedly
restart the new backend expecting it to repair them.

## Backup-first procedure

1. Close Memory Lane and disable its installed plugin through Omarchy. Verify
   that no `memory_lane_backend.py` process remains, including other shell
   sessions. Keep it stopped throughout the procedure.
2. Inspect the database path (including any XDG overrides) and every ancestor.
   Confirm real directories, expected ownership, no symbolic links, and no
   group/other-writable ancestors except sticky shared directories. If anything
   is suspicious, stop: do not chmod, delete, or open it in SQLite.
3. Inspect the database and any `-wal`, `-shm`, or `-journal` siblings without
   following links. Each must be a regular file owned by the current user with
   one hard link. Preserve the entire stopped state directory in a separate,
   user-owned 0700 backup directory, with backup files restricted to 0600.
   Do not copy only the main database: committed notes may still be in WAL.
   Verify the backup copies match before making any changes.
4. Only for those verified entries, adjust permissions through open, checked
   descriptors (`fstat` before `fchmod`): 0700 for the private state directory,
   0600 for the database and journal siblings. Do not use recursive chmod or
   path-following repair commands. Do not remove WAL/SHM/journal files.
5. Preview caches are disposable but should also be inspected before any
   action. If an old cache is unsafe, preserve/relocate its exact directory
   after checking its parent rather than following links or repairing targets.
   The plugin can create a new private cache on next use.
6. Install the hardened version, enable the plugin, and verify startup,
   existing notes, and a newly generated preview. Keep the backup until those
   checks succeed. If validation still fails, stop and inspect the reported
   path; do not weaken the checks or overwrite the backup.

This is a supervised migration checklist, not an automatic installer action.
The runtime and installer do not execute these repairs. The security boundary
does not protect against a hostile process already running as the same user
or root.
