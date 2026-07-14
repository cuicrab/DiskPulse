from pathlib import Path
from typing import List, Tuple
from app.utils.file_ops import delete_paths, delete_to_recycle_bin
from app.utils.logger import CleanupLogger
from app.scanner.recycler import empty_recycle_bin


class AdvisorActions:
    def __init__(self):
        self.logger = CleanupLogger()

    def clean_items(self, items: List[Path], use_recycle_bin: bool = True) -> Tuple[int, int]:
        total_size = 0
        total_count = 0
        for item in items:
            try:
                if item.exists():
                    total_size += item.stat().st_size if item.is_file() else 0
                    total_count += 1
            except (PermissionError, OSError):
                continue

        failed = delete_paths(items, use_recycle_bin)
        success_count = total_count - len(failed)
        self.logger.log_cleanup("批量清理", items, total_size)
        return success_count, len(failed)

    def empty_recycle_bin(self) -> bool:
        if empty_recycle_bin():
            self.logger.log_cleanup("清空回收站", [], 0)
            return True
        return False
