from typing import List, Optional, Set
from PySide6.QtCore import Qt, Signal, QSize, QEvent, QRect
from PySide6.QtGui import QColor, QAction, QFont, QPainter
from PySide6.QtWidgets import (
    QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
    QFrame, QVBoxLayout, QLabel, QPushButton, QHBoxLayout,
    QCheckBox, QWidget, QComboBox, QMenu, QMessageBox,
    QStyleOptionViewItem, QStyledItemDelegate, QStyle,
)

from app.models.file_item import FileItem, FileCategory
from app.i18n import tr

# 类别标签用低饱和色，配合深色背景与浅色文字，避免高饱和“荧光”感
CATEGORY_MAP = {
    FileCategory.LARGE_FILE: ("大文件", "#F0A44A"),
    FileCategory.DUPLICATE: ("重复文件", "#D8C36B"),
    FileCategory.TEMP_FILE: ("临时文件", "#6FA8DC"),
    FileCategory.EMPTY_FOLDER: ("空文件夹", "#9B8FE0"),
    FileCategory.CACHE: ("缓存文件", "#3FD9A4"),
    FileCategory.OLD_FILE: ("旧文件", "#D99A82"),
    FileCategory.RECYCLER: ("回收站", "#E06C5F"),
}

CATEGORY_FILTER_OPTIONS = [
    (tr("FileListPanel", "全部"), None),
    (tr("FileListPanel", "大文件"), FileCategory.LARGE_FILE),
    (tr("FileListPanel", "临时文件"), FileCategory.TEMP_FILE),
    (tr("FileListPanel", "空文件夹"), FileCategory.EMPTY_FOLDER),
    (tr("FileListPanel", "缓存文件"), FileCategory.CACHE),
    (tr("FileListPanel", "旧文件"), FileCategory.OLD_FILE),
    (tr("FileListPanel", "重复文件"), FileCategory.DUPLICATE),
    (tr("FileListPanel", "回收站"), FileCategory.RECYCLER),
]

SORT_OPTIONS = [
    (tr("FileListPanel", "按大小"), 2, Qt.DescendingOrder),
    (tr("FileListPanel", "按名称"), 1, Qt.AscendingOrder),
    (tr("FileListPanel", "按修改时间"), 3, Qt.DescendingOrder),
    (tr("FileListPanel", "按类别"), 5, Qt.AscendingOrder),
]


class CategoryDelegate(QStyledItemDelegate):
    """在类别列绘制多个圆角标签。

    数据源：列 5 的 Qt.UserRole（add_items 里写入的 categories 列表）。
    列 0 的 UserRole 存的是路径、UserRole+1 才是类别，不要读错。
    """

    @staticmethod
    def _categories(index):
        cats = index.data(Qt.UserRole)
        # 只接受类别列表，避免把路径字符串当成可迭代对象逐字符渲染
        if not cats or isinstance(cats, str):
            return []
        return list(cats)

    def paint(self, painter, option, index):
        categories = self._categories(index)
        if not categories:
            super().paint(painter, option, index)
            return

        # 先自行绘制行背景，再把标签叠上去；
        # 若直接 super().paint() 会连单元格文字一起画出来造成重影
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        opt.widget.style().drawControl(QStyle.CE_ItemViewItem, opt, painter, opt.widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = option.rect
        x = rect.left() + 6
        tag_h = min(20, rect.height() - 8)
        y = rect.top() + (rect.height() - tag_h) // 2

        font = painter.font()
        font.setPointSizeF(max(7.5, font.pointSizeF() - 1.0))
        painter.setFont(font)

        for cat in categories:
            label, color = CATEGORY_MAP.get(cat, ("其他", "#636e72"))
            text_width = painter.fontMetrics().horizontalAdvance(label) + 18
            tag_rect = QRect(x, y, text_width, tag_h)

            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(color))
            painter.drawRoundedRect(tag_rect, tag_h / 2, tag_h / 2)

            painter.setPen(QColor("#0B1512"))
            painter.drawText(tag_rect, Qt.AlignCenter, label)

            x += text_width + 6

        painter.restore()

    def sizeHint(self, option, index):
        categories = self._categories(index)
        if not categories:
            return super().sizeHint(option, index)

        total_width = 0
        for cat in categories:
            label, _ = CATEGORY_MAP.get(cat, ("其他", "#636e72"))
            total_width += option.fontMetrics.horizontalAdvance(label) + 18 + 6

        return QSize(total_width + 12, 26)


