from PySide6.QtCore import Qt, QRectF, Signal, QEvent
from PySide6.QtGui import QPainter, QColor, QFont, QPen, QBrush, QLinearGradient
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QGridLayout, QSizePolicy,
)
from app.i18n import tr
import psutil


class MiniGauge(QWidget):
    clicked = Signal(str, object, object)

    def __init__(self, drive: str, parent=None):
        super().__init__(parent)
        self._drive = drive
        self._percent = 0
        self._used = 0
        self._total = 0
        self.setMinimumSize(100, 130)
        self.setMaximumSize(160, 180)
        self.setCursor(Qt.PointingHandCursor)
        sizePolicy = QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        self.setSizePolicy(sizePolicy)

    def set_data(self, used: int, total: int):
        self._used = used
        self._total = total
        self._percent = (used / total * 100) if total > 0 else 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        w, h = self.width(), self.height()
        cx, cy = w / 2, h * 0.45

        r = min(w, h * 0.9) * 0.32
        rect = QRectF(cx - r, cy - r, r * 2, r * 2)

        pen = QPen()
        pen.setWidth(max(6, int(r * 0.15)))
        pen.setCapStyle(Qt.RoundCap)

        pen.setColor(QColor("#2d2d2d"))
        painter.setPen(pen)
        painter.drawArc(rect, 1440, 2880)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#00b894"))
        gradient.setColorAt(0.5, QColor("#fdcb6e"))
        gradient.setColorAt(1.0, QColor("#e17055"))
        pen.setBrush(QBrush(gradient))
        painter.setPen(pen)

        span = int(2880 * self._percent / 100)
        painter.drawArc(rect, 1440, span)

        painter.setPen(Qt.NoPen)

        fontSize = max(9, int(r * 0.22))
        painter.setFont(QFont("Segoe UI", fontSize, QFont.Bold))
        painter.setPen(QColor("#dfe6e9"))
        painter.drawText(QRectF(cx - 50, cy - fontSize, 100, fontSize * 2),
                         Qt.AlignCenter, f"{self._percent:.0f}%")

        painter.setFont(QFont("Segoe UI", max(10, int(r * 0.25)), QFont.Bold))
        painter.setPen(QColor("#00b894"))
        painter.drawText(QRectF(0, int(h * 0.78), w, int(h * 0.2)),
                         Qt.AlignCenter, self._drive)

    def mousePressEvent(self, event):
        self.clicked.emit(self._drive, self._used, self._total)
        super().mousePressEvent(event)


