# Privacy model

Memory Lane has no network client and scans only user-confirmed roots. It validates image signatures, ignores symlinks, filters common screenshot names and directories conservatively, and keeps all state in private XDG directories. Preview files contain the rendered image but have metadata stripped. Original files are never written.

Omarchy plugins execute as the signed-in user and are not sandboxed. Review this repository before installing it, as you should with any third-party shell plugin.

The optional location button reads embedded EXIF GPS metadata locally using
libvips. Only when clicked, it opens OpenStreetMap in your default browser,
sharing the photo's coordinates with that site (and normal browser connection
information). It does not upload the photo, file path, or notes. No location is
guessed when metadata is absent, and no coordinates are added to the database.

Database storage is opened through checked directory descriptors. Every path
component must be a real directory owned by the current user or root, without
group/other write access (sticky shared ancestors such as `/tmp` are allowed).
The final database directory must be owned by the current user and private.
Existing database, rollback-journal, WAL, and shared-memory entries must be
private regular files owned by the current user with a single hard link.
Symlinks, special files, and unsafe permissions are rejected before migration;
the plugin does not repair them automatically or change their targets.

New directories and database files are created with modes 0700 and 0600,
respectively. SQLite opens through `/proc/self/fd/<directory-fd>/…`; its
canonical database identity is checked before WAL setup and migration. SQLite
canonicalizes paths for journal access, so checked ancestor permissions are
also part of this protection. This guards against planted links and access by
other users, not a hostile process already running as your user or root.

An existing installation with a symlinked storage path or nonprivate database
permissions now stops instead of opening it. Inspect the path and preserve your
notes before manually relocating it to a real private directory. No database
content is rewritten or discarded to remediate an unsafe path.