class FileListPanel(QFrame):
    selection_changed = Signal(int)
    delete_requested = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._items: List[FileItem] = []
        self._checkboxes: dict = {}
        self._path_to_item: dict = {}  # path -> QTreeWidgetItem
        self._setup_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        # Header title
        self._title_label.setText(tr("FileListPanel", "扫描结果"))
        
        # Filter and Sort labels
        self._filter_label.setText(tr("FileListPanel", "筛选:"))
        self._sort_label.setText(tr("FileListPanel", "排序:"))
        
        # Filter combo
        self.filter_combo.blockSignals(True)
        self.filter_combo.clear()
        self.filter_combo.addItems([tr("FileListPanel", label) for label, _ in CATEGORY_FILTER_OPTIONS])
        
        # Sort combo
        self.sort_combo.blockSignals(True)
        self.sort_combo.clear()
        self.sort_combo.addItems([tr("FileListPanel", label) for label, _, _ in SORT_OPTIONS])
        
        # Buttons
        self.open_btn.setText(tr("FileListPanel", "打开位置"))
        self.select_all_cb.setText(tr("FileListPanel", "全选"))
        self.delete_btn.setText(tr("FileListPanel", "删除选中"))
        
        # Tree headers
        self.tree.setHeaderLabels([
            "",
            tr("FileListPanel", "文件名"),
            tr("FileListPanel", "大小"),
            tr("FileListPanel", "修改时间"),
            tr("FileListPanel", "路径"),
            tr("FileListPanel", "类别"),
        ])
        
        # Stats label
        self._update_stats()
        
        self.filter_combo.blockSignals(False)
        self.sort_combo.blockSignals(False)

    def _setup_ui(self):
        # 只创建一个顶层布局：重复 setLayout / 重复 QVBoxLayout(self)
        # 会让控件归属混乱，实测会导致整个面板渲染空白
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._title_label = QLabel(tr("FileListPanel", "扫描结果"))
        self._title_label.setObjectName("panelTitle")

        self.filter_combo = QComboBox()
        self.filter_combo.addItems([tr("FileListPanel", label) for label, _ in CATEGORY_FILTER_OPTIONS])
        self.filter_combo.currentIndexChanged.connect(self._apply_filter)
        self.filter_combo.setMinimumWidth(100)

        self.sort_combo = QComboBox()
        self.sort_combo.addItems([tr("FileListPanel", label) for label, _, _ in SORT_OPTIONS])
        self.sort_combo.currentIndexChanged.connect(self._apply_sort)
        self.sort_combo.setMinimumWidth(100)

        self.open_btn = QPushButton(tr("FileListPanel", "打开位置"))
        self.open_btn.setObjectName("openLocationButton")
        self.open_btn.clicked.connect(self._open_selected_location)
        self.open_btn.setEnabled(False)

        self.select_all_cb = QCheckBox(tr("FileListPanel", "全选"))
        self.select_all_cb.stateChanged.connect(self._on_select_all)

        self.delete_btn = QPushButton(tr("FileListPanel", "删除选中"))
        self.delete_btn.setObjectName("deleteButton")
        self.delete_btn.clicked.connect(self._on_delete)

        self.size_label = QLabel(tr("FileListPanel", "共 0 项，0 B"))
        self.size_label.setObjectName("sizeLabel")

        self._filter_label = QLabel(tr("FileListPanel", "筛选:"))
        self._sort_label = QLabel(tr("FileListPanel", "排序:"))

        header = QHBoxLayout()
        header.addWidget(self._filter_label)
        header.addWidget(self.filter_combo)
        header.addSpacing(8)
        header.addWidget(self._sort_label)
        header.addWidget(self.sort_combo)
        header.addStretch()
        header.addWidget(self.open_btn)
        header.addSpacing(8)
        header.addWidget(self.size_label)
        header.addSpacing(8)
        header.addWidget(self.select_all_cb)
        header.addWidget(self.delete_btn)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["", tr("FileListPanel", "文件名"), tr("FileListPanel", "大小"), tr("FileListPanel", "修改时间"), tr("FileListPanel", "路径"), tr("FileListPanel", "类别")])
        # 列宽之和刻意留出余量，避免出现横向滚动条
        self.tree.setColumnWidth(0, 44)
        self.tree.setColumnWidth(1, 240)
        self.tree.setColumnWidth(2, 96)
        self.tree.setColumnWidth(3, 150)
        self.tree.setColumnWidth(4, 300)
        self.tree.setColumnWidth(5, 150)
        self.tree.header().setStretchLastSection(False)
        self.tree.header().setSectionResizeMode(4, QHeaderView.Stretch)
        self.tree.header().setMinimumSectionSize(44)
        self.tree.setAlternatingRowColors(True)
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setSortingEnabled(True)
        self.tree.itemChanged.connect(self._on_item_changed)
        self.tree.itemClicked.connect(self._on_item_clicked)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)

        # Set custom delegate for category column (column 5)
        self.tree.setItemDelegateForColumn(5, CategoryDelegate())

        layout.addWidget(self._title_label)
        layout.addLayout(header)
        layout.addWidget(self.tree, 1)

    def clear_results(self):
        self.tree.clear()
        self._items.clear()
        self._checkboxes.clear()
        self._path_to_item.clear()
        self.size_label.setText(tr("FileListPanel", "共 0 项，0 B"))

    def add_items(self, items: List[FileItem]):
        new_items: List[FileItem] = []
        self.tree.setUpdatesEnabled(False)
        self.tree.setSortingEnabled(False)
        try:
            for item in items:
                path_key = str(item.path)

                # Check if item already exists (deduplication)
                if path_key in self._path_to_item:
                    existing_item = self._path_to_item[path_key]
                    # Merge categories
                    existing_cats = existing_item.data(0, Qt.UserRole + 1)
                    if existing_cats is None:
                        existing_cats = []
                    for cat in item.all_categories:
                        if cat not in existing_cats:
                            existing_cats.append(cat)
                    # Update category display data
                    existing_item.setData(0, Qt.UserRole + 1, existing_cats)
                    existing_item.setData(5, Qt.UserRole, existing_cats)
                    continue

                # Create new tree item
                categories = item.all_categories
                primary_cat = categories[0] if categories else FileCategory.LARGE_FILE
                category_label, color = CATEGORY_MAP.get(
                    primary_cat, ("其他", "#636e72")
                )

                checkbox = QTreeWidgetItem()
                checkbox.setFlags(checkbox.flags() | Qt.ItemIsUserCheckable)
                checkbox.setCheckState(0, Qt.Unchecked)
                checkbox.setText(1, item.name)
                checkbox.setText(2, item.size_str)
                checkbox.setText(3, item.modified_time.strftime("%Y-%m-%d %H:%M"))
                checkbox.setText(4, str(item.path.parent))
                checkbox.setText(5, category_label)  # fallback text for sorting
                checkbox.setForeground(5, QColor(color))
                checkbox.setData(0, Qt.UserRole, str(item.path))
                checkbox.setData(0, Qt.UserRole + 1, categories)  # store all categories
                checkbox.setData(5, Qt.UserRole, categories)  # for delegate rendering
                checkbox.setSizeHint(0, QSize(24, 24))
                self.tree.addTopLevelItem(checkbox)

                self._checkboxes[path_key] = checkbox
                self._path_to_item[path_key] = checkbox
                new_items.append(item)
        finally:
            self.tree.setSortingEnabled(True)
            self.tree.setUpdatesEnabled(True)

        # 只统计真正新建的条目：同一文件可能同时属于大文件/旧文件等多个类别，
        # 若整批 extend 会让项数与总大小被重复累加
        self._items.extend(new_items)
        self._update_stats()

    def _update_stats(self):
        total = len(self._items)
        total_size = sum(item.size for item in self._items)
        self.size_label.setText(tr("FileListPanel", "共 {} 项，{}").format(total, FileItem.format_size(total_size)))

    def _on_select_all(self, state):
        checked = Qt.Checked if state == Qt.CheckState.Checked.value else Qt.Unchecked
        for checkbox in self._checkboxes.values():
            checkbox.setCheckState(0, checked)

    def _on_item_clicked(self, item, column):
        if column == 0:
            return
        current = item.checkState(0)
        item.setCheckState(0, Qt.Unchecked if current == Qt.Checked else Qt.Checked)

    def _on_item_changed(self, item, column):
        if column == 0:
            checked_count = sum(
                1 for cb in self._checkboxes.values()
                if cb.checkState(0) == Qt.Checked
            )
            self.selection_changed.emit(checked_count)
            self.open_btn.setEnabled(checked_count > 0)

    def _on_delete(self):
        selected = []
        for path_str, cb in self._checkboxes.items():
            if cb.checkState(0) == Qt.Checked:
                from pathlib import Path
                selected.append(Path(path_str))
        if selected:
            self.delete_requested.emit(selected)

    def get_selected_paths(self) -> list:
        from pathlib import Path
        selected = []
        for path_str, cb in self._checkboxes.items():
            if cb.checkState(0) == Qt.Checked:
                selected.append(Path(path_str))
        return selected

    def _apply_filter(self):
        category_filter = CATEGORY_FILTER_OPTIONS[self.filter_combo.currentIndex()][1]
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if category_filter is None:
                item.setHidden(False)
            else:
                categories = item.data(0, Qt.UserRole + 1)
                if not categories:
                    item.setHidden(True)
                else:
                    item.setHidden(category_filter not in categories)

    def _apply_sort(self):
        _, col, order = SORT_OPTIONS[self.sort_combo.currentIndex()]
        self.tree.sortItems(col, order)

    def _show_context_menu(self, pos):
        item = self.tree.itemAt(pos)
        if not item:
            return
        path_str = item.data(0, Qt.UserRole)
        menu = QMenu(self)
        open_action = QAction(tr("FileListPanel", "打开文件位置"), self)
        open_action.triggered.connect(lambda: self._open_file_location(path_str))
        menu.addAction(open_action)

        copy_action = QAction(tr("FileListPanel", "复制路径"), self)
        copy_action.triggered.connect(lambda: self._copy_path(path_str))
        menu.addAction(copy_action)

        menu.exec(self.tree.mapToGlobal(pos))

    def _on_item_double_clicked(self, item, column):
        path_str = item.data(0, Qt.UserRole)
        if path_str:
            self._open_file_location(path_str)

    def _open_selected_location(self):
        for path_str, cb in self._checkboxes.items():
            if cb.checkState(0) == Qt.Checked:
                self._open_file_location(path_str)
                return

    @staticmethod
    def _open_file_location(path_str: str):
        import subprocess, os
        if os.path.isdir(path_str):
            subprocess.Popen(["explorer", path_str])
        else:
            subprocess.Popen(["explorer", "/select,", path_str])

    @staticmethod
    def _copy_path(path_str: str):
        from PySide6.QtGui import QClipboard
        from PySide6.QtWidgets import QApplication
        QApplication.clipboard().setText(path_str)

    def restore_selections(self, paths: list):
        """Restore checkbox selections for given paths after items are loaded"""
        from pathlib import Path
        path_set = {str(Path(p)) for p in paths}
        for path_str, cb in self._checkboxes.items():
            if str(Path(path_str)) in path_set:
                cb.setCheckState(0, Qt.Checked)

