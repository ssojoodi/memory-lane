import os
from pathlib import Path


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    # Database creation validates and creates this directory via descriptors.
    return base / "memory-lane"


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return base / "memory-lane" / "previews"


def database_path() -> Path:
    return data_dir() / "memory-lane.sqlite3"


def suggested_pictures() -> str:
    import subprocess
    from .process_output import bounded_output
    try:
        value = bounded_output(["xdg-user-dir", "PICTURES"], timeout=2).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        value = ""
    return str(Path(value).expanduser() if value else Path.home() / "Pictures")
