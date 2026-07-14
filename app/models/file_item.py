from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime
from enum import Enum, auto
from typing import List, Optional


class FileCategory(Enum):
    LARGE_FILE = auto()
    DUPLICATE = auto()
    TEMP_FILE = auto()
    EMPTY_FOLDER = auto()
    CACHE = auto()
    RECYCLER = auto()
    OLD_FILE = auto()


@dataclass
class FileItem:
    path: Path
    size: int
    modified_time: datetime
    accessed_time: datetime
    created_time: datetime
    category: FileCategory = FileCategory.LARGE_FILE
    categories: List[FileCategory] = field(default_factory=list)
    is_dir: bool = False
    hash: str = ""
    group_id: str = ""

    @property
    def all_categories(self) -> List[FileCategory]:
        if self.categories:
            return self.categories
        return [self.category]

    @property
    def size_str(self) -> str:
        return self._format_size(self.size)

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def parent_path(self) -> str:
        return str(self.path.parent)

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    @staticmethod
    def format_size(size: int) -> str:
        return FileItem._format_size(size)
