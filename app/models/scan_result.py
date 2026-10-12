from dataclasses import dataclass, field
from typing import List
from .file_item import FileItem


@dataclass
class ScanResult:
    total_files: int = 0
    total_folders: int = 0
    total_size: int = 0
    duration_seconds: float = 0.0
    large_files: List[FileItem] = field(default_factory=list)
    temp_files: List[FileItem] = field(default_factory=list)
    empty_folders: List[FileItem] = field(default_factory=list)
    duplicate_groups: List[List[FileItem]] = field(default_factory=list)
    # 重复文件比对是否因时间上限/取消而提前结束（结果不完整）
    duplicate_scan_truncated: bool = False
    cache_files: List[FileItem] = field(default_factory=list)
    old_files: List[FileItem] = field(default_factory=list)

    @property
    def total_size_str(self) -> str:
        return FileItem.format_size(self.total_size) if self.total_size > 0 else "0 B"

    @property
    def all_items(self) -> List[FileItem]:
        items = []
        items.extend(self.large_files)
        items.extend(self.temp_files)
        items.extend(self.empty_folders)
        items.extend(self.cache_files)
        items.extend(self.old_files)
        for group in self.duplicate_groups:
            items.extend(group[1:])
        return items
