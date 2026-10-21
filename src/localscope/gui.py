"""LocalScope v0.2: dark, read-only bubble explorer + synchronized file inspector."""
from __future__ import annotations
import os
import sys
from PySide6.QtCore import QObject, QThread, Signal, Qt, QRectF
from PySide6.QtGui import QColor, QBrush, QPen, QPainter, QFont, QFontMetrics
from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QGraphicsTextItem,
    QTreeWidget, QTreeWidgetItem, QMessageBox, QSplitter, QFrame, QHeaderView, QComboBox, QGraphicsItem, QStackedWidget, QScrollArea, QProgressBar, QButtonGroup)
from .models import FileNode, format_size
from .scanner import scan, ScanCancelled
from .bubbles import layout_bubbles
from .auditor import audit_tree
from .python_intelligence import inspect_python
from .redundancy import analyze_redundancy
from .optimization_ui import OptimizationDialog
from .insights_ui import InsightsDialog
from .categories_ui import CategoriesDialog
from .other_ui import OtherInspectorDialog
from .relationship_ui import RelationshipDialog
from .system_ui import SystemHealthDialog
from .smart_categories import build_purpose_report
from .storage_insights import build_insights

BG = '#101722'
PANEL = '#172233'
COLORS = ['#5887F5', '#E6A04A', '#40B9A0', '#A78BFA', '#F07791', '#6AB5D7', '#B0A0F2']

class ScanWorker(QObject):
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(str)

    def __init__(self, path):
        super().__init__()
        self.path = path
        import threading
        self.cancel_event = threading.Event()

    def run(self):
        try:
            result = scan(self.path, self.progress.emit, self.cancel_event.is_set)
            self.finished.emit(result)
        except ScanCancelled:
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

class BubbleView(QGraphicsView):
    """Wheel zoom, left-button pan on empty space, middle-button pan anywhere."""
    def __init__(self, scene):
        super().__init__(scene)
        self._panning = False
        self._last_pos = None
        self.zoom_callback = None
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setDragMode(QGraphicsView.DragMode.NoDrag)

    def wheelEvent(self, event):
        factor = 1.18 if event.angleDelta().y() > 0 else 1 / 1.18
        current = self.transform().m11()
        if 0.08 <= current * factor <= 35:
            self.scale(factor, factor)
            if self.zoom_callback:
                self.zoom_callback()
        event.accept()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton or (event.button() == Qt.MouseButton.LeftButton and self.itemAt(event.pos()) is None):
            self._panning = True
            self._last_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._panning and self._last_pos is not None:
            delta = event.pos() - self._last_pos
            self._last_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self._last_pos = None
            self.unsetCursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)


