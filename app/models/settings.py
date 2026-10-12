from dataclasses import dataclass, field
from typing import List
import json
import logging
import os
from pathlib import Path

from app.utils import resource_path


def user_config_dir() -> str:
    """可写的用户配置目录（安装目录只读时的回退位置）。"""
    base = os.environ.get("APPDATA")
    if not base:
        base = str(Path.home() / ".config")
    return os.path.join(base, "DiskPulse")


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
    # 重复文件比对限制：小于该体积的文件不参与；超过时间预算即停止并返回已确认结果
    duplicate_min_size_mb: int = 8
    duplicate_scan_budget_seconds: int = 60

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
        # 优先用户配置目录（save 回退时会写到这里），
        # 其次是仓库/安装目录，最后是打包后的只读资源目录
        paths_to_try = []
        if not os.path.isabs(path):
            paths_to_try.append(os.path.join(user_config_dir(), path))
        paths_to_try.extend([path, resource_path(path)])
        for p in paths_to_try:
            try:
                with open(p, encoding="utf-8") as f:
                    data = json.load(f)
            except (OSError, ValueError):
                continue
            # 只取本 dataclass 认识的键：配置文件里多一个未知字段不能让程序启动失败
            known = cls.__dataclass_fields__
            return cls(**{k: v for k, v in data.items() if k in known})
        return cls()

    def save(self, path: str = "settings.json") -> None:
        for p in (path, os.path.join(user_config_dir(), path)):
            try:
                parent = os.path.dirname(os.path.abspath(p))
                os.makedirs(parent, exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(self.__dict__, f, ensure_ascii=False, indent=2)
                return
            except OSError:
                continue
        # 两个位置都不可写：不能因为保存设置让关窗流程崩溃
        logging.getLogger("DiskPulse").warning("无法保存设置，本次会话状态不会保留")