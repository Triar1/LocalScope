"""Category Explorer for a completed scan. No disk access or file modifications."""
from __future__ import annotations
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QTreeWidget, QTreeWidgetItem, QHeaderView, QProgressBar, QWidget, QScrollArea, QTabWidget, QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QGraphicsSimpleTextItem)
from PySide6.QtGui import QColor, QBrush, QPen, QFont
from math import sqrt, cos, sin, pi
from .models import format_size
from .smart_categories import build_purpose_report, PURPOSES


class CategoryBubble(QGraphicsEllipseItem):
    def __init__(self, rect, purpose, on_select, color):
        super().__init__(rect)
        self.purpose = purpose
        self.on_select = on_select
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor('#EAF0F9'), 1.5))
        self.setToolTip(f'{purpose} — click to filter')
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event):
        self.on_select(self.purpose)
        event.accept()


class CategoriesDialog(QDialog):
    def __init__(self, root, navigate, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LocalScope — Category Explorer')
        self.resize(1100, 760)
        self.navigate = navigate
        self.report = build_purpose_report(root)
        self.setStyleSheet('''
            QDialog, QWidget { background:#101722; color:#EAF0F9; font:12px "Segoe UI"; }
            QTreeWidget { background:#172233; alternate-background-color:#1D2B3D; border:0; }
            QTreeWidget::item { padding:7px; }
            QHeaderView::section { background:#23344A; color:#B9C8DB; padding:7px; border:0; }
            QComboBox { background:#273950; border:1px solid #35465C; border-radius:6px; padding:7px; }
            QProgressBar { background:#23344A; border:0; border-radius:5px; height:14px; text-align:center; }
            QProgressBar::chunk { background:#5887F5; border-radius:5px; }
        ''')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('CATEGORY EXPLORER  ·  Folder purpose, inferred locally'))
        layout.addWidget(QLabel(f'{format_size(self.report.total_bytes)} scanned  ·  '
                                f'{format_size(self.report.classified_bytes)} attributed  ·  Read-only'))
        layout.addWidget(QLabel('USAGE CATEGORIES  ·  Offline rules: owner path first, then folder markers and extensions'))
        tabs = QTabWidget()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        holder = QWidget()
        bars = QVBoxLayout(holder)
        for item in sorted(self.report.totals, key=lambda t: -t.bytes):
            row = QHBoxLayout()
            label = QLabel(f'{item.purpose} · {item.files:,} files')
            label.setMinimumWidth(190)
            row.addWidget(label)
            bar = QProgressBar()
            bar.setRange(0, 1000)
            share = item.bytes / self.report.classified_bytes if self.report.classified_bytes else 0
            bar.setValue(round(1000 * share))
            bar.setFormat(f'{share:.1%}')
            row.addWidget(bar, 1)
            size = QLabel(format_size(item.bytes))
            size.setMinimumWidth(105)
            row.addWidget(size)
            bars.addLayout(row)
        bars.addStretch()
        scroll.setWidget(holder)
        tabs.addTab(scroll, 'Category breakdown')
        self.bubble_view = QGraphicsView()
        self.bubble_view.setRenderHints(self.bubble_view.renderHints())
        self.bubble_scene = QGraphicsScene(self.bubble_view)
        self.bubble_view.setScene(self.bubble_scene)
        self.bubble_view.setStyleSheet('background:#172233; border:0;')
        tabs.addTab(self.bubble_view, 'Category bubbles · click to filter')
        layout.addWidget(tabs)
        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel('FOLDER ATTRIBUTIONS  ·  Double-click to explore in bubble map'))
        toolbar.addStretch()
        toolbar.addWidget(QLabel('Category'))
        self.category = QComboBox()
        self.category.addItems(['All', *PURPOSES])
        self.category.currentTextChanged.connect(self.populate)
        toolbar.addWidget(self.category)
        toolbar.addWidget(QLabel('Show'))
        self.limit = QComboBox()
        self.limit.addItems(['25', '100', '500', 'All'])
        self.limit.currentTextChanged.connect(self.populate)
        toolbar.addWidget(self.limit)
        layout.addLayout(toolbar)
        self.tree = QTreeWidget()
        self.tree.setColumnCount(5)
        self.tree.setHeaderLabels(['Folder', 'Category', 'Size', 'Confidence', 'Why'])
        self.tree.setAlternatingRowColors(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self.open_folder)
        layout.addWidget(self.tree, 1)
        self.populate()
        self.draw_bubbles()
        layout.addWidget(QLabel('Estimates are heuristic, not verified application identities. '
                                'Folder rows do not overlap in totals; direct files are counted once.'))

    def populate(self, *_):
        self.tree.clear()
        category = self.category.currentText()
        entries = (e for e in self.report.entries if category == 'All' or e.purpose == category)
        limit = None if self.limit.currentText() == 'All' else int(self.limit.currentText())
        for i, row in enumerate(entries):
            if limit is not None and i >= limit:
                break
            item = QTreeWidgetItem([row.display_path or row.node.path, row.purpose, format_size(row.bytes),
                                    row.confidence, row.explanation])
            item.setData(0, Qt.ItemDataRole.UserRole, row.node)
            item.setToolTip(0, row.node.path)
            item.setToolTip(4, row.explanation)
            self.tree.addTopLevelItem(item)

    def choose_bubble(self, purpose):
        self.category.setCurrentText(purpose)

    def draw_bubbles(self):
        scene = self.bubble_scene
        scene.clear()
        values = [t for t in sorted(self.report.totals, key=lambda x: -x.bytes) if t.bytes > 0]
        if not values:
            return
        colors = ['#5887F5', '#36B5A4', '#A88AF5', '#64748B', '#ED9E4C', '#EC7194', '#62B3D5', '#DBBF5A', '#7D8CA5']
        # Stable spiral layout with non-overlapping circles. Area represents bytes.
        placed = []
        largest = max(t.bytes for t in values)
        for index, item in enumerate(values):
            radius = max(24, 90 * sqrt(item.bytes / largest))
            if index == 0:
                x, y = 0.0, 0.0
            else:
                x = y = 0.0
                for step in range(1, 12000):
                    angle = step * 0.23
                    dist = 5.0 * sqrt(step)
                    cx, cy = dist * cos(angle), dist * sin(angle)
                    if all((cx - px)**2 + (cy - py)**2 >= (radius + pr + 8)**2
                           for px, py, pr in placed):
                        x, y = cx, cy
                        break
            placed.append((x, y, radius))
            bubble = CategoryBubble(QRectF(x-radius, y-radius, radius*2, radius*2),
                                    item.purpose, self.choose_bubble, colors[index % len(colors)])
            scene.addItem(bubble)
            text = QGraphicsSimpleTextItem(f'{item.purpose}\n{format_size(item.bytes)}')
            text.setBrush(QBrush(QColor('#FFFFFF')))
            font = QFont('Segoe UI', 9)
            font.setBold(True)
            text.setFont(font)
            rect = text.boundingRect()
            text.setPos(x - rect.width()/2, y - rect.height()/2)
            text.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            scene.addItem(text)
        scene.setSceneRect(scene.itemsBoundingRect().adjusted(-20, -20, 20, 20))
        self.bubble_view.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'bubble_scene') and not self.bubble_scene.sceneRect().isEmpty():
            self.bubble_view.fitInView(self.bubble_scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def open_folder(self, item, _column):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node:
            self.accept()
            self.navigate(node)
