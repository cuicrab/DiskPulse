from dataclasses import dataclass, field
from typing import List
import json
import os
from pathlib import Path

from app.utils import resource_path


@dataclass
class AppSettings:
    min_large_file_mb: int = 100
    old_file_days: int = 90
    scan_paths: List[str] = field(default_factory=lambda: ["C:/"])
    exclude_paths: List[str] = field(default_factory=list)
    theme: str = "dark"
    language: str = "zh_CN"
    use_recycle_bin: bool = True
    confirm_before_delete: bool = True
    enable_duplicate_scan: bool = True
    hash_algorithm: str = "md5"

    # Session state
    window_width: int = 1100
    window_height: int = 720
    splitter_sizes: List[str] = field(default_factory=lambda: [200, 900])
    last_page: str = "dashboard"

    # File list state
    selected_file_paths: List[str] = field(default_factory=list)
    file_list_sort_column: int = 2
    file_list_sort_order: int = 2  # Qt.DescendingOrder
    file_list_filter_index: int = 0

    # Last scan state
    last_scan_paths: List[str] = field(default_factory=list)
    last_selected_files: List[str] = field(default_factory=list)

    @classmethod
    def load(cls, path: str = "settings.json") -> "AppSettings":
        paths_to_try = [path]
        if not os.path.isabs(path):
            paths_to_try.append(resource_path(path))
        for p in paths_to_try:
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
                return cls(**data)
            except (FileNotFoundError, json.JSONDecodeError):
                continue
        return cls()

    def save(self, path: str = "settings.json") -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)