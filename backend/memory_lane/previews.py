import hashlib
import os
import subprocess
import uuid
from pathlib import Path

from .paths import cache_dir
from .photo_files import photo_file
from .storage import check_private_file, private_directory


def ensure_preview(photo):
    source = Path(photo["path"])
    with photo_file(source) as stream, private_directory(cache_dir()) as directory:
        info = os.fstat(stream.fileno())
        key = hashlib.blake2b(
            f"{source}\0{info.st_dev}\0{info.st_ino}\0{info.st_size}\0{info.st_mtime_ns}".encode(),
            digest_size=20,
        ).hexdigest()
        name = f"{key}.jpg"
        target = cache_dir() / name
        if check_private_file(directory, name) is not None:
            return str(target)
        temporary = f"preview-{uuid.uuid4().hex}.jpg"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                     0o600, dir_fd=directory)
        os.close(fd)
        try:
            subprocess.run(
                ["vipsthumbnail", f"/proc/self/fd/{stream.fileno()}", "--size", "1600x1200",
                 "--path", f"/proc/self/fd/{directory}/{temporary}[strip]"],
                pass_fds=(stream.fileno(), directory), env={**os.environ, "VIPS_CONCURRENCY": "1"},
                timeout=20, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
            check_private_file(directory, temporary)
            check_private_file(directory, name)
            os.replace(temporary, name, src_dir_fd=directory, dst_dir_fd=directory)
            return str(target)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass
