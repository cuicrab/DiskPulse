import os
import shutil
from pathlib import Path
from typing import List, Optional
from send2trash import send2trash


def delete_to_recycle_bin(paths: List[Path]) -> List[Path]:
    failed = []
    for p in paths:
        try:
            send2trash(str(p))
        except Exception:
            failed.append(p)
    return failed


def delete_permanently(paths: List[Path]) -> List[Path]:
    failed = []
    for p in paths:
        try:
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink()
        except Exception:
            failed.append(p)
    return failed


def delete_paths(paths: List[Path], use_recycle_bin: bool = True) -> List[Path]:
    if use_recycle_bin:
        return delete_to_recycle_bin(paths)
    return delete_permanently(paths)


def get_folder_size(path: Path) -> int:
    total = 0
    try:
        for entry in os.scandir(str(path)):
            try:
                if entry.is_dir(follow_symlinks=False):
                    total += get_folder_size(Path(entry.path))
                else:
                    total += entry.stat(follow_symlinks=False).st_size
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return total


def is_admin() -> bool:
    import ctypes
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def request_admin() -> None:
    import sys
    import ctypes
    script_path = sys.argv[0]
    ctypes.windll.shell32.ShellExecuteW(
        None, "runas", sys.executable, f'"{script_path}"', None, 1
    )
