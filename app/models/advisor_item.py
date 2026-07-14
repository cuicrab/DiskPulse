from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class AdvisorItem:
    name: str
    description: str
    importance: int
    importance_label: str
    hint: str
    size_bytes: int = 0
    file_count: int = 0
    files: List[Path] = field(default_factory=list)

    @property
    def size_str(self) -> str:
        size = self.size_bytes
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"
