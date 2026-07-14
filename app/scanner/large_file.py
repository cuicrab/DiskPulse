from typing import List
from pathlib import Path
from app.models.file_item import FileItem, FileCategory
from app.models.settings import AppSettings


def find_large_files(files: List[FileItem], settings: AppSettings) -> List[FileItem]:
    min_size = settings.min_large_file_mb * 1024 * 1024
    large = [f for f in files if f.size >= min_size]
    large.sort(key=lambda x: x.size, reverse=True)
    for f in large:
        f.category = FileCategory.LARGE_FILE
    return large[:500]