class Bubble(QGraphicsEllipseItem):
    def __init__(self, node, x, y, radius, color, select, open_folder):
        super().__init__(x, y, 2*radius, 2*radius)
        self.node, self.select, self.open_folder = node, select, open_folder
        self.color = color
        self.setBrush(QBrush(QColor(color)))
        self.setPen(QPen(QColor('#E8F1FF' if node.is_dir else '#203249'), 1.2))
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f'{node.path}\n{format_size(node.size)}\nClick to explore' if node.is_dir else f'{node.path}\n{format_size(node.size)}')
        self.setZValue(1)
        self.radius = radius
        self.label = QGraphicsTextItem(self)
        self.label.setDefaultTextColor(QColor('white'))
        self.label.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIgnoresTransformations, True)
        self.label.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
        self.label.setZValue(2)
        self.label.hide()

    def update_label(self, scale):
        diameter = 2 * self.radius * scale
        if diameter < 48:
            self.label.hide()
            return
        font = QFont('Segoe UI', 9 if diameter >= 90 else 8)
        font.setBold(True)
        metrics = QFontMetrics(font)
        available = max(15, int(diameter * 0.78))
        name = metrics.elidedText(self.node.name, Qt.TextElideMode.ElideRight, available)
        show_size = diameter >= 70
        content = name + ('\n' + format_size(self.node.size) if show_size else '')
        self.label.setFont(font)
        self.label.setPlainText(content)
        self.label.setTextWidth(-1)
        rect = self.label.boundingRect()
        self.label.setPos(self.rect().center().x() - rect.width() / (2 * scale), self.rect().center().y() - rect.height() / (2 * scale))
        self.label.show()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.node.is_dir:
                self.open_folder(self.node)
            else:
                self.select(self.node)
            event.accept()
            return
        super().mousePressEvent(event)

    def set_selected(self, selected):
        self.setPen(QPen(QColor('#FFFFFF' if selected else '#203249'), 3 if selected else 1.2))
        self.setZValue(3 if selected else 1)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('LocalScope 1.0 — Your storage, visualized')
        self.resize(1280, 820)
        self.root_node = self.current_node = self.selected_node = None
        self.thread = self.worker = None
        self.bubble_items = {}
        self.path_nodes = []
        self.audit_report = None
        self._perspective_cache = {}
        self._drill_context = None
        self._active_section = "Explorer"
        self.build_ui()

    def build_ui(self):
        self.setStyleSheet('''
            QMainWindow, QWidget { background: #101722; color: #EAF0F9; font-family: Segoe UI; font-size: 12px; }
            QFrame#panel { background: #172233; border-radius: 12px; }
            QPushButton { background: #273950; border: 1px solid #35465C; border-radius: 7px; padding: 8px 12px; }
            QPushButton:hover { background: #344E6A; }
            QPushButton:disabled { color: #687A91; }
            QTreeWidget { background: #172233; border: none; alternate-background-color: #1D2B3D; outline: none; }
            QTreeWidget::item { padding: 7px; }
            QTreeWidget::item:selected { background: #304C71; }
            QHeaderView::section { background: #23344A; color: #B9C8DB; padding: 8px; border: none; }
            QComboBox { background: #273950; padding: 7px; border: 1px solid #35465C; border-radius: 7px; }
            QSplitter::handle { background: #101722; }
            QProgressBar { background: #24364C; border: 0; border-radius: 4px; }
            QProgressBar::chunk { background: #55B7A7; border-radius: 4px; }
            QToolTip { background: #24364C; color: #F0F5FF; border: 1px solid #5887F5; }
        ''')
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(18, 16, 18, 14)
        outer.setSpacing(12)
        top = QHBoxLayout()
        brand = QLabel('◉  LocalScope  ·  Your storage, visualized')
        brand.setStyleSheet('font-size: 22px; font-weight: 700; color: #F3F6FC;')
        top.addWidget(brand)
        top.addStretch()
        top.addWidget(QLabel('●  Offline · Read-only'))
        self.choose = QPushButton('Scan folder / drive')
        self.choose.clicked.connect(self.pick_folder)
        top.addWidget(self.choose)
        self.cancel = QPushButton('Cancel scan')
        self.cancel.clicked.connect(self.cancel_scan)
        self.cancel.setEnabled(False)
        top.addWidget(self.cancel)
        outer.addLayout(top)

        # Overview stays visible: the bubble map remains the primary workspace.
        sections = QHBoxLayout()
        overview = QPushButton('◉ Explorer')
        overview.clicked.connect(self.show_overview)
        sections.addWidget(overview)
        system = QPushButton('✚  System Health')
        system.clicked.connect(self.open_system_health)
        sections.addWidget(system)
        developer = QPushButton('⌘  Developer Hub')
        developer.clicked.connect(self.show_developer_hub)
        sections.addWidget(developer)
        sections.addStretch()
        outer.addLayout(sections)

        navigation = QHBoxLayout()
        self.back = QPushButton('← Back')
        self.back.clicked.connect(self.go_up)
        self.back.setEnabled(False)
        # Back belongs to the map navigation controls, not the global header.
        self.breadcrumb = QLabel('Choose a folder to explore your storage')
        self.breadcrumb.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        navigation.addWidget(self.breadcrumb, 1)
        self.mode = QComboBox()
        self.mode.addItems(['Hybrid', 'Bubbles only', 'Files only'])
        self.mode.currentIndexChanged.connect(self.set_mode)
        navigation.addWidget(self.mode)
        outer.addLayout(navigation)

        stats = QHBoxLayout()
        self.size_label = self.stat('SCANNED SIZE', '—', stats)
        self.files_label = self.stat('FILES', '—', stats)
        self.errors_label = self.stat('ACCESS ERRORS', '—', stats)
        outer.addLayout(stats)

        self.advanced_label = QLabel('DEVELOPER HUB  ·  Read-only diagnostics')
        outer.addWidget(self.advanced_label)
        audit_toolbar = QHBoxLayout()
        self.audit_button = QPushButton('Developer audit (scanned folder)')
        self.audit_button.setEnabled(False)
        self.audit_button.clicked.connect(self.show_audit)
        audit_toolbar.addWidget(self.audit_button)
        self.python_button = QPushButton('Python environment map')
        self.python_button.setEnabled(False)
        self.python_button.clicked.connect(self.show_python_map)
        audit_toolbar.addWidget(self.python_button)
        self.graph_button = QPushButton('Project Relationship Map')
        self.graph_button.setEnabled(False)
        self.graph_button.clicked.connect(self.open_relationships)
        audit_toolbar.addWidget(self.graph_button)
        self.redundancy_button = QPushButton('Redundancy report')
        self.redundancy_button.setEnabled(False)
        self.redundancy_button.clicked.connect(self.show_redundancy)
        audit_toolbar.addWidget(self.redundancy_button)
        self.optimization_button = QPushButton('Optimization Center (experimental)')
        self.optimization_button.setEnabled(False)
        self.optimization_button.clicked.connect(self.open_optimization)
        self.optimization_button.hide()  # Experimental duplicate GUI paused; CLI remains available.
        self.insights_button = QPushButton('Storage Insights')
        self.insights_button.setEnabled(False)
        self.insights_button.clicked.connect(self.open_insights)
        audit_toolbar.addWidget(self.insights_button)
        self.categories_button = QPushButton('Category Explorer')
        self.categories_button.setEnabled(False)
        self.categories_button.clicked.connect(self.open_categories)
        audit_toolbar.addWidget(self.categories_button)
        self.other_button = QPushButton('Explain Other')
        self.other_button.setEnabled(False)
        self.other_button.clicked.connect(self.open_other)
        audit_toolbar.addWidget(self.other_button)
        self.other_button.hide()  # Available through existing API; no duplicate navigation.
        audit_toolbar.addWidget(QLabel('Read-only · Python projects, .venv, caches'), 1)
        self.audit_toolbar_widget = QWidget()
        self.audit_toolbar_widget.setLayout(audit_toolbar)
        outer.addWidget(self.audit_toolbar_widget)
        self.advanced_label.hide()
        self.audit_toolbar_widget.hide()
        self.audit_panel = QFrame()
        self.audit_panel.setObjectName('panel')
        audit_layout = QVBoxLayout(self.audit_panel)
        audit_layout.addWidget(QLabel('PROJECT INTELLIGENCE  ·  Double-click a row to explore its folder'))
        self.audit_summary = QLabel('Scan a folder first.')
        audit_layout.addWidget(self.audit_summary)
        self.audit_tree = QTreeWidget()
        self.audit_tree.setColumnCount(5)
        self.audit_tree.setHeaderLabels(['Category', 'Location', 'Size', 'Status', 'Explanation'])
        self.audit_tree.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.audit_tree.setColumnWidth(0, 170)
        self.audit_tree.setColumnWidth(1, 480)
        self.audit_tree.setColumnWidth(2, 115)
        self.audit_tree.setColumnWidth(3, 110)
        self.audit_tree.setColumnWidth(4, 650)
        self.audit_tree.setAlternatingRowColors(True)
        self.audit_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.audit_tree.itemDoubleClicked.connect(self.audit_open)
        audit_layout.addWidget(self.audit_tree)
        self.audit_back = QPushButton('← Back to storage map')
        self.audit_back.clicked.connect(self.hide_audit)
        audit_layout.addWidget(self.audit_back)
        self.audit_panel.hide()
        outer.addWidget(self.audit_panel, 1)

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.bubble_panel = QFrame()
        self.bubble_panel.setObjectName('panel')
        bubble_layout = QVBoxLayout(self.bubble_panel)
        map_toolbar = QHBoxLayout()
        map_toolbar.addWidget(QLabel('STORAGE EXPLORER  ·  Select perspective and visualization'))
        map_toolbar.addStretch()
        reset = QPushButton('Reset zoom')
        reset.clicked.connect(self.fit_bubbles)
        map_toolbar.addWidget(reset)
        # Keep navigation actions together on the same header row.
        self.back.setMinimumWidth(112)
        map_toolbar.addWidget(self.back)
        bubble_layout.addLayout(map_toolbar)
        self.scene = QGraphicsScene(self)
        self.scene.setBackgroundBrush(QBrush(QColor(PANEL)))
        self.view = BubbleView(self.scene)
        self.view.zoom_callback = self.update_bubble_labels
        self.view.setFrameShape(QFrame.Shape.NoFrame)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setBackgroundBrush(QBrush(QColor(PANEL)))
        self.explorer_controls = QHBoxLayout()
        self.explorer_controls.setSpacing(8)
        self.perspective = QComboBox()
        self.perspective.addItems(['Folders', 'Categories', 'File types'])
        self.perspective.currentIndexChanged.connect(self._change_perspective)
        self.perspective.hide()  # Internal compatibility: the visible control is a tab strip.
        self.perspective_buttons = []
        for idx, name in enumerate(('Folders', 'Categories', 'File types')):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setChecked(idx == 0)
            button.clicked.connect(lambda checked=False, i=idx: self.perspective.setCurrentIndex(i))
            self.perspective_buttons.append(button)
            self.explorer_controls.addWidget(button)
        self.explorer_controls.addSpacing(20)
        self.visualization = QComboBox()
        self.visualization.addItems(['Bubbles', 'Bars'])
        self.visualization.currentIndexChanged.connect(self._change_visualization)
        self.visualization.hide()
        self.visual_buttons = []
        for idx, name in enumerate(('◉ Bubbles', '☰ Bars')):
            button = QPushButton(name)
            button.setCheckable(True)
            button.setChecked(idx == 0)
            button.clicked.connect(lambda checked=False, i=idx: self.visualization.setCurrentIndex(i))
            self.visual_buttons.append(button)
            self.explorer_controls.addWidget(button)
        self.explorer_controls.addStretch()
        bubble_layout.addLayout(self.explorer_controls)
        self.drill_label = QLabel('Click a bubble or bar to explore. Categories and file types open a second level.')
        self.drill_label.setStyleSheet('color: #9AACC2; font-size: 11px;')
        bubble_layout.addWidget(self.drill_label)
        self.visual_stack = QStackedWidget()
        self.visual_stack.addWidget(self.view)
        self.bar_scroll = QScrollArea()
        self.bar_scroll.setWidgetResizable(True)
        self.bar_host = QWidget()
        self.bar_layout = QVBoxLayout(self.bar_host)
        self.bar_scroll.setWidget(self.bar_host)
        self.visual_stack.addWidget(self.bar_scroll)
        bubble_layout.addWidget(self.visual_stack, 1)
        self.splitter.addWidget(self.bubble_panel)

        self.file_panel = QFrame()
        self.file_panel.setObjectName('panel')
        files_layout = QVBoxLayout(self.file_panel)
        files_layout.addWidget(QLabel('FILE INSPECTOR  ·  Double-click a folder to enter'))
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['Name', 'Size', 'Type'])
        self.tree.setAlternatingRowColors(True)
        self.tree.setSortingEnabled(True)
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.itemDoubleClicked.connect(self.tree_open)
        self.tree.itemSelectionChanged.connect(self.tree_selected)
        files_layout.addWidget(self.tree, 1)
        self.details = QLabel('Select an item to see its full path and size.')
        self.details.setWordWrap(True)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        files_layout.addWidget(self.details)
        self.splitter.addWidget(self.file_panel)
        self.splitter.setSizes([770, 480])
        outer.addWidget(self.splitter, 1)
        self.status = QLabel('Ready · All scans are local. Nothing is modified or deleted.')
        self.status.setWordWrap(True)
        outer.addWidget(self.status)

    def stat(self, title, value, layout):
        frame = QFrame()
        frame.setObjectName('panel')
        col = QVBoxLayout(frame)
        caption = QLabel(title)
        caption.setStyleSheet('color: #9AACC2; font-size: 10px;')
        label = QLabel(value)
        label.setStyleSheet('font-size: 22px; font-weight: 700;')
        col.addWidget(caption)
        col.addWidget(label)
        layout.addWidget(frame, 1)
        return label

    def set_mode(self, index):
        self.bubble_panel.setVisible(index != 2)
        self.file_panel.setVisible(index != 1)
        if self.current_node and index != 2:
            self.fit_bubbles()

    def pick_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select folder or drive', os.path.expanduser('~'))
        if not path:
            return
        if self.thread and self.thread.isRunning():
            return
        self.choose.setEnabled(False)
        self.cancel.setEnabled(True)
        self.status.setText(f'Scanning {path} ...')
        self.thread = QThread(self)
        self.worker = ScanWorker(path)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.status.setText)
        self.worker.finished.connect(self.scan_finished)
        self.worker.failed.connect(self.scan_failed)
        self.worker.cancelled.connect(self.scan_cancelled)
        for signal in (self.worker.finished, self.worker.failed, self.worker.cancelled):
            signal.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.clear_thread)
        self.thread.start()

    def clear_thread(self):
        self.thread = None
        self.worker = None

    def cancel_scan(self):
        if self.worker:
            self.worker.cancel_event.set()
            self.status.setText('Cancelling scan…')
            self.cancel.setEnabled(False)

    def finish_scan_ui(self):
        self.choose.setEnabled(True)
        self.cancel.setEnabled(False)

    def scan_finished(self, root):
        self.finish_scan_ui()
        self.root_node = root
        self.audit_report = None
        self._perspective_cache.clear()
        self._drill_context = None
        self.audit_button.setEnabled(True)
        self.python_button.setEnabled(True)
        self.graph_button.setEnabled(True)
        self.redundancy_button.setEnabled(True)
        self.insights_button.setEnabled(True)
        self.categories_button.setEnabled(True)
        self.other_button.setEnabled(True)
        self.optimization_button.setEnabled(False)
        self.hide_audit()
        self.show_node(root)
        self.show_overview()

    def scan_failed(self, message):
        self.finish_scan_ui()
        self.status.setText('Scan failed')
        QMessageBox.warning(self, 'Scan error', message)

    def scan_cancelled(self):
        self.finish_scan_ui()
        self.status.setText('Scan cancelled. Previous results remain available.')

    def show_audit(self):
        if self.root_node is None:
            return
        self.audit_report = audit_tree(self.root_node)
        r = self.audit_report
        self.audit_summary.setText(
            f'{len(r.projects)} projects · {len(r.environments)} virtual environments · '
            f'{len(r.caches)} caches · {len(r.python_executables)} Python executables · '
            f'{len(r.protected)} bundled components · {len(r.possible_versions)} version candidates · '
            f'{r.access_errors} scan access errors | No deletion recommendations.')
        self.audit_tree.clear()
        for finding in r.findings:
            item = QTreeWidgetItem([finding.kind, finding.path, format_size(finding.size), finding.severity, finding.detail])
            item.setToolTip(1, finding.path)
            item.setToolTip(4, finding.detail)
            item.setData(0, Qt.ItemDataRole.UserRole, finding.path)
            self.audit_tree.addTopLevelItem(item)
        self.splitter.hide()
        self.audit_panel.show()
        self.status.setText('Developer audit complete · Only scanned paths were inspected · No files modified.')

    def show_python_map(self):
        if self.root_node is None:
            return
        result = inspect_python(self.root_node)
        self.audit_tree.clear()
        self.audit_summary.setText(
            f'{len(result.links)} non-temporary environments · {len(result.temporary_links)} temporary test artifacts · '
            f'{len(result.installation_candidates)} standalone Python executable candidates · '
            f'{len(result.embedded_executables)} embedded executables · '
            f'{result.audit.access_errors} access errors | Read-only, no deletion suggestions.')
        for link in result.links:
            project = link.project or 'No project marker found'
            base = link.base_executable or 'Unknown base Python'
            detail = (f'Confidence: {link.confidence} | Project: {project} | Base: {base} | '
                      f'Python: {link.version or "unknown"} | '
                      f'Package metadata: {link.installed_packages} | {link.explanation}')
            item = QTreeWidgetItem(['Environment', link.path, format_size(link.size), link.state, detail])
            item.setData(0, Qt.ItemDataRole.UserRole, link.path)
            item.setToolTip(1, link.path)
            item.setToolTip(4, detail)
            self.audit_tree.addTopLevelItem(item)
        for link in result.temporary_links:
            detail = f'Temporary test fixture | {link.explanation}'
            item = QTreeWidgetItem(['Temporary environment', link.path, format_size(link.size), 'Temporary', detail])
            item.setData(0, Qt.ItemDataRole.UserRole, link.path)
            item.setToolTip(1, link.path)
            item.setToolTip(4, detail)
            self.audit_tree.addTopLevelItem(item)
        for path in result.installation_candidates:
            item = QTreeWidgetItem(['Python executable', path, '—', 'Unverified',
                'Executable found outside recognized embedded-software paths. Not executed.'])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self.audit_tree.addTopLevelItem(item)
        for path in result.embedded_executables:
            item = QTreeWidgetItem(['Embedded Python', path, '—', 'Protected',
                'Likely bundled with another application. Do not remove manually.'])
            item.setData(0, Qt.ItemDataRole.UserRole, path)
            self.audit_tree.addTopLevelItem(item)
        self.splitter.hide()
        self.audit_panel.show()
        self.status.setText('Python environment map · Offline and read-only · Relationships are heuristic.')

    def show_redundancy(self):
        if self.root_node is None:
            return
        # Metadata comparison only in the UI: hashing a whole drive could freeze Qt.
        # The CLI supports optional explicit hashing separately.
        result = analyze_redundancy(self.root_node)
        self.audit_tree.clear()
        self.audit_summary.setText(
            f'{len(result.insights)} insights · {result.exact_duplicate_groups} exact duplicate groups checked '
            f'· Metadata analysis only · {self.root_node.errors} scan access errors · Read-only')
        for finding in result.insights:
            item = QTreeWidgetItem([finding.kind, finding.path,
                format_size(finding.size), finding.status, finding.explanation])
            item.setData(0, Qt.ItemDataRole.UserRole, finding.path)
            item.setToolTip(1, finding.path)
            item.setToolTip(4, finding.explanation)
            self.audit_tree.addTopLevelItem(item)
        self.splitter.hide()
        self.audit_panel.show()
        self.status.setText('Redundancy report · No deletion recommendations · File hashing not run.')

    def show_overview(self):
        self._active_section = 'Explorer'
        self.advanced_label.hide()
        self.audit_toolbar_widget.hide()
        self.hide_audit()
        self.refresh_perspective()

    def show_developer_hub(self):
        self._active_section = 'Developer Hub'
        self.advanced_label.show()
        self.audit_toolbar_widget.show()
        if self.root_node is not None:
            self.show_audit()
        else:
            self.status.setText('Scan a folder or drive before opening Developer Hub.')

    def open_system_health(self):
        if self.root_node is not None:
            self.status.setText('⏳ Preparing System Health insights… this may take a few seconds on large scans.')
            QApplication.processEvents()
            try:
                SystemHealthDialog(self.root_node, self).exec()
            finally:
                self.status.setText('✓ System Health ready · Offline / Read-only')
        else:
            self.status.setText('Scan a folder or drive before opening System Health.')

    def open_insights(self):
        if self.root_node is not None:
            InsightsDialog(self.root_node, self.show_node, self).exec()

    def open_relationships(self):
        if self.root_node is not None:
            RelationshipDialog(self.root_node, self.show_node, self).exec()

    def open_categories(self):
        if self.root_node is not None:
            CategoriesDialog(self.root_node, self.show_node, self).exec()

    def open_other(self):
        if self.root_node is not None:
            OtherInspectorDialog(self.root_node, self.show_node, self).exec()

    def open_optimization(self):
        if self.root_node is None:
            return
        dialog = OptimizationDialog(self.root_node, self)
        dialog.exec()

    def hide_audit(self):
        self.audit_panel.hide()
        self.splitter.show()

    def audit_open(self, item, _column):
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if not path or not self.root_node:
            return
        target = path if os.path.isdir(path) else os.path.dirname(path)
        stack = [self.root_node]
        while stack:
            node = stack.pop()
            if node.path == target:
                self.hide_audit()
                self.show_node(node)
                return
            stack.extend(child for child in node.children if child.is_dir)
        self.status.setText('Folder is not available in the scanned tree.')

    def show_node(self, node):
        self.current_node = node
        self.selected_node = None
        self.bubble_items.clear()
        self.scene.clear()
        self.scene.setSceneRect(QRectF(0, 0, 850, 590))
        children = sorted(node.children, key=lambda n: n.size, reverse=True)
        for index, (child, x, y, r) in enumerate(layout_bubbles(children, 850, 590)):
            color = COLORS[index % len(COLORS)]
            bubble = Bubble(child, x, y, r, color, self.select_node, self.show_node)
            self.scene.addItem(bubble)
            self.bubble_items[child.path] = bubble
        self.fit_bubbles()
        self.tree.blockSignals(True)
        self.tree.clear()
        for child in children:
            kind = 'Folder' if child.is_dir else (os.path.splitext(child.name)[1].lower() or 'File')
            item = QTreeWidgetItem([child.name, format_size(child.size), kind])
            item.setData(0, Qt.ItemDataRole.UserRole, child)
            item.setData(1, Qt.ItemDataRole.UserRole, child.size)
            self.tree.addTopLevelItem(item)
        self.tree.sortItems(1, Qt.SortOrder.DescendingOrder)
        self.tree.blockSignals(False)
        self.size_label.setText(format_size(node.size))
        self.files_label.setText(f'{node.total_files:,}')
        self.errors_label.setText(str(node.errors))
        self.breadcrumb.setText(node.path)
        self.details.setText('Select a bubble or file to inspect it.')
        self.status.setText(f'{len(children):,} immediate entries · showing up to 45 largest bubbles · {node.errors} access errors')
        self.back.setEnabled(node is not self.root_node)
        if self._active_section == "Explorer":
            self.refresh_perspective()

    def _change_perspective(self, *_):
        self._drill_context = None
        self._sync_explorer_buttons()
        self.refresh_perspective()

    def _change_visualization(self, *_):
        self._sync_explorer_buttons()
        self.refresh_perspective()

    def _sync_explorer_buttons(self):
        for i, button in enumerate(self.perspective_buttons):
            button.setChecked(i == self.perspective.currentIndex())
        for i, button in enumerate(self.visual_buttons):
            button.setChecked(i == self.visualization.currentIndex())
        for button in self.perspective_buttons + self.visual_buttons:
            button.setStyleSheet('background: #365681; color: white; font-weight: 600;' if button.isChecked()
                                 else 'background: #202B3A; color: #AAB9CC;')

    def _perspective_rows(self):
        if self.root_node is None:
            return []
        perspective = self.perspective.currentText()
        if perspective == 'Folders':
            node = self.current_node or self.root_node
            return [(c.name, c.size, c) for c in sorted(node.children, key=lambda n: -n.size)]
        if self._drill_context and self._drill_context[0] == perspective:
            return self._drill_context[2]
        if perspective not in self._perspective_cache:
            if perspective == 'Categories':
                report = build_purpose_report(self.root_node)
                rows = [(t.purpose, t.bytes, None) for t in report.totals if t.bytes]
            else:
                report = build_insights(self.root_node, max_folders=0)
                rows = [(t.category, t.bytes, None) for t in report.categories if t.bytes]
            self._perspective_cache[perspective] = (rows, report)
        return self._perspective_cache[perspective][0]

    def refresh_perspective(self, *_):
        if not hasattr(self, 'visual_stack'):
            return
        perspective = self.perspective.currentText()
        visual = self.visualization.currentText()
        self.visual_stack.setCurrentIndex(0 if visual == 'Bubbles' else 1)
        if self.root_node is None:
            return
        if perspective != 'Folders' and perspective not in self._perspective_cache and not self._drill_context:
            self.status.setText(f'⏳ Analyzing {perspective.lower()} from the existing scan… first load may take a few seconds.')
            QApplication.processEvents()
        rows = self._perspective_rows()
        if perspective != 'Folders':
            self.status.setText(f'✓ {perspective} ready · Cached for faster switching · Read-only')
        if self._drill_context and self._drill_context[0] == perspective:
            self.drill_label.setText(f'{perspective}  /  {self._drill_context[1]}   ·   Click a folder to explore it · Back to return')
            self.back.setEnabled(True)
        else:
            self.drill_label.setText('Click a bubble or bar to explore. Categories and file types open a second level.')
            self.back.setEnabled(self.current_node is not self.root_node)
        if visual == 'Bars':
            while self.bar_layout.count():
                item = self.bar_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            total = max(1, sum(size for _, size, _ in rows))
            for name, size, node in sorted(rows, key=lambda x: -x[1])[:150]:
                button = QPushButton(f'{name}   ·   {format_size(size)}   ·   {size / total:.1%}')
                button.setToolTip('Click to explore')
                button.clicked.connect(lambda _, n=name, item=node: self._drill_down(n, item))
                self.bar_layout.addWidget(button)
                progress = QProgressBar()
                progress.setRange(0, 1000)
                progress.setValue(round(1000 * size / total))
                progress.setTextVisible(False)
                progress.setFixedHeight(9)
                self.bar_layout.addWidget(progress)
            self.bar_layout.addStretch()
        elif perspective == 'Folders':
            self.show_folder_bubbles_only()
        else:
            self.scene.clear()
            self.bubble_items.clear()
            self.scene.setSceneRect(QRectF(0, 0, 850, 590))
            pseudo = [FileNode(name=name, path=f'category:{name}', size=size, is_dir=True)
                      for name, size, _ in sorted(rows, key=lambda row: -row[1])[:45]]
            for i, (item, x, y, r) in enumerate(layout_bubbles(pseudo, 850, 590)):
                matching = next((n for name, _, n in rows if name == item.name), None)
                bubble = Bubble(item, x, y, r, COLORS[i % len(COLORS)],
                                lambda n, m=matching: self._drill_down(n.name, m),
                                lambda n, m=matching: self._drill_down(n.name, m))
                self.scene.addItem(bubble)
                self.bubble_items[item.path] = bubble
            self.fit_bubbles()

    def show_folder_bubbles_only(self):
        if self.current_node is None:
            return
        self.scene.clear()
        self.bubble_items.clear()
        children = sorted(self.current_node.children, key=lambda n: -n.size)
        for i, (child, x, y, r) in enumerate(layout_bubbles(children, 850, 590)):
            bubble = Bubble(child, x, y, r, COLORS[i % len(COLORS)], self.select_node, self.show_node)
            self.scene.addItem(bubble)
            self.bubble_items[child.path] = bubble
        self.fit_bubbles()

    def _drill_down(self, name, node):
        if node is not None:
            if node.is_dir:
                self._drill_context = None
                self.perspective.setCurrentIndex(0)
                self.show_node(node)
            else:
                self.select_node(node)
            return
        if self.root_node is None:
            return
        perspective = self.perspective.currentText()
        if self._drill_context is not None:
            return
        report = self._perspective_cache.get(perspective, (None, None))[1]
        if perspective == 'Categories':
            entries = [(e.node, e.bytes) for e in report.entries if e.purpose == name]
        else:
            from .storage_insights import category_for
            entries = []
            stack = [self.root_node]
            while stack:
                current = stack.pop()
                if current.is_dir:
                    stack.extend(current.children)
                elif category_for(current.name) == name:
                    entries.append((current, current.size))
        entries.sort(key=lambda pair: -pair[1])
        # Keep all matching bytes in the second level; only the visual renderer caps nodes.
        rows = [(n.path, size, n) for n, size in entries if size > 0]
        self._drill_context = (perspective, name, rows)
        self.refresh_perspective()
        self.tree.blockSignals(True)
        self.tree.clear()
        for item_node, size in entries[:250]:
            item = QTreeWidgetItem([item_node.path, format_size(size), 'Folder' if item_node.is_dir else 'File'])
            item.setData(0, Qt.ItemDataRole.UserRole, item_node)
            item.setData(1, Qt.ItemDataRole.UserRole, size)
            self.tree.addTopLevelItem(item)
        self.tree.blockSignals(False)
        self.details.setText(f'{name} · {len(entries):,} matching entries. Showing up to 250 in inspector.')

    def select_node(self, node):
        self.selected_node = node
        for bubble in self.bubble_items.values():
            bubble.set_selected(bubble.node.path == node.path)
        self.details.setText(f'{node.path}\n{format_size(node.size)} · {"Folder" if node.is_dir else "File"}')
        self.tree.blockSignals(True)
        for i in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(i)
            if item.data(0, Qt.ItemDataRole.UserRole).path == node.path:
                self.tree.setCurrentItem(item)
                break
        self.tree.blockSignals(False)

    def tree_selected(self):
        items = self.tree.selectedItems()
        if items:
            node = items[0].data(0, Qt.ItemDataRole.UserRole)
            if node:
                self.select_node(node)

    def tree_open(self, item, _column):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node and node.is_dir:
            self.show_node(node)

    def go_up(self):
        if self._drill_context is not None:
            self._drill_context = None
            self.refresh_perspective()
            return
        if self.current_node is None or self.current_node is self.root_node:
            return
        parent_path = os.path.dirname(self.current_node.path)
        node = self.root_node
        if node.path == parent_path:
            self.show_node(node)
            return
        # Iterative lookup avoids Python recursion limits on deeply nested paths.
        stack = [node]
        while stack:
            candidate = stack.pop()
            if candidate.path == parent_path:
                self.show_node(candidate)
                return
            stack.extend(child for child in candidate.children if child.is_dir)

    def update_bubble_labels(self):
        scale = self.view.transform().m11()
        for bubble in self.bubble_items.values():
            bubble.update_label(scale)

    def fit_bubbles(self):
        self.view.resetTransform()
        self.view.fitInView(self.scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.view.centerOn(self.scene.sceneRect().center())
        self.update_bubble_labels()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Preserve user zoom/pan when resizing the window.

    def closeEvent(self, event):
        if self.thread and self.thread.isRunning():
            self.cancel_scan()
            self.thread.quit()
            self.thread.wait(5000)
            if self.thread.isRunning():
                event.ignore()
                self.status.setText('Waiting for scan to stop before closing…')
                return
        super().closeEvent(event)

def main():
    app = QApplication(sys.argv)
    window = Window()
    window.show()
    sys.exit(app.exec())
