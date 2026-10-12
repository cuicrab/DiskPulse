import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class CleanupLogger:
    _configured = False

    def __init__(self, log_dir: Optional[str] = None):
        self.log_dir = Path(log_dir) if log_dir else Path("logs")
        self.logger = logging.getLogger("DiskPulse")
        self.logger.setLevel(logging.INFO)
        # 同一 logger 只挂一次 handler：MainWindow 与 AdvisorActions 都会构造本类，
        # 重复挂载会让每条日志写两遍
        if not CleanupLogger._configured:
            CleanupLogger._configured = True
            self._setup_logger()

    def _setup_logger(self):
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            log_file = self.log_dir / f"cleanup_{datetime.now().strftime('%Y%m%d')}.log"
            handler = logging.FileHandler(str(log_file), encoding="utf-8")
            formatter = logging.Formatter(
                "%(asctime)s | %(levelname)-8s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
        except OSError as e:
            # 日志目录不可写（只读安装目录、权限不足等）不应阻断程序启动
            self.logger.addHandler(logging.NullHandler())
            self.logger.warning("无法写入日志文件，本次运行不记录操作日志: %s", e)

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
