"""Linux descriptor-based validation of the SQLite storage boundary."""

import os
import sqlite3
import stat
from contextlib import contextmanager
from pathlib import Path


class UnsafeStorageError(OSError):
    pass


@contextmanager
def private_directory(path):
    """Hold a checked private state/cache directory open for relative I/O."""
    fd = _open_directory(path)
    try:
        yield fd
    finally:
        os.close(fd)


def check_private_file(directory_fd, name):
    return _check_file(directory_fd, name)


def _check_directory(fd, private=False):
    info = os.fstat(fd)
    if not stat.S_ISDIR(info.st_mode):
        raise UnsafeStorageError("Private storage must be a directory.")
    if private:
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise UnsafeStorageError("Storage directory must be owned by you and private (0700).")
    elif info.st_uid not in (0, os.geteuid()) or (
        info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX
    ):
        raise UnsafeStorageError("Storage ancestor directory has unsafe ownership or permissions.")


def _open_directory(path):
    # Never resolve() first: that would hide symlinks from O_NOFOLLOW.
    parts = Path(path).absolute().parts
    if ".." in parts:
        raise UnsafeStorageError("Database path must not contain parent traversal.")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC
    fd = os.open(parts[0], flags)
    try:
        _check_directory(fd)
        for part in parts[1:]:
            try:
                os.mkdir(part, mode=0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
            _check_directory(fd)
        _check_directory(fd, private=True)
        return fd
    except BaseException:
        os.close(fd)
        raise


def _check_file(directory_fd, name, required=False):
    # O_PATH inspects even a FIFO without opening it for I/O. Unlike a normal
    # file descriptor, closing it does not release this process's SQLite locks.
    try:
        fd = os.open(name, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=directory_fd)
    except FileNotFoundError:
        if required:
            raise
        return None
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077):
            raise UnsafeStorageError("Stored files must be private, owned regular files without links.")
        return info.st_dev, info.st_ino
    finally:
        os.close(fd)


@contextmanager
def _database_location(path):
    target = Path(path)
    directory_fd = _open_directory(target.parent)
    try:
        # Check sidecars before creating anything or asking SQLite to recover a
        # journal. Never chmod, truncate, delete, or follow a suspicious entry.
        for suffix in ("-journal", "-wal", "-shm"):
            _check_file(directory_fd, target.name + suffix)
        if _check_file(directory_fd, target.name) is None:
            try:
                fd = os.open(target.name, os.O_RDWR | os.O_CREAT | os.O_EXCL
                             | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=directory_fd)
            except FileExistsError:
                pass  # Another legitimate connection may have created it.
            else:
                os.close(fd)
        identity = _check_file(directory_fd, target.name, required=True)
        # Anchor SQLite's initial lookup to the checked directory, not the
        # original path. SQLite canonicalizes this path for its sidecars; the
        # checked ancestor ownership/permissions protect that canonical path.
        yield f"/proc/self/fd/{directory_fd}/{target.name}", identity
    finally:
        os.close(directory_fd)


def open_private_database(path):
    """Return an identity-checked connection; the caller owns its lifetime."""
    with _database_location(path) as (location, identity):
        con = sqlite3.connect(location, timeout=3)
        try:
            # Verify SQLite's canonical filename before any migration or WAL
            # setup. The private directory excludes other-user replacement.
            actual = con.execute("PRAGMA database_list").fetchone()[2]
            info = os.stat(actual, follow_symlinks=False)
            if (info.st_dev, info.st_ino) != identity:
                raise UnsafeStorageError("Database changed while opening it.")
            return con
        except BaseException:
            con.close()
            raise
