import hashlib
from typing import List, Dict
from pathlib import Path
from collections import defaultdict
from app.models.file_item import FileItem, FileCategory


def hash_file(path: Path, chunk_size: int = 8192) -> str:
    h = hashlib.md5()
    try:
        with open(str(path), "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError):
        return ""


def find_duplicates(files: List[FileItem]) -> List[List[FileItem]]:
    size_map: Dict[int, List[FileItem]] = defaultdict(list)
    for f in files:
        if f.size > 0:
            size_map[f.size].append(f)

    hash_map: Dict[str, List[FileItem]] = defaultdict(list)
    for size_group in size_map.values():
        if len(size_group) < 2:
            continue
        for f in size_group:
            f_hash = hash_file(f.path)
            if f_hash:
                hash_map[f_hash].append(f)

    result = []
    for group in hash_map.values():
        if len(group) >= 2:
            for f in group:
                f.category = FileCategory.DUPLICATE
            result.append(group)
    return result
