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
    seen_paths = set()
    for f in files:
        # 同一个路径只算一次：调用方传入的列表若有重复条目
        # （例如缓存扫描与目录扫描重叠），否则会凭空造出"重复文件"
        key = str(f.path)
        if f.size > 0 and key not in seen_paths:
            seen_paths.add(key)
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
            # 约定：组内第一个为保留的"原文件"，其余为判定删除的重复副本。
            # 按修改时间升序（最旧优先）排列，使"可释放空间"与建议删除的集合稳定可复现。
            result.append(sorted(group, key=lambda x: (x.modified_time, str(x.path))))
    return result
