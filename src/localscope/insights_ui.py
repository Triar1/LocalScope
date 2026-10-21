"""Storage Insights: visual, non-destructive overview of the existing scan."""
from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QProgressBar, QWidget, QScrollArea,
    QPushButton)
from .models import format_size
from .storage_insights import build_insights


class InsightsDialog(QDialog):
    def __init__(self, root, navigate, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LocalScope — Storage Insights')
        self.resize(1080, 760)
        self.navigate = navigate
        self.report = build_insights(root)
        self.setStyleSheet('''
            QDialog, QWidget { background:#101722; color:#EAF0F9; font:12px "Segoe UI"; }
            QTreeWidget { background:#172233; alternate-background-color:#1D2B3D; border:0; }
            QTreeWidget::item { padding:7px; }
            QHeaderView::section { background:#23344A; color:#B9C8DB; padding:7px; border:0; }
            QComboBox, QPushButton { background:#273950; border:1px solid #35465C; border-radius:6px; padding:7px; }
            QProgressBar { background:#23344A; border:0; border-radius:5px; height:14px; text-align:center; }
            QProgressBar::chunk { background:#5887F5; border-radius:5px; }
        ''')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('STORAGE INSIGHTS  ·  Breakdown of files already scanned'))
        summary = QLabel(f'{format_size(self.report.total_bytes)} scanned  ·  '
                         f'{self.report.total_files:,} files  ·  '
                         f'{self.report.access_errors} access errors  ·  Read-only')
        layout.addWidget(summary)
        layout.addWidget(QLabel('FILE TYPES  ·  Share of scanned file bytes (not application attribution)'))
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        bars = QVBoxLayout(holder)
        for item in sorted(self.report.categories, key=lambda c: -c.bytes):
            row = QHBoxLayout()
            label = QLabel(f'{item.category} · {item.files:,} files')
            label.setMinimumWidth(180)
            row.addWidget(label)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            bar.setValue(round(1000 * item.bytes / self.report.total_bytes) if self.report.total_bytes else 0)
            bar.setFormat(f'{(100 * item.bytes / self.report.total_bytes):.1f}%' if self.report.total_bytes else '0%')
            row.addWidget(bar, 1)
            size = QLabel(format_size(item.bytes))
            size.setMinimumWidth(100)
            row.addWidget(size)
            bars.addLayout(row)
        bars.addStretch()
        scroll.setWidget(holder)
        scroll.setMaximumHeight(330)
        layout.addWidget(scroll)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('LARGEST FOLDERS'))
        toolbar.addStretch()
        toolbar.addWidget(QLabel('Show'))
        self.limit = QComboBox()
        self.limit.addItems(['10', '25', '50', '100'])
        self.limit.currentTextChanged.connect(self.populate_folders)
        toolbar.addWidget(self.limit)
        layout.addLayout(toolbar)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Folder', 'Size', 'Files'])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self.open_folder)
        layout.addWidget(self.tree, 1)
        self.populate_folders()
        layout.addWidget(QLabel('Double-click a folder to explore it in the bubble map. '
                                'Categories are based on file extensions; unknown formats appear under Other.'))

    def populate_folders(self, *_):
        self.tree.clear()
        for row in self.report.folders[:int(self.limit.currentText())]:
            item = QTreeWidgetItem([row.path, format_size(row.bytes), f'{row.files:,}'])
            item.setData(0, Qt.ItemDataRole.UserRole, row.node)
            item.setToolTip(0, row.path)
            self.tree.addTopLevelItem(item)

    def open_folder(self, item, _column):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node:
            self.accept()
            self.navigate(node)
