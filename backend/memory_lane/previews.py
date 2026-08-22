import hashlib
import os
import subprocess
import tempfile
from pathlib import Path

from .paths import cache_dir


def ensure_preview(photo):
    source = Path(photo["path"])
    stat = source.stat()
    key = hashlib.blake2b(f"{source}\0{stat.st_size}\0{stat.st_mtime_ns}".encode(), digest_size=20).hexdigest()
    target = cache_dir() / f"{key}.jpg"
    if target.exists():
        return str(target)
    fd, temporary = tempfile.mkstemp(prefix="preview-", suffix=".jpg", dir=cache_dir())
    os.close(fd)
    env = dict(os.environ)
    env["VIPS_CONCURRENCY"] = "1"
    try:
        subprocess.run(["vipsthumbnail", str(source), "--size", "1600x1200", "--path", temporary + "[strip]"],
                       env=env, timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        os.replace(temporary, target)
        os.chmod(target, 0o600)
        return str(target)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
