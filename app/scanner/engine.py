import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Optional, Set
from PySide6.QtCore import QThread, Signal

from app.models.file_item import FileItem, FileCategory
from app.models.scan_result import ScanResult
from app.models.settings import AppSettings
from app.scanner.cache_detector import scan_cache_paths
from app.scanner.duplicate import find_duplicates


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
        self._denied_count = 0

    def stop(self):
        self._is_running = False

    def _should_stop(self) -> bool:
        return not self._is_running

    def run(self):
        result = ScanResult()
        start_time = time.time()
        self._all_files = []
        self._seen_inodes.clear()
        self._denied_count = 0

        for path_str in self.settings.scan_paths:
            path = Path(path_str)
            if not path.exists():
                continue
            self.progress.emit(f"正在扫描: {path}")
            self._scan_directory(path, result)

        # 权限不足的目录可能成百上千个，逐条上报会把状态栏刷屏，
        # 这里只在结束时汇总一次
        if self._denied_count:
            self.progress.emit(f"扫描完成，{self._denied_count} 个目录无访问权限已跳过")

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

        self.progress.emit("正在查找缓存文件...")
        self._find_cache_files(result)

        if self.settings.enable_duplicate_scan and self._is_running:
            self._find_duplicate_files(result)

        result.total_size = sum(item.size for item in self._all_files)
        self.finished_signal.emit(result)

    def _find_cache_files(self, result: ScanResult):
        """扫描 rules.yaml 中的缓存/临时类规则命中的目录。"""
        patterns = self._load_cache_patterns()
        if not patterns:
            return
        found = scan_cache_paths(patterns)
        if not self._is_running:
            return
        for f in found:
            f.category = FileCategory.CACHE
        result.cache_files = found
        # 注意：不并入 _all_files。缓存目录可能与扫描路径重叠，
        # 同一个文件被登记两次会让重复检测产生假阳性。

    @staticmethod
    def _load_cache_patterns() -> List[str]:
        """只取缓存/临时类规则的路径，排除"最近使用/预读"这类非缓存规则。"""
        import yaml
        from app.utils import resource_path

        try:
            with open(resource_path("rules.yaml"), encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except (OSError, yaml.YAMLError):
            return []

        skip = {"recent_files", "prefetch", "recycler"}
        patterns: List[str] = []
        for rule in data.get("rules", []):
            if rule.get("name") in skip:
                continue
            patterns.extend(rule.get("paths", []))
        return patterns

    def _find_duplicate_files(self, result: ScanResult):
        """基于内容哈希找出重复文件；组内第一个为保留项，其余为可删除副本。

        受 min_size / time_budget 限制，并支持随时取消，避免整盘比对无休止读盘。
        """
        groups, truncated = find_duplicates(
            self._all_files,
            algorithm=self.settings.hash_algorithm,
            min_size=self.settings.duplicate_min_size_mb * 1024 * 1024,
            time_budget_seconds=self.settings.duplicate_scan_budget_seconds,
            should_stop=self._should_stop,
            on_progress=self.progress.emit,
        )
        result.duplicate_groups = groups
        result.duplicate_scan_truncated = truncated

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
            # 只计数，由 run() 在扫描结束后汇总上报一次，避免状态栏被刷屏
            self._denied_count += 1

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
