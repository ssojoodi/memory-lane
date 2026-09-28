"""Open photo files without following links or blocking on special files."""

import os
import stat
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def photo_file(path):
    parts = Path(path).absolute().parts
    if ".." in parts:
        raise OSError("Photo paths must not contain parent traversal.")
    directory = os.open(parts[0], os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    handle = None
    try:
        for part in parts[1:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                            dir_fd=directory)
            os.close(directory)
            directory = child
        # O_PATH inspects a device/FIFO without opening it for I/O.
        handle = os.open(parts[-1], os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory)
        if not stat.S_ISREG(os.fstat(handle).st_mode):
            raise OSError("The photo must be a regular file, not a link or special file.")
        fd = os.open(f"/proc/self/fd/{handle}", os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
        with os.fdopen(fd, "rb") as stream:
            yield stream
    finally:
        if handle is not None:
            os.close(handle)
        os.close(directory)
