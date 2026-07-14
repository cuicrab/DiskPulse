import os
from pathlib import Path
from typing import List, Optional
from datetime import datetime
from app.models.file_item import FileItem, FileCategory


def resolve_env_path(pattern: str) -> List[Path]:
    pattern = pattern.replace("%LOCALAPPDATA%", os.environ.get("LOCALAPPDATA", ""))
    pattern = pattern.replace("%APPDATA%", os.environ.get("APPDATA", ""))
    pattern = pattern.replace("%TEMP%", os.environ.get("TEMP", ""))
    pattern = pattern.replace("%USERPROFILE%", os.environ.get("USERPROFILE", ""))
    pattern = pattern.replace("%SYSTEMROOT%", os.environ.get("SYSTEMROOT", ""))
    pattern = pattern.replace("%WINDIR%", os.environ.get("WINDIR", ""))
    pattern = pattern.replace("%PROGRAMFILES%", os.environ.get("ProgramFiles", ""))
    pattern = pattern.replace("%PROGRAMFILES(X86)%", os.environ.get("ProgramFiles(x86)", ""))
    pattern = pattern.replace("/*", "/*")
    pattern = pattern.replace("\\", "/")

    if "*" in pattern:
        base = pattern[:pattern.index("*")]
        rest = pattern[pattern.index("*") + 1:]
        base_path = Path(base)
        if base_path.exists():
            results = []
            for child in base_path.iterdir():
                candidate = str(child) + rest
                p = Path(candidate)
                if p.exists():
                    results.append(p)
            return results
    else:
        p = Path(pattern)
        if p.exists():
            return [p]
    return []


def scan_cache_paths(paths: List[str]) -> List[FileItem]:
    items = []
    seen = set()
    for pattern in paths:
        resolved = resolve_env_path(pattern)
        for path in resolved:
            if str(path) in seen:
                continue
            seen.add(str(path))
            try:
                for entry in os.scandir(str(path)):
                    try:
                        if entry.is_file(follow_symlinks=False):
                            stat = entry.stat()
                            items.append(FileItem(
                                path=Path(entry.path),
                                size=stat.st_size,
                                modified_time=datetime.fromtimestamp(stat.st_mtime),
                                accessed_time=datetime.fromtimestamp(stat.st_atime),
                                created_time=datetime.fromtimestamp(stat.st_ctime),
                                category=FileCategory.CACHE,
                            ))
                    except (PermissionError, OSError):
                        continue
            except (PermissionError, OSError):
                continue
    return items
