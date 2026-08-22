import os
from pathlib import Path


def _private(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path, 0o700)
    return path


def data_dir() -> Path:
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share"))
    return _private(base / "memory-lane")


def cache_dir() -> Path:
    base = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    return _private(base / "memory-lane" / "previews")


def database_path() -> Path:
    return data_dir() / "memory-lane.sqlite3"


def suggested_pictures() -> str:
    import subprocess
    try:
        value = subprocess.run(["xdg-user-dir", "PICTURES"], capture_output=True, text=True,
                               timeout=2, check=False).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        value = ""
    return str(Path(value).expanduser() if value else Path.home() / "Pictures")
