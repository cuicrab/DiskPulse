import sys
from pathlib import Path
from PySide6.QtCore import Qt, QSize, QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QStackedWidget, QPushButton, QLabel, QFrame,
    QMessageBox, QProgressBar, QCheckBox, QDialog,
    QFileDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
    QSplitter, QComboBox,
)
from PySide6.QtGui import QAction

from app.models.settings import AppSettings
from app.models.file_item import FileItem
from app.scanner.engine import ScanEngine
from app.advisor.engine import AdvisorEngine
from app.advisor.actions import AdvisorActions
from app.ui.dashboard import DashboardPage
from app.ui.file_list import FileListPanel
from app.ui.advisor_panel import AdvisorPanel
from app.utils.logger import CleanupLogger
from app.utils.file_ops import is_admin, request_admin
from app.i18n import get_translation_manager, tr


def get_available_drives() -> list:
    import string
    drives = []
    for letter in string.ascii_uppercase:
        path = f"{letter}:/"
        if Path(path).exists():
            try:
                usage = __import__("psutil").disk_usage(path)
                drives.append((letter, path, usage))
            except Exception:
                drives.append((letter, path, None))
    return drives


class DriveSelectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("MainWindow", "选择扫描目标"))
        self.setMinimumWidth(420)
        self.selected_paths = []
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        title = QLabel(tr("MainWindow", "请选择要扫描的磁盘或目录："))
        title.setObjectName("dialogTitle")
        layout.addWidget(title)

        self.drive_list = QListWidget()
        self.drive_list.setObjectName("driveList")

        drives = get_available_drives()
        for letter, path, usage in drives:
            if usage:
                total = self._format_size(usage.total)
                used = self._format_size(usage.used)
                text = f"{letter}:\\    {used} / {total}    ({usage.percent:.0f}%)"
            else:
                text = f"{letter}:\\"
            item = QListWidgetItem(f"  {text}")
            item.setData(Qt.UserRole, path)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            item.setSizeHint(QSize(0, 36))
            self.drive_list.addItem(item)

        layout.addWidget(self.drive_list)

        btn_layout = QHBoxLayout()

        self.custom_dir_btn = QPushButton(tr("MainWindow", "选择自定义目录"))
        self.custom_dir_btn.setObjectName("customDirButton")
        self.custom_dir_btn.clicked.connect(self._select_custom_dir)
        btn_layout.addWidget(self.custom_dir_btn)

        btn_layout.addStretch()

        self.select_all_btn = QPushButton(tr("MainWindow", "全选"))
        self.select_all_btn.clicked.connect(lambda: self._toggle_all(True))
        btn_layout.addWidget(self.select_all_btn)

        self.clear_all_btn = QPushButton(tr("MainWindow", "取消全选"))
        self.clear_all_btn.clicked.connect(lambda: self._toggle_all(False))
        btn_layout.addWidget(self.clear_all_btn)

        layout.addLayout(btn_layout)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _toggle_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for i in range(self.drive_list.count()):
            self.drive_list.item(i).setCheckState(state)

    def _select_custom_dir(self):
        dir_path = QFileDialog.getExistingDirectory(
            self, tr("MainWindow", "选择要扫描的目录"), "C:/"
        )
        if dir_path:
            item = QListWidgetItem(f"  📁 {dir_path}")
            item.setData(Qt.UserRole, dir_path)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            self.drive_list.addItem(item)

    def _accept(self):
        paths = []
        for i in range(self.drive_list.count()):
            item = self.drive_list.item(i)
            if item.checkState() == Qt.Checked:
                path = item.data(Qt.UserRole)
                if path not in paths:
                    paths.append(path)
        if not paths:
            QMessageBox.warning(self, tr("MainWindow", "提示"), tr("MainWindow", "请至少选择一个磁盘或目录。"))
            return
        self.selected_paths = paths
        self.accept()

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = AppSettings.load()
        self.advisor_engine = AdvisorEngine()
        self.advisor_actions = AdvisorActions()
        self.logger = CleanupLogger()
        self.scan_engine: ScanEngine = None
        self._scan_result = None
        self._trans_mgr = get_translation_manager()

        self._setup_ui()
        self._check_admin()
        
        # Restore window state after UI is set up
        self.resize(self.settings.window_width, self.settings.window_height)
        self._restore_session()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        """热切换时更新所有 UI 文本"""
        # 窗口标题
        self.setWindowTitle(tr("MainWindow", "DiskPulse - 磁盘管理清理工具"))
        
        # 侧边栏导航按钮
        if hasattr(self, 'nav_buttons'):
            nav_texts = {
                "dashboard": tr("MainWindow", "📊  仪表盘"),
                "scan": tr("MainWindow", "🔍  扫描结果"),
                "advisor": tr("MainWindow", "🧠  清理建议"),
            }
            for key, btn in self.nav_buttons.items():
                if key in nav_texts:
                    btn.setText(nav_texts[key])
                    
        # 语言选择器
        if hasattr(self, 'lang_combo'):
            tm = get_translation_manager()
            current_code = self.lang_combo.currentData()
            self.lang_combo.blockSignals(True)
            self.lang_combo.clear()
            for code, name in tm.available_languages().items():
                self.lang_combo.addItem(name, code)
            # 恢复选中
            idx = self.lang_combo.findData(self._trans_mgr.current_language())
            if idx >= 0:
                self.lang_combo.setCurrentIndex(idx)
            self.lang_combo.blockSignals(False)
                
        # 管理员按钮
        if hasattr(self, 'admin_btn') and self.admin_btn.isVisible():
            self.admin_btn.setText(tr("MainWindow", "⚠ 非管理员模式 - 点击提权"))
            
        # 内容区域页面
        if hasattr(self, 'dashboard'):
            self.dashboard.retranslateUi()
        if hasattr(self, 'file_list'):
            self.file_list.retranslateUi()
        if hasattr(self, 'advisor_panel'):
            self.advisor_panel.retranslateUi()
            
        # 状态栏
        if hasattr(self, 'status_label'):
            current_text = self.status_label.text()
            # 只翻译静态状态文本
            if current_text in ("就绪", "Ready"):
                self.status_label.setText(tr("Common", "就绪"))
            elif current_text in ("正在扫描...", "Scanning..."):
                self.status_label.setText(tr("Common", "正在扫描..."))
            elif current_text in ("权限不足", "Insufficient Permissions"):
                self.status_label.setText(tr("Common", "权限不足"))

    def _setup_ui(self):
        self.setWindowTitle(tr("MainWindow", "DiskPulse - 磁盘管理清理工具"))
        self.setMinimumSize(900, 600)
        self.setObjectName("mainWindow")

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(1)
        splitter.setChildrenCollapsible(False)

        self._setup_sidebar(splitter)
        self._setup_content(splitter)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([200, 900])

        main_layout.addWidget(splitter)
        self._setup_status_bar()

    def _setup_sidebar(self, widget):
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setMinimumWidth(160)
        sidebar.setMaximumWidth(300)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("DiskPulse")
        logo.setObjectName("sidebarLogo")
        logo.setAlignment(Qt.AlignCenter)
        logo.setMinimumHeight(64)
        sidebar_layout.addWidget(logo)

        self.nav_buttons = {}
        nav_items = [
            ("dashboard", tr("MainWindow", "📊  仪表盘")),
            ("scan", tr("MainWindow", "🔍  扫描结果")),
            ("advisor", tr("MainWindow", "🧠  清理建议")),
        ]

        for key, text in nav_items:
            btn = QPushButton(text)
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda checked, k=key: self._switch_page(k))
            sidebar_layout.addWidget(btn)
            self.nav_buttons[key] = btn

        sidebar_layout.addStretch()

        # Language switcher
        from app.i18n import get_translation_manager
        self.lang_combo = QComboBox()
        self.lang_combo.setObjectName("langCombo")
        tm = get_translation_manager()
        for code, name in tm.available_languages().items():
            self.lang_combo.addItem(name, code)
        self.lang_combo.setCurrentText(tm.current_language_name())
        self.lang_combo.currentIndexChanged.connect(self._on_lang_combo_changed)
        sidebar_layout.addWidget(self.lang_combo)

        self.admin_btn = QPushButton()
        self.admin_btn.setObjectName("adminButton")
        self.admin_btn.setCursor(Qt.PointingHandCursor)
        self.admin_btn.clicked.connect(self._request_elevation)
        self.admin_btn.hide()
        sidebar_layout.addWidget(self.admin_btn)

        widget.addWidget(sidebar)

    def _setup_content(self, widget):
        content = QFrame()
        content.setObjectName("contentArea")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 24, 24, 24)

        self.stacked = QStackedWidget()

        self.dashboard = DashboardPage()
        self.dashboard.start_scan.connect(self._start_scan)

        self.file_list = FileListPanel()
        self.file_list.delete_requested.connect(self._on_delete_requested)

        self.advisor_panel = AdvisorPanel()
        self.advisor_panel.clean_btn.clicked.connect(self._on_advisor_clean)

        self.stacked.addWidget(self.dashboard)
        self.stacked.addWidget(self.file_list)
        self.stacked.addWidget(self.advisor_panel)

        content_layout.addWidget(self.stacked)

        self.progress_bar = QProgressBar()
        self.progress_bar.setObjectName("scanProgress")
        self.progress_bar.setMaximum(0)
        self.progress_bar.hide()
        content_layout.addWidget(self.progress_bar)

        widget.addWidget(content)

        self.nav_buttons["dashboard"].setChecked(True)

    def _setup_status_bar(self):
        self.status_label = QLabel(tr("Common", "就绪"))
        self.status_label.setObjectName("statusLabel")
        sb = self.statusBar()
        sb.addWidget(self.status_label)
        sb.setObjectName("statusBar")

    def _on_lang_combo_changed(self, index: int):
        """语言下拉框切换：仅负责加载语言，界面刷新由 LanguageChange 事件驱动"""
        locale_code = self.lang_combo.itemData(index)
        if locale_code:
            self._trans_mgr.load_language(locale_code)

    def _switch_page(self, page: str):
        mapping = {
            "dashboard": 0,
            "scan": 1,
            "advisor": 2,
        }
        idx = mapping.get(page, 0)
        self.stacked.setCurrentIndex(idx)
        for key, btn in self.nav_buttons.items():
            btn.setChecked(key == page)

        if page == "advisor" and self._scan_result:
            self._refresh_advice()

    def _start_scan(self):
        dialog = DriveSelectDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return

        self.settings.scan_paths = dialog.selected_paths
        self.file_list.clear_results()
        self._scan_result = None

        self.progress_bar.show()
        self.status_label.setText(tr("Common", "正在扫描..."))

        self.scan_engine = ScanEngine(self.settings)
        self.scan_engine.progress.connect(self._on_scan_progress)
        self.scan_engine.finished_signal.connect(self._on_scan_finished)
        self.scan_engine.start()

    def _on_scan_progress(self, message: str):
        self.status_label.setText(message)

    def _on_scan_finished(self, result):
        self._scan_result = result
        self.progress_bar.hide()
        self.status_label.setText(tr("Common", "扫描完成！共 {} 个文件，{}").format(result.total_files, result.total_size_str))

        if result.large_files:
            self.file_list.add_items(result.large_files)
        if result.temp_files:
            self.file_list.add_items(result.temp_files[:200])
        if result.old_files:
            self.file_list.add_items(result.old_files)
        if result.empty_folders:
            self.file_list.add_items(result.empty_folders[:100])

        self._switch_page("scan")
        self._refresh_advice()

        QMessageBox.information(
            self,
            tr("MainWindow", "扫描完成"),
            tr("MainWindow", "文件数：{}\n文件夹数：{}\n总大小：{}\n大文件(>{}MB)：{} 个\n临时文件：{} 个\n旧文件(>{}天)：{} 个\n空文件夹：{} 个\n扫描耗时：{} 秒").format(
                result.total_files,
                result.total_folders,
                result.total_size_str,
                self.settings.min_large_file_mb,
                len(result.large_files),
                len(result.temp_files),
                self.settings.old_file_days,
                len(result.old_files),
                len(result.empty_folders),
                f"{result.duration_seconds:.1f}",
            ),
        )

    def _refresh_advice(self):
        suggestions = self.advisor_engine.analyze(self._scan_result)
        self.advisor_panel.set_suggestions(suggestions)

    def _on_delete_requested(self, paths: list):
        if not paths:
            return

        total_size = 0
        for p in paths:
            try:
                total_size += p.stat().st_size if p.is_file() else 0
            except OSError:
                pass

        msg = QMessageBox(self)
        msg.setWindowTitle(tr("MainWindow", "确认删除"))
        msg.setText(tr("MainWindow", "确定要删除选中的 {} 个文件？\n可释放空间：{}").format(len(paths), FileItem.format_size(total_size)))
        msg.setInformativeText(tr("MainWindow", "删除操作将文件移入回收站。"))
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        cb = QCheckBox(tr("MainWindow", "我理解以上说明"))
        msg.setCheckBox(cb)

        result = msg.exec()
        if result == QMessageBox.Yes:
            from app.utils.file_ops import delete_paths
            failed = delete_paths(paths, use_recycle_bin=True)
            if failed:
                QMessageBox.warning(
                    self, tr("MainWindow", "删除失败"),
                    tr("MainWindow", "{} 个文件删除失败，可能被占用或权限不足。").format(len(failed))
                )
            else:
                QMessageBox.information(
                    self, tr("MainWindow", "删除完成"),
                    tr("MainWindow", "成功删除 {} 个文件，释放 {}。").format(len(paths), FileItem.format_size(total_size))
                )
                self.status_label.setText(
                    tr("Common", "已删除 {} 个文件，释放 {}").format(len(paths), FileItem.format_size(total_size))
                )

    def _on_advisor_clean(self):
        items = self.advisor_panel.get_checked_items()
        if not items:
            return

        total_size = 0
        for p in items:
            try:
                total_size += p.stat().st_size if p.is_file() else 0
            except OSError:
                pass

        msg = QMessageBox(self)
        msg.setWindowTitle(tr("MainWindow", "确认清理"))
        msg.setText(tr("MainWindow", "确定要清理选中的 {} 项？\n可释放空间：{}").format(len(items), FileItem.format_size(total_size)))
        msg.setInformativeText(
            tr("MainWindow", "建议先在回收站中确认没有重要文件。\n清理后的文件将移入回收站。")
        )
        msg.setIcon(QMessageBox.Warning)
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)

        result = msg.exec()
        if result == QMessageBox.Yes:
            from app.utils.file_ops import delete_paths
            failed = delete_paths(items, use_recycle_bin=True)
            if failed:
                QMessageBox.warning(self, tr("MainWindow", "清理失败"), tr("MainWindow", "{} 项清理失败。").format(len(failed)))
            else:
                QMessageBox.information(
                    self, tr("MainWindow", "清理完成"),
                    tr("MainWindow", "成功清理 {} 项，释放 {}。").format(len(items), FileItem.format_size(total_size))
                )
                self.status_label.setText(
                    tr("Common", "已清理 {} 项，释放 {}").format(len(items), FileItem.format_size(total_size))
                )

    def _check_admin(self):
        if not is_admin():
            self.admin_btn.setText(tr("MainWindow", "⚠ 非管理员模式 - 点击提权"))
            self.admin_btn.show()
            msg = QMessageBox(self)
            msg.setWindowTitle(tr("MainWindow", "权限不足"))
            msg.setIcon(QMessageBox.Warning)
            msg.setText(tr("MainWindow", "当前未以管理员身份运行"))
            msg.setInformativeText(
                tr("MainWindow", "以管理员身份运行可以扫描更多系统目录（如 Windows、Program Files 等）\n\n是否要以管理员身份重新启动？")
            )
            msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
            msg.setDefaultButton(QMessageBox.Yes)
            if msg.exec() == QMessageBox.Yes:
                self._request_elevation()

    def _request_elevation(self):
        reply = QMessageBox.question(
            self, tr("MainWindow", "提权确认"),
            tr("MainWindow", "将以管理员身份重新启动 DiskPulse，是否继续？"),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply == QMessageBox.Yes:
            request_admin()
            sys.exit(0)

    def closeEvent(self, event):
        self._save_session()
        if self.scan_engine and self.scan_engine.isRunning():
            self.scan_engine.stop()
            self.scan_engine.wait(3000)
        self.settings.save()
        super().closeEvent(event)

    def _restart_application(self):
        """Restart the application to apply language changes"""
        self._save_session()
        self.settings.save()
        if self.scan_engine and self.scan_engine.isRunning():
            self.scan_engine.stop()
            self.scan_engine.wait(3000)
        import subprocess
        subprocess.Popen([sys.executable] + sys.argv)
        self.close()

    def _save_session(self):
        # Save window size
        self.settings.window_width = self.width()
        self.settings.window_height = self.height()

        # Save splitter sizes
        central = self.centralWidget()
        if central:
            layout = central.layout()
            if layout and layout.count() > 0:
                splitter = layout.itemAt(0).widget()
                if hasattr(splitter, 'sizes'):
                    self.settings.splitter_sizes = splitter.sizes()

        # Save last page
        current_index = self.stacked.currentIndex()
        page_map = {0: "dashboard", 1: "scan", 2: "advisor"}
        self.settings.last_page = page_map.get(current_index, "dashboard")

        # Save file list state
        if hasattr(self, 'file_list') and self.file_list:
            self.settings.selected_file_paths = [str(p) for p in self.file_list.get_selected_paths()]
            self.settings.file_list_sort_column = self.file_list.tree.sortColumn()
            self.settings.file_list_sort_order = int(self.file_list.tree.header().sortIndicatorOrder())
            self.settings.file_list_filter_index = self.file_list.filter_combo.currentIndex()

        # Save scan paths
        if hasattr(self, 'settings') and hasattr(self, 'scan_engine') and self.scan_engine:
            self.settings.last_scan_paths = self.settings.scan_paths

    def _restore_session(self):
        # Restore splitter sizes
        if hasattr(self, 'settings') and self.settings.splitter_sizes:
            central = self.centralWidget()
            if central:
                layout = central.layout()
                if layout and layout.count() > 0:
                    splitter = layout.itemAt(0).widget()
                    if hasattr(splitter, 'setSizes'):
                        splitter.setSizes(self.settings.splitter_sizes)

        # Restore last page
        if hasattr(self, 'settings') and self.settings.last_page:
            self._switch_page(self.settings.last_page)

        # Restore file list state
        if hasattr(self, 'file_list') and self.file_list:
            # Restore sort
            if self.settings.file_list_sort_column is not None:
                sort_order = Qt.SortOrder(self.settings.file_list_sort_order) if self.settings.file_list_sort_order is not None else Qt.DescendingOrder
                self.file_list.tree.sortItems(self.settings.file_list_sort_column, sort_order)
            # Restore filter
            if self.settings.file_list_filter_index is not None:
                self.file_list.filter_combo.setCurrentIndex(self.settings.file_list_filter_index)
            # Restore selections (after items are added)
            if self.settings.selected_file_paths:
                self._restore_file_selections()

    def _restore_file_selections(self):
        """Restore checkbox selections in file list after items are loaded"""
        if hasattr(self, 'file_list') and self.file_list and self.settings.selected_file_paths:
            self.file_list.restore_selections(self.settings.selected_file_paths)