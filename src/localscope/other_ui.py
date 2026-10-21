"""Responsive offline storage intelligence explorer (read-only)."""
from PySide6.QtCore import Qt, QObject, QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTabWidget, QTreeWidget,
    QTreeWidgetItem, QHeaderView, QPushButton, QHBoxLayout)
from .models import format_size
from .other_inspector import inspect_other, AnalysisCancelled
from .smart_categories import build_purpose_report

class InspectorWorker(QObject):
    completed = Signal(object, object)
    failed = Signal(str)
    finished = Signal()

    def __init__(self, root):
        super().__init__()
        self.root = root
        import threading
        self.stop = threading.Event()

    def run(self):
        try:
            if self.stop.is_set():
                return
            purpose = build_purpose_report(self.root)
            if self.stop.is_set():
                return
            unknown = inspect_other(self.root, purpose, limit=50, cancelled=self.stop.is_set)
            if not self.stop.is_set():
                self.completed.emit(purpose, unknown)
        except AnalysisCancelled:
            pass
        except Exception as exc:
            self.failed.emit(f'{type(exc).__name__}: {exc}')
        finally:
            self.finished.emit()

class OtherInspectorDialog(QDialog):
    def __init__(self, root, navigate, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LocalScope — Storage Intelligence Explorer')
        self.resize(1120, 760)
        self.navigate = navigate
        self.setStyleSheet("""
            QDialog {background:#101722;color:#EAF0F9;font:12px "Segoe UI";}
            QLabel {color:#EAF0F9;}
            QTreeWidget {background:#172233;alternate-background-color:#1D2B3D;color:#EAF0F9;border:0;}
            QTreeWidget::item {padding:6px;}
            QHeaderView::section {background:#23344A;color:#B9C8DB;padding:7px;border:0;}
            QPushButton {background:#273950;color:white;padding:9px;border-radius:5px;}
        """)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('STORAGE INTELLIGENCE  ·  Games and Other · Offline · Read-only'))
        self.status = QLabel('Analyzing existing scan in background…')
        layout.addWidget(self.status)
        layout.addWidget(QLabel('Top 50 shown per tab. Unknown does NOT mean safe to delete.'))
        self.tabs = QTabWidget()
        self.locations = self._table(['Unknown location / file', 'Size', 'Why unclassified'])
        self.games = self._table(['Game / library folder', 'Size', 'Evidence'])
        self.extensions = self._table(['Extension', 'Size', 'Files'])
        self.tabs.addTab(self.locations, 'Other · top 50')
        self.tabs.addTab(self.games, 'Games · top 50')
        self.tabs.addTab(self.extensions, 'Unknown extensions · top 50')
        layout.addWidget(self.tabs)
        controls = QHBoxLayout()
        self.cancel_button = QPushButton('Cancel analysis')
        self.cancel_button.clicked.connect(self.cancel_analysis)
        controls.addWidget(self.cancel_button)
        open_button = QPushButton('Explore selected location in storage map')
        open_button.clicked.connect(self._open_selected)
        controls.addWidget(open_button)
        layout.addLayout(controls)
        self.locations.itemDoubleClicked.connect(self._open)
        self.games.itemDoubleClicked.connect(self._open)
        self.games.itemExpanded.connect(self._expand)
        self.locations.itemExpanded.connect(self._expand)
        self.worker = InspectorWorker(root)
        self.thread = QThread(self)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.completed.connect(self._populate)
        self.worker.failed.connect(self._failed)
        self.worker.finished.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self._finished)
        self.thread.start()

    def _table(self, headings):
        tree = QTreeWidget()
        tree.setColumnCount(3)
        tree.setHeaderLabels(headings)
        tree.setAlternatingRowColors(True)
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        return tree

    def _populate(self, purpose, unknown):
        self.status.setText(f'Other: {format_size(unknown.total)} · {unknown.file_count:,} files · '
                            f'Games: {format_size(next(t.bytes for t in purpose.totals if t.purpose == "Games"))}')
        for row in unknown.items:
            item = QTreeWidgetItem([row.path, format_size(row.size), row.reason])
            item.setData(0, Qt.ItemDataRole.UserRole, row.parent or row.node)
            item.setToolTip(0, row.path)
            self.locations.addTopLevelItem(item)
            self._mark_expandable(item, row.node)
        games = [entry for entry in purpose.entries if entry.purpose == 'Games']
        for row in sorted(games, key=lambda e: -e.bytes)[:50]:
            item = QTreeWidgetItem([row.node.path, format_size(row.bytes), row.explanation])
            item.setData(0, Qt.ItemDataRole.UserRole, row.node)
            item.setToolTip(0, row.node.path)
            self.games.addTopLevelItem(item)
            self._mark_expandable(item, row.node)
        for ext, size, count in unknown.extensions:
            self.extensions.addTopLevelItem(QTreeWidgetItem([ext, format_size(size), f'{count:,}']))

    def _mark_expandable(self, item, node):
        if node.is_dir and any(c.is_dir for c in node.children):
            item.addChild(QTreeWidgetItem(['Expand to see subfolders (max 50)']))

    def _expand(self, item):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node is None or not node.is_dir or item.data(1, Qt.ItemDataRole.UserRole):
            return
        item.takeChildren()
        for child in sorted((c for c in node.children if c.is_dir),
                            key=lambda c: -c.size)[:50]:
            row = QTreeWidgetItem([child.name, format_size(child.size), 'Child folder · classification inherited'])
            row.setData(0, Qt.ItemDataRole.UserRole, child)
            item.addChild(row)
            self._mark_expandable(row, child)
        item.setData(1, Qt.ItemDataRole.UserRole, True)

    def _failed(self, message):
        self.status.setText('Analysis failed: ' + message)

    def _finished(self):
        self.cancel_button.setEnabled(False)
        if self.worker.stop.is_set():
            self.status.setText('Analysis cancelled.')

    def cancel_analysis(self):
        self.worker.stop.set()
        self.status.setText('Cancelling analysis…')
        self.cancel_button.setEnabled(False)

    def _open(self, item, *_):
        node = item.data(0, Qt.ItemDataRole.UserRole)
        if node is not None:
            self.navigate(node)
            self.close()

    def _open_selected(self):
        selected = self.tabs.currentWidget().currentItem()
        if selected is not None:
            self._open(selected)

    def closeEvent(self, event):
        # Do not destroy a running QThread; cancel and keep the dialog alive until it exits.
        if self.thread.isRunning():
            self.cancel_analysis()
            self.status.setText('Cancelling analysis before closing…')
            event.ignore()
            self.thread.finished.connect(self.close)
        else:
            super().closeEvent(event)
