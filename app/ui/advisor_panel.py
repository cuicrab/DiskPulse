from typing import List, Callable
from PySide6.QtCore import Qt, Signal, QSize, QEvent
from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QWidget, QCheckBox, QGridLayout, QSizePolicy,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QAbstractItemView,
)
from PySide6.QtGui import QColor
from app.models.advisor_item import AdvisorItem
from app.i18n import tr


class AdvisorCard(QFrame):
    def __init__(self, item: AdvisorItem, parent=None):
        super().__init__(parent)
        self.item = item
        self._expanded = False
        self._checked_files: set = set()
        self._updating_main_checkbox = False  # 防止信号循环
        self._setup_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self.expand_btn.setText(tr("AdvisorCard", "▸ 查看文件") if not self._expanded else tr("AdvisorCard", "▾ 收起文件"))
        if self._no_file_label:
            self._no_file_label.setText(tr("AdvisorCard", "  无法枚举具体文件（需要管理员权限）"))
        self.file_tree.setHeaderLabels(["", tr("AdvisorCard", "文件名"), tr("AdvisorCard", "路径")])

    def _setup_ui(self):
        self.setObjectName("advisorCard")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        self.checkbox = QCheckBox()
        self.checkbox.setTristate(True)
        self.checkbox.stateChanged.connect(self._on_main_check_changed)
        top_layout.addWidget(self.checkbox)

        info_layout = QVBoxLayout()
        info_layout.setSpacing(2)

        name_label = QLabel(self.item.description)
        name_label.setObjectName("advisorName")

        hint_label = QLabel(self.item.hint)
        hint_label.setObjectName("advisorHint")
        hint_label.setWordWrap(True)

        info_layout.addWidget(name_label)
        info_layout.addWidget(hint_label)
        top_layout.addLayout(info_layout, 1)

        self.expand_btn = QPushButton(tr("AdvisorCard", "▸ 查看文件"))
        self.expand_btn.setObjectName("expandButton")
        self.expand_btn.setFixedWidth(100)
        self.expand_btn.clicked.connect(self._toggle_expand)
        top_layout.addWidget(self.expand_btn)

        size_label = QLabel(self.item.size_str)
        size_label.setObjectName("advisorSize")
        top_layout.addWidget(size_label)

        count_label = QLabel(tr("AdvisorCard", "{} 项").format(self.item.file_count))
        count_label.setObjectName("advisorCount")
        top_layout.addWidget(count_label)

        self.layout().addLayout(top_layout)

        self.file_tree = QTreeWidget()
        self.file_tree.setHeaderLabels(["", tr("AdvisorCard", "文件名"), tr("AdvisorCard", "路径")])
        self.file_tree.header().setStretchLastSection(True)
        self.file_tree.setColumnWidth(0, 40)
        self.file_tree.setColumnWidth(1, 250)
        self.file_tree.setAlternatingRowColors(True)
        self.file_tree.setVisible(False)
        self.file_tree.setMinimumHeight(0)
        self.file_tree.setMaximumHeight(300)
        self.file_tree.setRootIsDecorated(False)
        self.file_tree.setHeaderHidden(True)
        self.file_tree.itemClicked.connect(self._on_file_item_clicked)
        self.file_tree.itemChanged.connect(self._on_file_tree_item_changed)

        for file_path in self.item.files[:200]:
            item_widget = QTreeWidgetItem()
            item_widget.setFlags(item_widget.flags() | Qt.ItemIsUserCheckable)
            item_widget.setCheckState(0, Qt.Unchecked)
            item_widget.setText(1, file_path.name)
            item_widget.setText(2, str(file_path.parent))
            item_widget.setForeground(1, QColor("#b2bec3"))
            item_widget.setForeground(2, QColor("#636e72"))
            item_widget.setData(0, Qt.UserRole, str(file_path))
            item_widget.setSizeHint(0, QSize(24, 24))
            self.file_tree.addTopLevelItem(item_widget)

        if not self.item.files:
            no_file_label = QLabel(tr("AdvisorCard", "  无法枚举具体文件（需要管理员权限）"))
            no_file_label.setObjectName("advisorHint")
            no_file_label.setVisible(False)
            self._no_file_label = no_file_label
            layout.addWidget(no_file_label)
        else:
            self._no_file_label = None

        layout.addWidget(self.file_tree)

    def _toggle_expand(self):
        self._expanded = not self._expanded
        self.file_tree.setVisible(self._expanded)
        if self._no_file_label:
            self._no_file_label.setVisible(self._expanded)
        self.expand_btn.setText(tr("AdvisorCard", "▾ 收起文件") if self._expanded else tr("AdvisorCard", "▸ 查看文件"))
        self._update_main_checkbox_state()

    def _on_main_check_changed(self, state):
        if self._updating_main_checkbox:
            return
        if state == Qt.CheckState.PartiallyChecked.value:
            return
        checked_state = Qt.Checked if state == Qt.CheckState.Checked.value else Qt.Unchecked
        self._updating_main_checkbox = True
        for i in range(self.file_tree.topLevelItemCount()):
            self.file_tree.topLevelItem(i).setCheckState(0, checked_state)
        self._updating_main_checkbox = False
        if checked_state == Qt.Checked:
            self._checked_files = {str(self.item.files[i]) for i in range(min(self.file_tree.topLevelItemCount(), len(self.item.files)))}
        else:
            self._checked_files.clear()

    def _on_file_item_clicked(self, item, column):
        current = item.checkState(0)
        new_state = Qt.Unchecked if current == Qt.Checked else Qt.Checked
        item.setCheckState(0, new_state)
        path = item.data(0, Qt.UserRole)
        if new_state == Qt.Checked:
            self._checked_files.add(path)
        else:
            self._checked_files.discard(path)
        self._update_main_checkbox_state()

    def _on_file_tree_item_changed(self, item, column):
        if column == 0 and not self._updating_main_checkbox:
            self._update_checked_files_from_tree()
            self._update_main_checkbox_state()

    def _update_checked_files_from_tree(self):
        self._checked_files.clear()
        for i in range(self.file_tree.topLevelItemCount()):
            item = self.file_tree.topLevelItem(i)
            if item.checkState(0) == Qt.Checked:
                path = item.data(0, Qt.UserRole)
                self._checked_files.add(path)

    def _update_main_checkbox_state(self):
        if not self.file_tree.topLevelItemCount():
            return
        checked_count = sum(
            1 for i in range(self.file_tree.topLevelItemCount())
            if self.file_tree.topLevelItem(i).checkState(0) == Qt.Checked
        )
        total = self.file_tree.topLevelItemCount()
        self._updating_main_checkbox = True
        if checked_count == 0:
            self.checkbox.setCheckState(Qt.Unchecked)
        elif checked_count == total:
            self.checkbox.setCheckState(Qt.Checked)
        else:
            self.checkbox.setCheckState(Qt.PartiallyChecked)
        self._updating_main_checkbox = False

    def has_checked_items(self) -> bool:
        return len(self._checked_files) > 0

    def get_checked_paths(self) -> list:
        from pathlib import Path
        return [Path(p) for p in self._checked_files]


class AdvisorPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._cards: List[AdvisorCard] = []
        self._setup_ui()

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)

    def retranslateUi(self):
        self._title_label.setText(tr("AdvisorPanel", "清理建议"))
        self.clean_btn.setText(tr("AdvisorPanel", "清理选中项"))
        for card in self._cards:
            card.retranslateUi()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        self._title_label = QLabel(tr("AdvisorPanel", "清理建议"))
        self._title_label.setObjectName("panelTitle")
        layout.addWidget(self._title_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        scroll_content = QWidget()
        self._scroll_layout = QVBoxLayout(scroll_content)
        self._scroll_layout.setSpacing(8)
        self._scroll_layout.addStretch()

        scroll.setWidget(scroll_content)
        layout.addWidget(scroll, 1)

        btn_layout = QHBoxLayout()
        self.clean_btn = QPushButton(tr("AdvisorPanel", "清理选中项"))
        self.clean_btn.setObjectName("cleanButton")
        self.clean_btn.setEnabled(False)
        btn_layout.addStretch()
        btn_layout.addWidget(self.clean_btn)

        layout.addLayout(btn_layout)

    def set_suggestions(self, suggestions: dict):
        self._clear_cards()
        self._cards.clear()

        sections = [
            (tr("AdvisorPanel", "⭐⭐⭐ 强烈建议清理"), suggestions.get("strongly_recommended", []), "#00b894"),
            (tr("AdvisorPanel", "⭐⭐ 建议检查清理"), suggestions.get("suggested", []), "#fdcb6e"),
            (tr("AdvisorPanel", "⭐ 谨慎清理"), suggestions.get("caution", []), "#e17055"),
        ]

        for section_title, items, color in sections:
            if not items:
                continue

            total_size = sum(item.size_bytes for item in items)
            header = QLabel(
                f'{section_title}  (可释放 {self._format_size(total_size)})'
            )
            header.setObjectName("sectionHeader")
            header.setStyleSheet(f"color: {color};")
            self._scroll_layout.insertWidget(
                self._scroll_layout.count() - 1, header
            )

            for item in items:
                card = AdvisorCard(item)
                card.checkbox.stateChanged.connect(self._on_check_changed)
                self._cards.append(card)
                self._scroll_layout.insertWidget(
                    self._scroll_layout.count() - 1, card
                )

    def _clear_cards(self):
        for card in self._cards:
            card.setParent(None)
        for i in reversed(range(self._scroll_layout.count() - 1)):
            item = self._scroll_layout.itemAt(i)
            if item and item.widget():
                item.widget().setParent(None)

    def _on_check_changed(self):
        checked = any(card.has_checked_items() for card in self._cards)
        self.clean_btn.setEnabled(checked)

    def get_checked_items(self) -> list:
        checked_files = []
        for card in self._cards:
            checked_files.extend(card.get_checked_paths())
        return checked_files

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"

    def changeEvent(self, event):
        if event.type() == QEvent.Type.LanguageChange:
            self.retranslateUi()
        super().changeEvent(event)