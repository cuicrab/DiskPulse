import os
from pathlib import Path
from typing import List
from datetime import datetime
from app.models.file_item import FileItem, FileCategory


def find_temp_files(directory: Path) -> List[FileItem]:
    temp_exts = {".tmp", ".temp", ".log", ".cache", ".bak", ".old"}
    result = []
    try:
        for entry in os.scandir(str(directory)):
            try:
                if entry.is_file(follow_symlinks=False):
                    ext = Path(entry.path).suffix.lower()
                    if ext in temp_exts:
                        stat = entry.stat()
                        result.append(FileItem(
                            path=Path(entry.path),
                            size=stat.st_size,
                            modified_time=datetime.fromtimestamp(stat.st_mtime),
                            accessed_time=datetime.fromtimestamp(stat.st_atime),
                            created_time=datetime.fromtimestamp(stat.st_ctime),
                            category=FileCategory.TEMP_FILE,
                        ))
            except (PermissionError, OSError):
                continue
    except (PermissionError, OSError):
        pass
    return result
