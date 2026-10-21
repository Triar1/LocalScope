"""Optimization Center: asynchronous read-only duplicate inspection."""
from __future__ import annotations
import os
import subprocess
import threading
import time
from PySide6.QtCore import QObject, QThread, Signal, Qt, Slot, QTimer
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QProgressBar, QTreeWidget, QTreeWidgetItem, QComboBox, QMessageBox, QSplitter,
    QWidget, QAbstractItemView, QFileDialog)
from .models import format_size
from .optimization import find_duplicates, AnalysisCancelled
from .scanner import scan, ScanCancelled

class DuplicateWorker(QObject):
    finished = Signal(object, int, int)
    failed = Signal(str)
    cancelled = Signal()
    progress = Signal(int, int)
    status = Signal(str, int, int, str, int)
    group_found = Signal(object)
    diagnostic = Signal(str, str, object)

    def __init__(self, root, scope_path=None):
        super().__init__()
        self.root = root
        self.scope_path = scope_path
        self.stop_event = threading.Event()

    def run(self):
        try:
            target = self.root
            if self.scope_path and os.path.normcase(os.path.abspath(self.scope_path)) != os.path.normcase(os.path.abspath(self.root.path)):
                self.status.emit('Scanning selected folder', 0, 0, self.scope_path, 0)
                target = scan(self.scope_path, cancelled=self.stop_event.is_set,
                              progress=lambda message: self.status.emit('Scanning selected folder', 0, 0, message, 0))
            groups, hashed, skipped = find_duplicates(
                target, cancelled=self.stop_event.is_set,
                progress=lambda done, total: self.progress.emit(done, total),
                status=lambda phase, done, total, path, bytes_read: self.status.emit(phase, done, total, path, bytes_read),
                group_found=lambda group: self.group_found.emit(group),
                diagnostic=lambda kind, path, value: self.diagnostic.emit(kind, path, value))
            self.finished.emit(groups, hashed, skipped)
        except (AnalysisCancelled, ScanCancelled):
            self.cancelled.emit()
        except Exception as exc:
            self.failed.emit(str(exc))

class OptimizationDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.root = root
        self.groups = []
        self.scope_path = root.path
        self.thread = None
        self.worker = None
        self.last_update = 0.0
        self.last_phase = "Not started"
        self.heartbeat = QTimer(self)
        self.heartbeat.setInterval(1000)
        self.heartbeat.timeout.connect(self.update_heartbeat)
        self.setWindowTitle('LocalScope — Storage Optimization Center')
        self.resize(1100, 720)
        self.setStyleSheet('''QDialog,QWidget{background:#101722;color:#EAF0F9;font-family:Segoe UI;font-size:12px}
            QTreeWidget{background:#172233;alternate-background-color:#1D2B3D;border:0}
            QTreeWidget::item{padding:6px} QTreeWidget::item:selected{background:#304C71}
            QHeaderView::section{background:#23344A;color:#EAF0F9;padding:7px}
            QPushButton,QComboBox{background:#273950;border:1px solid #35465C;border-radius:6px;padding:7px}
            QPushButton:disabled{color:#7A8999}''')
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('STORAGE OPTIMIZATION CENTER  ·  Exact duplicate finder'))
        layout.addWidget(QLabel('Read-only · SHA-256 verifies identical bytes, not whether a copy is safe to delete.'))
        scope_controls = QHBoxLayout()
        self.scope_label = QLabel('Analysis scope: ' + self.scope_path)
        self.scope_label.setWordWrap(True)
        scope_controls.addWidget(self.scope_label, 1)
        self.scope_button = QPushButton('Choose folder…')
        self.scope_button.clicked.connect(self.choose_folder)
        scope_controls.addWidget(self.scope_button)
        layout.addLayout(scope_controls)
        controls = QHBoxLayout()
        self.start_button = QPushButton('Find exact duplicates')
        self.start_button.clicked.connect(self.start)
        controls.addWidget(self.start_button)
        self.cancel_button = QPushButton('Cancel analysis')
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel)
        controls.addWidget(self.cancel_button)
        controls.addWidget(QLabel('Minimum extra bytes:'))
        self.filter = QComboBox()
        for text, threshold in [('All', 0), ('100 KiB', 100*1024), ('1 MiB', 1024**2), ('10 MiB', 10*1024**2), ('100 MiB', 100*1024**2)]:
            self.filter.addItem(text, threshold)
        self.filter.currentIndexChanged.connect(self.populate)
        controls.addWidget(self.filter)
        controls.addStretch()
        layout.addLayout(controls)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)
        self.summary = QLabel('No duplicate scan run yet. Existing storage scan data will be reused.')
        layout.addWidget(self.summary)
        self.detail = QLabel('Phase, file and bytes read will appear here.')
        self.detail.setWordWrap(True)
        layout.addWidget(self.detail)
        splitter = QSplitter(Qt.Orientation.Vertical)
        self.table = QTreeWidget()
        self.table.setHeaderLabels(['Duplicate group', 'Copies', 'Extra identical bytes', 'Individual size'])
        self.table.setAlternatingRowColors(True)
        self.table.setColumnWidth(0, 570)
        self.table.setColumnWidth(1, 90)
        self.table.setColumnWidth(2, 190)
        self.table.itemSelectionChanged.connect(self.show_copies)
        splitter.addWidget(self.table)
        bottom = QWidget()
        bottom_layout = QVBoxLayout(bottom)
        bottom_layout.addWidget(QLabel('COPIES  ·  Select a file to open its location in Windows Explorer'))
        self.copies = QTreeWidget()
        self.copies.setHeaderLabels(['Full file path', 'Size'])
        self.copies.setColumnWidth(0, 820)
        self.copies.setAlternatingRowColors(True)
        bottom_layout.addWidget(self.copies)
        open_button = QPushButton('Show selected file in Windows Explorer')
        open_button.clicked.connect(self.open_selected)
        bottom_layout.addWidget(open_button)
        splitter.addWidget(bottom)
        splitter.setSizes([350, 260])
        layout.addWidget(splitter, 1)
        self.note = QLabel('Nothing will be deleted. OneDrive placeholders, hard links and file changes can affect disk-space estimates.')
        self.note.setWordWrap(True)
        layout.addWidget(self.note)

    def choose_folder(self):
        if self.thread is not None:
            return
        folder = QFileDialog.getExistingDirectory(self, 'Choose folder to analyze', self.scope_path)
        if folder:
            self.scope_path = folder
            self.scope_label.setText('Analysis scope: ' + folder)
            self.groups = []
            self.table.clear()
            self.copies.clear()
            self.summary.setText('Ready to analyze selected folder. No scan running.')

    def start(self):
        if self.thread is not None:
            return
        self.groups = []
        self.started_at = time.monotonic()
        self.last_update = self.started_at
        self.last_phase = "Indexing"
        self.heartbeat.start()
        self.table.clear()
        self.copies.clear()
        self.start_button.setEnabled(False)
        self.scope_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress_bar.setRange(0, 0)
        self.summary.setText('Starting analysis of: ' + self.scope_path)
        self.detail.setText('Preparing analysis…')
        self.thread = QThread(self)
        self.worker = DuplicateWorker(self.root, self.scope_path)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.update_progress, Qt.ConnectionType.QueuedConnection)
        self.worker.status.connect(self.update_status, Qt.ConnectionType.QueuedConnection)
        self.worker.group_found.connect(self.append_group)
        self.worker.diagnostic.connect(self.show_diagnostic)
        self.worker.finished.connect(self.finished)
        self.worker.failed.connect(self.failed)
        self.worker.cancelled.connect(self.cancelled)
        for sig in (self.worker.finished, self.worker.failed, self.worker.cancelled):
            sig.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(self.thread_done)
        self.thread.start()

    @Slot(int, int)
    def update_progress(self, done, total):
        # Status updates own the phase-aware progress bar. Avoid stale progress signals.
        return


    @Slot()
    def update_heartbeat(self):
        if self.thread is None:
            self.heartbeat.stop()
            return
        silence = int(time.monotonic() - self.last_update)
        if silence >= 5:
            self.detail.setText(f'No progress event for {silence}s during {self.last_phase}. Last known file: {self.detail.toolTip()} — a disk read may be slow.')

    @Slot(str, str, object)
    def show_diagnostic(self, kind, path, value):
        self.note.setText(f'{kind}: {path} ({value}) · Nothing will be deleted.')

    @Slot(str, int, int, str, int)
    def update_status(self, phase, done, total, path, bytes_read):
        self.last_update = time.monotonic()
        self.last_phase = phase
        if total <= 0:
            self.progress_bar.setRange(0, 0)  # unknown total during indexing
        else:
            self.progress_bar.setRange(0, max(total, 1))
            self.progress_bar.setValue(min(done, total))
        elapsed = max(time.monotonic() - self.started_at, 0.01)
        count = f'{done:,} nodes examined' if total <= 0 else f'{done:,} / {total:,} items'
        self.summary.setText(f'{phase}: {count} · {elapsed:.0f}s elapsed · {format_size(bytes_read)} read')
        self.detail.setText('Current: ' + (path if path else '—'))
        self.detail.setToolTip(path)

    def append_group(self, group):
        # Confirmed groups only; results are delivered in the final phase.
        self.groups.append(group)
        if group.extra_bytes >= self.filter.currentData():
            item = QTreeWidgetItem([os.path.basename(group.paths[0]), str(len(group.paths)),
                format_size(group.extra_bytes), format_size(group.size)])
            item.setData(0, Qt.ItemDataRole.UserRole, group)
            item.setToolTip(0, group.paths[0])
            self.table.addTopLevelItem(item)

    def finished(self, groups, hashed, skipped):
        self.groups = groups
        total = sum(g.extra_bytes for g in groups)
        self.summary.setText(f'{len(groups):,} duplicate groups · {format_size(total)} extra identical bytes (NOT confirmed recoverable) · {hashed:,} hashed · {skipped:,} skipped')
        self.progress_bar.setRange(0, 1)
        self.progress_bar.setValue(1)
        self.cancel_button.setEnabled(False)
        self.populate()

    def failed(self, error):
        self.summary.setText('Analysis failed: ' + error)
        self.progress_bar.setRange(0, 1)
        self.cancel_button.setEnabled(False)

    def cancelled(self):
        self.summary.setText('Analysis cancelled. No files changed.')
        self.progress_bar.setRange(0, 1)
        self.cancel_button.setEnabled(False)

    def thread_done(self):
        self.heartbeat.stop()
        self.thread = None
        self.worker = None
        self.start_button.setEnabled(True)
        self.scope_button.setEnabled(True)

    def cancel(self):
        if self.worker:
            self.worker.stop_event.set()
            self.cancel_button.setEnabled(False)
            self.summary.setText('Cancelling…')

    def populate(self, *_):
        self.table.clear()
        self.copies.clear()
        threshold = self.filter.currentData()
        for group in self.groups:
            if group.extra_bytes < threshold:
                continue
            item = QTreeWidgetItem([os.path.basename(group.paths[0]), str(len(group.paths)),
                format_size(group.extra_bytes), format_size(group.size)])
            item.setData(0, Qt.ItemDataRole.UserRole, group)
            item.setToolTip(0, group.paths[0])
            self.table.addTopLevelItem(item)

    def show_copies(self):
        self.copies.clear()
        item = self.table.currentItem()
        if not item:
            return
        group = item.data(0, Qt.ItemDataRole.UserRole)
        if not group:
            return
        for path in group.paths:
            child = QTreeWidgetItem([path, format_size(group.size)])
            child.setData(0, Qt.ItemDataRole.UserRole, path)
            self.copies.addTopLevelItem(child)

    def open_selected(self):
        item = self.copies.currentItem()
        if not item:
            return
        path = item.data(0, Qt.ItemDataRole.UserRole)
        if os.name == 'nt' and os.path.isfile(path):
            subprocess.Popen(['explorer.exe', '/select,', os.path.normpath(path)])
        else:
            QMessageBox.information(self, 'Unavailable', 'The file is unavailable or this is not Windows.')

    def closeEvent(self, event):
        if self.thread is not None:
            self.cancel()
            event.ignore()
            self.summary.setText('Please wait for the running analysis to stop before closing.')
        else:
            super().closeEvent(event)
