from dataclasses import dataclass, field
from typing import List
import json
from pathlib import Path


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

    # Session state
    window_width: int = 1100
    window_height: int = 720
    splitter_sizes: List[int] = field(default_factory=lambda: [200, 900])
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
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return cls(**data)
        except (FileNotFoundError, json.JSONDecodeError):
            return cls()

    def save(self, path: str = "settings.json") -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.__dict__, f, ensure_ascii=False, indent=2)