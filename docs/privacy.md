# Privacy model

Memory Lane has no network client and scans only user-confirmed roots. It validates image signatures, ignores symlinks, filters common screenshot names and directories conservatively, and keeps all state in private XDG directories. Preview files contain the rendered image but have metadata stripped. Original files are never written.

Omarchy plugins execute as the signed-in user and are not sandboxed. Review this repository before installing it, as you should with any third-party shell plugin.
