import fnmatch
import os
from pathlib import Path

from .database import utcnow

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_DIRS = {"screenshots", "screenshot", "downloads", "thumbnails", ".thumbnails", "cache", ".cache", "trash", ".trash"}
DEFAULT_PATTERNS = ("Screenshot_*", "screenshot-*", "Screenshot *", "screenshot_*")


def mime_type(path):
    if path.suffix.lower() not in EXTENSIONS:
        return None
    try:
        with path.open("rb") as stream:
            head = stream.read(12)
    except OSError:
        return None
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"RIFF") and head[8:12] == b"WEBP":
        return "image/webp"
    return None


def canonical_root(raw):
    path = Path(raw).expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("Choose a readable local folder.")
    return path


def scan_root(con, root_id, raw_path, generation, progress=None):
    root = canonical_root(raw_path)
    seen = eligible = errors = 0
    stack = [root]
    while stack:
        directory = stack.pop()
        try:
            entries = list(os.scandir(directory))
        except OSError:
            errors += 1
            continue
        for entry in entries:
            seen += 1
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if entry.name.lower() not in DEFAULT_DIRS:
                        stack.append(Path(entry.path))
                    continue
                path = Path(entry.path)
                if any(fnmatch.fnmatch(path.name, p) for p in DEFAULT_PATTERNS):
                    continue
                mime = mime_type(path)
                if not mime:
                    continue
                stat = entry.stat(follow_symlinks=False)
                now = utcnow()
                con.execute("""INSERT INTO photos(root_id,path,device,inode,mime_type,size_bytes,mtime_ns,last_seen_generation,available,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(path) DO UPDATE SET root_id=excluded.root_id,device=excluded.device,inode=excluded.inode,mime_type=excluded.mime_type,size_bytes=excluded.size_bytes,mtime_ns=excluded.mtime_ns,last_seen_generation=excluded.last_seen_generation,available=1,updated_at=excluded.updated_at""",
                    (root_id, str(path), stat.st_dev, stat.st_ino, mime, stat.st_size, stat.st_mtime_ns, generation, now, now))
                eligible += 1
                if eligible % 100 == 0:
                    con.commit()
                    if progress:
                        progress(seen, eligible, errors)
            except OSError:
                errors += 1
    con.execute("UPDATE photos SET available=0 WHERE root_id=? AND COALESCE(last_seen_generation,0)<>?", (root_id, generation))
    con.execute("UPDATE library_roots SET last_completed_scan_at=? WHERE id=?", (utcnow(), root_id))
    con.commit()
    if progress:
        progress(seen, eligible, errors)
    return {"seen": seen, "eligible": eligible, "errors": errors}
