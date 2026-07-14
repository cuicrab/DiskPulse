import os
from typing import List
from pathlib import Path
from datetime import datetime
from app.models.file_item import FileItem, FileCategory


def find_empty_folders(root: Path) -> List[FileItem]:
    result = []
    try:
        for dirpath, dirnames, filenames in os.walk(str(root)):
            if not dirnames and not filenames:
                result.append(FileItem(
                    path=Path(dirpath),
                    size=0,
                    modified_time=datetime.fromtimestamp(os.path.getmtime(dirpath)),
                    accessed_time=datetime.fromtimestamp(os.path.getatime(dirpath)),
                    created_time=datetime.fromtimestamp(os.path.getctime(dirpath)),
                    category=FileCategory.EMPTY_FOLDER,
                    is_dir=True,
                ))
    except (PermissionError, OSError):
        pass
    return result
