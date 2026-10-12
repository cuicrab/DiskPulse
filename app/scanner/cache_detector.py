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


def find_files_shallow(directory: Path) -> List[Path]:
    """列出一层文件：只枚举目录的直接子文件，不递归进子目录。

    缓存/临时目录（Chrome Cache、%TEMP% 等）的文件都直接位于目录内，
    只扫一层即可，避免对大目录做整树遍历。
    """
    found: List[Path] = []
    try:
        for entry in os.scandir(str(directory)):
            try:
                if entry.is_file(follow_symlinks=False):
                    found.append(Path(entry.path))
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return found


def scan_cache_paths(paths: List[str]) -> List[FileItem]:
    items = []
    seen = set()
    for pattern in paths:
        resolved = resolve_env_path(pattern)
        for path in resolved:
            if str(path) in seen:
                continue
            seen.add(str(path))
            for entry in find_files_shallow(path):
                try:
                    stat = entry.stat()
                    items.append(FileItem(
                        path=entry,
                        size=stat.st_size,
                        modified_time=datetime.fromtimestamp(stat.st_mtime),
                        accessed_time=datetime.fromtimestamp(stat.st_atime),
                        created_time=datetime.fromtimestamp(stat.st_ctime),
                        category=FileCategory.CACHE,
                    ))
                except (PermissionError, OSError):
                    continue
    return items
