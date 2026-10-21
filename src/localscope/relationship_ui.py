"""Offline read-only visualization of inferred Python project relationships."""
from __future__ import annotations
from collections import defaultdict
from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPen
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QGraphicsScene, QGraphicsView, QGraphicsRectItem, QGraphicsSimpleTextItem,
    QTreeWidget, QTreeWidgetItem, QSplitter)
from .python_intelligence import inspect_python
from .models import format_size
from .relationship_model import relationship_data, group_project_families




class ClickableRect(QGraphicsRectItem):
    def __init__(self, bounds, selected, opened):
        super().__init__(bounds)
        self.selected = selected
        self.opened = opened
    def mousePressEvent(self, event):
        self.selected()
        super().mousePressEvent(event)
    def mouseDoubleClickEvent(self, event):
        self.opened()
        event.accept()


class GraphView(QGraphicsView):
    def wheelEvent(self, event):
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        if 0.25 < self.transform().m11() * factor < 4:
            self.scale(factor, factor)
        event.accept()


class RelationshipDialog(QDialog):
    def __init__(self, root, navigate, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LocalScope — Project Relationship Map')
        self.resize(1250, 780)
        self.navigate = navigate
        self.root = root
        report = inspect_python(root)
        self.nodes, self.edges = relationship_data(report)
        self.families = group_project_families(self.nodes, {f.path.casefold(): f.size for f in report.audit.projects})
        self.collapsed = True
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('PROJECT RELATIONSHIP MAP  ·  Inferred from scanned files and pyvenv.cfg · Offline · Read-only'))
        layout.addWidget(QLabel(f'{sum(v[1]=="Project" for v in self.nodes.values())} projects · '
                                f'{len(report.links)} environments · '
                                f'{sum(v[1]=="Base reference" for v in self.nodes.values())} base interpreter references · '
                                f'{report.audit.access_errors} access errors'))
        controls = QHBoxLayout()
        reset = QPushButton('Fit graph')
        controls.addWidget(reset)
        self.group_button = QPushButton('Show individual versions')
        self.group_button.clicked.connect(self._toggle_groups)
        controls.addWidget(self.group_button)
        controls.addWidget(QLabel('Wheel: zoom · Drag: pan · Click a node: details · Double-click: explore'), 1)
        layout.addLayout(controls)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.scene = QGraphicsScene(self)
        self.view = GraphView(self.scene)
        self.view.setRenderHints(self.view.renderHints())
        self.view.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.view.setBackgroundBrush(QColor('#172233'))
        splitter.addWidget(self.view)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Type', 'Name', 'Location', 'Explanation'])
        self.table.setColumnWidth(0, 140)
        self.table.setColumnWidth(1, 210)
        self.table.setColumnWidth(2, 420)
        self.table.itemDoubleClicked.connect(self._open_row)
        self.table.itemSelectionChanged.connect(self._selected_row)
        splitter.addWidget(self.table)
        splitter.setSizes([500, 180])
        layout.addWidget(splitter, 1)
        self.info = QLabel('Select a node or row. References are not proof of installed or redundant Python copies.')
        self.info.setWordWrap(True)
        layout.addWidget(self.info)
        self._render()
        reset.clicked.connect(self._fit)
        self._fit()

    def _toggle_groups(self):
        self.collapsed = not self.collapsed
        self.group_button.setText('Show individual versions' if self.collapsed else 'Group project versions')
        self._render()
        self._fit()

    def _fit(self):
        if not self.scene.items():
            return
        self.view.fitInView(self.scene.itemsBoundingRect().adjusted(-30,-30,30,30), Qt.AspectRatioMode.KeepAspectRatio)

    def _selected_row(self):
        item = self.table.currentItem()
        if item:
            self.info.setText(f"{item.text(0)}: {item.text(2)} | {item.text(3)}")

    def _open_row(self, item, _column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        self._open_path(path)

    def _open_path(self, path):
        if not path:
            return
        stack = [self.root]
        key = path.replace('\\','/').casefold()
        while stack:
            node = stack.pop()
            if node.is_dir and node.path.replace('\\','/').casefold() == key:
                self.accept()
                self.navigate(node)
                return
            if node.is_dir:
                stack.extend(node.children)
        self.info.setText('This path is not an indexed directory in the current scan. Scan its parent to explore it.')

    def _render(self):
        self.scene.clear()
        self.table.clear()
        nodes = dict(self.nodes)
        edges = set(self.edges)
        if self.collapsed:
            for family in self.families:
                family_key = 'family:' + family.label
                member_keys = {'project:' + path.casefold() for path in family.paths}
                detail = f'{len(family.paths)} versions · {format_size(family.total_size)} · Expand with Show individual versions'
                nodes[family_key] = (family.label + f' ({len(family.paths)} versions)', 'Family', family.paths[0], detail)
                edges = {(family_key if a in member_keys else a, family_key if b in member_keys else b)
                         for a, b in edges}
                for key in member_keys:
                    nodes.pop(key, None)
        by_kind = defaultdict(list)
        for key, data in nodes.items():
            by_kind[data[1]].append((key, data))
        # Family and Project occupy the same first column.
        columns = [('Family', 'Project'), ('Environment',), ('Base reference',)]
        colors = {'Project':'#39ad9d', 'Family':'#2e8c80', 'Environment':'#9a7cf0', 'Base reference':'#5085e8'}
        positions = {}
        for column, kinds in enumerate(columns):
            entries = sorted((entry for kind in kinds for entry in by_kind[kind]), key=lambda e:e[1][0].casefold())
            for row, (key, (name, kind, path, detail)) in enumerate(entries):
                # Sizes communicate relationship density, not falsely inferred disk usage.
                degree = sum(1 for a,b in edges if key in (a,b))
                height = min(84, 48 + 5 * degree)
                x, y = column * 390 + 20, row * 100 + 20
                positions[key] = (x, y, height)
                rect = ClickableRect(QRectF(x, y, 330, height),
                    lambda p=path, k=kind, d=detail: self.info.setText(f"{k}: {p} | {d}"),
                    lambda p=path: self._open_path(p))
                rect.setBrush(QBrush(QColor(colors[kind])))
                rect.setPen(QPen(QColor('#c6d6ef'), 1))
                rect.setToolTip(f'{kind}: {path}\n{detail}')
                self.scene.addItem(rect)
                label = QGraphicsSimpleTextItem(name[:39] + ('…' if len(name)>39 else ''))
                label.setBrush(QBrush(QColor('white')))
                label.setPos(x+12, y+12)
                label.setToolTip(rect.toolTip())
                self.scene.addItem(label)
                item = QTreeWidgetItem([kind, name, path, detail])
                item.setData(0, Qt.ItemDataRole.UserRole, path)
                item.setToolTip(2, path)
                self.table.addTopLevelItem(item)
        for source, target in edges:
            if source not in positions or target not in positions:
                continue
            x1,y1,h1=positions[source]; x2,y2,h2=positions[target]
            line=self.scene.addLine(x1+330,y1+h1/2,x2,y2+h2/2,QPen(QColor('#7891b6'),2))
            line.setZValue(-1)
        if not edges:
            self.info.setText('No relationships detected in this scan. Scan the folder containing your .venv directories and pyvenv.cfg files.')
        self.scene.setSceneRect(self.scene.itemsBoundingRect().adjusted(-35,-35,35,35))
