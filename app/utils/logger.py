import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class CleanupLogger:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self._setup_logger()

    def _setup_logger(self):
        self.logger = logging.getLogger("DiskPulse")
        self.logger.setLevel(logging.INFO)
        log_file = self.log_dir / f"cleanup_{datetime.now().strftime('%Y%m%d')}.log"
        handler = logging.FileHandler(str(log_file), encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)

    def log_cleanup(self, action: str, items: list, total_size: int):
        self.logger.info(
            "操作: %s | 文件数: %d | 释放空间: %.2f MB",
            action,
            len(items),
            total_size / (1024 * 1024),
        )
        for item in items:
            self.logger.info("  删除: %s", item)

    def log_error(self, message: str):
        self.logger.error(message)
