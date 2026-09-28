import fnmatch
import os
from pathlib import Path

from .database import utcnow
from .photo_files import photo_file

EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
DEFAULT_DIRS = {"screenshots", "screenshot", "downloads", "thumbnails", ".thumbnails", "cache", ".cache", "trash", ".trash"}
DEFAULT_PATTERNS = ("Screenshot_*", "screenshot-*", "Screenshot *", "screenshot_*")


def mime_type(path):
    if path.suffix.lower() not in EXTENSIONS:
        return None
    try:
        with photo_file(path) as stream:
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


def index_photo(con, root_id, path, generation):
    mime = mime_type(path)
    if not mime or path.is_symlink():
        raise ValueError("Choose a supported JPEG, PNG, or WebP photo (not a link).")
    with photo_file(path) as stream:
        info = os.fstat(stream.fileno())
    is_new = con.execute("SELECT 1 FROM photos WHERE path=?", (str(path),)).fetchone() is None
    now = utcnow()
    con.execute("""INSERT INTO photos(root_id,path,device,inode,mime_type,size_bytes,mtime_ns,last_seen_generation,available,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(path) DO UPDATE SET root_id=excluded.root_id,device=excluded.device,inode=excluded.inode,mime_type=excluded.mime_type,size_bytes=excluded.size_bytes,mtime_ns=excluded.mtime_ns,last_seen_generation=excluded.last_seen_generation,available=1,updated_at=excluded.updated_at""",
        (root_id, str(path), info.st_dev, info.st_ino, mime, info.st_size, info.st_mtime_ns, generation, now, now))
    return is_new


def open_photo(con, raw_path):
    path = Path(raw_path).expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Choose a photo without symbolic links in its path.")
    path = path.resolve(strict=True)
    roots = con.execute("SELECT id,path FROM library_roots WHERE enabled=1 ORDER BY length(path) DESC").fetchall()
    root = next((row for row in roots if path.is_relative_to(Path(row["path"]))), None)
    if root is None:
        raise ValueError("Choose a photo inside one of your approved photo folders.")
    relative = path.relative_to(root["path"])
    if (any(part.lower() in DEFAULT_DIRS for part in relative.parts[:-1])
            or any(fnmatch.fnmatch(path.name, pattern) for pattern in DEFAULT_PATTERNS)):
        raise ValueError("This file is excluded by your photo-library filters.")
    index_photo(con, root["id"], path, 0)
    con.commit()
    return con.execute("SELECT * FROM photos WHERE path=?", (str(path),)).fetchone()


def scan_root(con, root_id, raw_path, generation, progress=None):
    root = Path(raw_path).absolute()
    if any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError("The approved photo folder now contains a symbolic link.")
    if not root.is_dir():
        raise ValueError("The approved photo folder is unavailable.")
    seen = eligible = errors = added = 0
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
                added += index_photo(con, root_id, path, generation)
                eligible += 1
                if eligible % 100 == 0:
                    con.commit()
                    if progress:
                        progress(seen, eligible, errors)
            except (OSError, ValueError):
                errors += 1
    con.execute("UPDATE photos SET available=0 WHERE root_id=? AND COALESCE(last_seen_generation,0)<>?", (root_id, generation))
    con.execute("UPDATE library_roots SET last_completed_scan_at=? WHERE id=?", (utcnow(), root_id))
    con.commit()
    if progress:
        progress(seen, eligible, errors)
    return {"seen": seen, "eligible": eligible, "errors": errors, "added": added}
