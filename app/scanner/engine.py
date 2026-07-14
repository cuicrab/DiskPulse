import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Set
from PySide6.QtCore import QThread, Signal

from app.models.file_item import FileItem, FileCategory
from app.models.scan_result import ScanResult
from app.models.settings import AppSettings


class ScanEngine(QThread):
    progress = Signal(str)
    progress_value = Signal(int, int)
    finished_signal = Signal(ScanResult)
    file_found = Signal(FileItem)

    def __init__(self, settings: AppSettings, parent=None):
        super().__init__(parent)
        self.settings = settings
        self._is_running = True
        self._all_files: List[FileItem] = []
        self._seen_inodes: Set[str] = set()

    def stop(self):
        self._is_running = False

    def run(self):
        result = ScanResult()
        start_time = time.time()
        self._all_files = []
        self._seen_inodes.clear()

        for path_str in self.settings.scan_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            self.progress.emit(f"正在扫描: {path}")
            self._scan_directory(path, result)

        elapsed = time.time() - start_time
        result.duration_seconds = elapsed

        self.progress.emit("扫描完成，正在分析大文件...")
        self._analyze_large_files(result)

        self.progress.emit("正在查找临时文件...")
        self._find_temp_files(result)

        self.progress.emit("正在检查空文件夹...")
        for path_str in self.settings.scan_paths:
            root_path = Path(path_str)
            if root_path.exists():
                self._find_empty_folders(root_path, result)

        self.progress.emit("正在查找旧文件...")
        self._find_old_files(result)

        result.total_size = sum(item.size for item in self._all_files)
        self.finished_signal.emit(result)

    def _scan_directory(self, path: Path, result: ScanResult):
        try:
            for entry in os.scandir(str(path)):
                if not self._is_running:
                    return
                try:
                    stat = entry.stat(follow_symlinks=False)
                    if entry.is_dir(follow_symlinks=False):
                        result.total_folders += 1
                        self._scan_directory(Path(entry.path), result)
                    else:
                        result.total_files += 1
                        item = FileItem(
                            path=Path(entry.path),
                            size=stat.st_size,
                            modified_time=datetime.fromtimestamp(stat.st_mtime),
                            accessed_time=datetime.fromtimestamp(stat.st_atime),
                            created_time=datetime.fromtimestamp(stat.st_ctime),
                            is_dir=False,
                        )
                        self._all_files.append(item)
                except (PermissionError, OSError):
                    continue
        except (PermissionError, OSError):
            self.progress.emit(f"权限不足，跳过: {path}")

    def _analyze_large_files(self, result: ScanResult):
        min_size = self.settings.min_large_file_mb * 1024 * 1024
        large = [f for f in self._all_files if f.size >= min_size]
        large.sort(key=lambda x: x.size, reverse=True)
        for f in large[:500]:
            f.category = FileCategory.LARGE_FILE
        result.large_files = large[:500]

    def _find_temp_files(self, result: ScanResult):
        temp_exts = {".tmp", ".temp", ".log", ".cache", ".bak", ".old"}
        temps = [f for f in self._all_files if f.path.suffix.lower() in temp_exts]
        for f in temps:
            f.category = FileCategory.TEMP_FILE
        result.temp_files = temps

    def _find_old_files(self, result: ScanResult):
        cutoff = datetime.now() - timedelta(days=self.settings.old_file_days)
        min_size = 50 * 1024 * 1024
        old = [
            f for f in self._all_files
            if f.size >= min_size and f.accessed_time < cutoff
        ]
        for f in old:
            f.category = FileCategory.OLD_FILE
        result.old_files = old

    def _find_empty_folders(self, root: Path, result: ScanResult):
        empty_dirs: List[FileItem] = []
        try:
            for dirpath, dirnames, filenames in os.walk(str(root)):
                if not self._is_running:
                    return
                if not dirnames and not filenames:
                    empty_dirs.append(FileItem(
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
        result.empty_folders = empty_dirs
