import os
from pathlib import Path


def can_access(path: Path) -> bool:
    try:
        os.listdir(str(path))
        return True
    except (PermissionError, OSError):
        return False


def check_path_permissions(paths: list) -> dict:
    result = {}
    for p in paths:
        path = Path(p)
        if path.exists():
            result[str(path)] = {
                "readable": os.access(str(path), os.R_OK),
                "writable": os.access(str(path), os.W_OK),
            }
    return result