class DiskGauge(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(200, 200)
        self.setMaximumSize(400, 400)
        self._percent = 0
        self._used = 0
        self._total = 0
        self._drive = ""

    def set_data(self, drive: str, used: int, total: int):
        self._drive = drive
        self._used = used
        self._total = total
        self._percent = (used / total * 100) if total > 0 else 0
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()
        side = min(width, height) - 20
        rect = QRectF(
            (width - side) / 2,
            (height - side) / 2,
            side,
            side,
        )

        pen = QPen()
        pen.setWidth(12)
        pen.setCapStyle(Qt.RoundCap)

        pen.setColor(QColor("#2d2d2d"))
        painter.setPen(pen)
        painter.drawArc(rect, 1440, 2880)

        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, QColor("#00b894"))
        gradient.setColorAt(0.5, QColor("#fdcb6e"))
        gradient.setColorAt(1.0, QColor("#e17055"))
        pen.setBrush(QBrush(gradient))
        painter.setPen(pen)

        span = int(2880 * self._percent / 100)
        painter.drawArc(rect, 1440, span)

        painter.setPen(Qt.NoPen)
        center = rect.center()

        painter.setFont(QFont("Segoe UI", 12))
        painter.setPen(QColor("#b2bec3"))
        painter.drawText(QRectF(center.x() - 60, center.y() - 45, 120, 20),
                         Qt.AlignCenter, self._drive)

        painter.setFont(QFont("Segoe UI", 28, QFont.Bold))
        painter.setPen(QColor("#ffffff"))
        painter.drawText(QRectF(center.x() - 80, center.y() - 25, 160, 40),
                         Qt.AlignCenter, f"{self._percent:.0f}%")

        painter.setFont(QFont("Segoe UI", 10))
        painter.setPen(QColor("#636e72"))
        used_str = self._format_size(self._used)
        total_str = self._format_size(self._total)
        painter.drawText(QRectF(center.x() - 80, center.y() + 15, 160, 20),
                         Qt.AlignCenter, f"{used_str} / {total_str}")

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class DashboardPage(QFrame):
    start_scan = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._mini_gauges = []
        self._setup_ui()
        self._load_all_drives()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        # 标题
        if hasattr(self, '_title_label'):
            self._title_label.setText(tr("DashboardPage", "DiskPulse"))
        if hasattr(self, '_subtitle_label'):
            self._subtitle_label.setText(tr("DashboardPage", "磁盘管理清理工具"))
        # 扫描按钮
        if hasattr(self, 'scan_btn'):
            self.scan_btn.setText(tr("DashboardPage", "开始扫描"))
        # 重新加载驱动器（会重建标签）
        self._load_all_drives()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(12)

        self._title_label = QLabel(tr("DashboardPage", "DiskPulse"))
        self._title_label.setObjectName("dashboardTitle")
        self._title_label.setAlignment(Qt.AlignCenter)

        self._subtitle_label = QLabel(tr("DashboardPage", "磁盘管理清理工具"))
        self._subtitle_label.setObjectName("dashboardSubtitle")
        self._subtitle_label.setAlignment(Qt.AlignCenter)

        self.gauge = DiskGauge()

        self.drives_grid = QGridLayout()
        self.drives_grid.setSpacing(8)
        self.drives_grid.setAlignment(Qt.AlignCenter)

        self.scan_btn = QPushButton(tr("DashboardPage", "开始扫描"))
        self.scan_btn.setObjectName("scanButton")
        self.scan_btn.setMinimumHeight(48)
        self.scan_btn.setMinimumWidth(200)
        self.scan_btn.setCursor(Qt.PointingHandCursor)
        self.scan_btn.clicked.connect(self.start_scan.emit)

        self.info_label = QLabel()
        self.info_label.setObjectName("diskInfo")
        self.info_label.setAlignment(Qt.AlignCenter)

        layout = self.layout()
        layout.addStretch()
        layout.addWidget(self._title_label)
        layout.addWidget(self._subtitle_label)
        layout.addSpacing(8)
        layout.addLayout(self.drives_grid)
        layout.addSpacing(4)
        layout.addWidget(self.gauge, 0, Qt.AlignCenter)
        layout.addWidget(self.info_label)
        layout.addSpacing(8)
        layout.addWidget(self.scan_btn, 0, Qt.AlignCenter)
        layout.addStretch()

    def _load_all_drives(self):
        for i in reversed(range(self.drives_grid.count())):
            item = self.drives_grid.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

        self._mini_gauges.clear()
        selected_drive = ""
        selected_used = 0
        selected_total = 0

        import string
        col = 0
        row = 0
        max_cols = 5
        for letter in string.ascii_uppercase:
            path = f"{letter}:/"
            if not __import__("pathlib").Path(path).exists():
                continue
            try:
                usage = psutil.disk_usage(path)
                gauge = MiniGauge(f"{letter}:")
                gauge.set_data(usage.used, usage.total)
                gauge.clicked.connect(self._on_drive_selected)
                self.drives_grid.addWidget(gauge, row, col, Qt.AlignCenter)
                self._mini_gauges.append(gauge)

                if not selected_drive:
                    selected_drive = f"{letter}:"
                    selected_used = usage.used
                    selected_total = usage.total

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            except Exception:
                continue

        if selected_drive:
            self.gauge.set_data(selected_drive, selected_used, selected_total)
            self._update_info(selected_drive, selected_used, selected_total)

    def _on_drive_selected(self, drive: str, used: int, total: int):
        self.gauge.set_data(drive, used, total)
        self._update_info(drive, used, total)

    def _update_info(self, drive: str, used: int, total: int):
        free = total - used
        used_str = DiskGauge._format_size(used)
        total_str = DiskGauge._format_size(total)
        free_str = DiskGauge._format_size(free)
        self.info_label.setText(
            f"{drive}  已用 {used_str}  /  共 {total_str}  /  可用 {free_str}"
        )

    def refresh(self):
        self._load_all_drives()
