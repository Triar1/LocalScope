"""Read-only, actionable Windows storage education using existing scan metadata."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QTabWidget, QWidget, QTextBrowser)
from .models import format_size
from .system_health import system_findings, windows_storage_areas
from .redundancy import analyze_redundancy

GUIDES = {
    'hiberfil.sys': (
        'What it does: Windows stores hibernation state here; it may also support Fast Startup.\n\n'
        'Check first: Do you use Hibernate? Is Fast Startup important on this machine?\n\n'
        'How to review: Open Windows Terminal as administrator, run powercfg /a to inspect available sleep states. '
        'If you explicitly choose to disable hibernation, powercfg /hibernate off removes hiberfil.sys after Windows applies the change. '
        'Restore with powercfg /hibernate on. This is an optional system change, NOT performed by LocalScope.\n\n'
        'Trade-off: Hibernate and possibly Fast Startup stop working. On laptops, consider battery and sleep behavior.'),
    'pagefile.sys': (
        'What it does: Windows uses the paging file for memory management and crash dumps. '
        'Its size is not automatically wasted space.\n\n'
        'How to review: Settings → System → About → Advanced system settings → Performance Settings → Advanced → Virtual memory. '
        'Prefer System managed size unless you have a specific, well-understood reason to change it.\n\n'
        'Warning: Disabling or aggressively shrinking the pagefile can cause application failures and prevent crash dumps.'),
    'swapfile.sys': (
        'Windows manages this file as part of memory management. Do not manually delete it. '
        'Review Windows virtual-memory settings only if diagnosing a specific issue.'),
    'memory.dmp': (
        'A memory dump can help diagnose a Windows crash. If you are no longer investigating a crash, '
        'review Settings → System → Storage → Temporary files or Disk Cleanup for system-error memory dump files. '
        'Review the selected categories before confirming cleanup.'),
}

GENERAL = (
    'WINDOWS UPDATE AND COMPONENT STORE (WinSxS)\n'
    'Open Settings → System → Storage → Temporary files. Review Windows Update Cleanup and other items. '
    'Windows may need a restart. Do not manually delete WinSxS: its apparent folder size includes hard links. '
    'For a more accurate component-store assessment, an administrator can run:\n'
    'DISM /Online /Cleanup-Image /AnalyzeComponentStore\n'
    'This command analyzes the store; it does not clean it.\n\n'
    'TEMPORARY FILES AND CACHES\n'
    'Use Windows Storage recommendations or Storage Sense. Review Downloads carefully; it may contain personal files. '
    'GPU caches, application caches and OneDrive placeholders require context; never assume they are safe to delete.\n\n'
    'IMPORTANT\n'
    'These instructions describe optional manual Windows actions. LocalScope never executes commands, '
    'modifies settings, deletes files or promises reclaimable space. Incomplete scans and access errors can hide data.'
)

class SystemHealthDialog(QDialog):
    def __init__(self, root, parent=None):
        super().__init__(parent)
        self.setWindowTitle('LocalScope — System Health & Redundancy')
        self.resize(1100, 760)
        self.setStyleSheet('''
            QDialog, QWidget { background: #101722; color: #EAF0F9; font: 12px "Segoe UI"; }
            QLabel#healthTitle { color: #EAF2FF; font-size: 19px; font-weight: 700; padding: 7px 2px; }
            QLabel#healthMeta { color: #8DCDBE; padding: 4px 2px 10px 2px; }
            QLabel#healthHint { color: #A8BED9; padding: 8px 4px; }
            QTabWidget::pane { border: 1px solid #2B405B; border-radius: 7px; background: #172233; }
            QTabBar::tab { background: #22334A; color: #B9CBE0; padding: 11px 18px; border: 1px solid #30465E; }
            QTabBar::tab:selected { background: #31527B; color: white; border-bottom: 2px solid #66B9E8; }
            QTabBar::tab:hover { background: #35506E; }
            QTreeWidget { background: #172233; alternate-background-color: #1E2C40; border: 1px solid #283C54; border-radius: 6px; outline: none; }
            QTreeWidget::item { padding: 9px 5px; }
            QTreeWidget::item:selected { background: #355A83; color: #FFFFFF; }
            QHeaderView::section { background: #263B54; color: #BBD8F2; padding: 10px; border: none; }
            QTextBrowser { background: #152237; color: #D9E6F5; border: 1px solid #344B65; border-radius: 7px; padding: 12px; }
        ''')
        layout = QVBoxLayout(self)
        title = QLabel('✚  SYSTEM HEALTH  ·  Understand your storage before taking action')
        title.setObjectName('healthTitle')
        layout.addWidget(title)
        meta = QLabel(f'●  {format_size(root.size)} scanned     ◈  {root.errors} access errors     ✓  Offline / Read-only')
        meta.setObjectName('healthMeta')
        layout.addWidget(meta)
        tabs = QTabWidget()
        layout.addWidget(tabs)
        system = QWidget()
        sl = QVBoxLayout(system)
        sl.addWidget(QLabel('◈  Detected system files — occupied bytes, NOT guaranteed recoverable space.'))
        table = QTreeWidget()
        table.setAlternatingRowColors(True)
        table.setColumnCount(3)
        table.setHeaderLabels(['File', 'Size', 'What it does'])
        table.setColumnWidth(0, 450)
        table.setColumnWidth(1, 120)
        sl.addWidget(table, 2)
        detail = QTextBrowser()
        detail.setOpenExternalLinks(False)
        sl.addWidget(detail, 3)
        findings = system_findings(root)
        for finding in findings:
            row = QTreeWidgetItem([finding.path, format_size(finding.size), finding.explanation])
            row.setData(0, 256, finding.name.lower())
            table.addTopLevelItem(row)
        def explain():
            item = table.currentItem()
            if item:
                name = item.data(0, 256)
                detail.setPlainText(GUIDES.get(name, 'Windows-managed file. Do not delete manually.') + '\n\n' + GENERAL)
        table.itemSelectionChanged.connect(explain)
        detail.setPlainText('Select a file above to see its purpose, review steps and trade-offs.\n\n' + GENERAL)
        areas = QWidget()
        al = QVBoxLayout(areas)
        al.addWidget(QLabel('▣  Windows storage areas — actual scanned sizes, NOT guaranteed recoverable space.'))
        area_table = QTreeWidget()
        area_table.setAlternatingRowColors(True)
        area_table.setColumnCount(3)
        area_table.setHeaderLabels(['Location', 'Scanned size', 'Purpose'])
        area_table.setColumnWidth(0, 460)
        area_table.setColumnWidth(1, 135)
        area_detail = QTextBrowser()
        area_detail.setOpenExternalLinks(False)
        observed = windows_storage_areas(root)
        for area in observed:
            item = QTreeWidgetItem([area.path, format_size(area.size), area.explanation])
            item.setData(0, 256, area.advice)
            area_table.addTopLevelItem(item)
        def show_area():
            item = area_table.currentItem()
            if item:
                area_detail.setPlainText(item.text(2) + '\n\nRecommended review: ' + item.data(0, 256)
                    + '\n\nLocalScope does not change files or Windows settings.')
        area_table.itemSelectionChanged.connect(show_area)
        al.addWidget(area_table, 3)
        al.addWidget(area_detail, 2)
        if not observed:
            area_detail.setPlainText('No drive-root Windows areas were observed in this scan. Scan a drive root to see this overview. No size is estimated.')
        else:
            area_detail.setPlainText('Select an area to understand its purpose and safe review steps. Sizes can include hard-linked files and must not be added to file-level totals.')
        tabs.addTab(areas, '▣  Windows storage overview')
        tabs.addTab(system, '◈  Windows files & actions')
        redundancy = QWidget()
        rl = QVBoxLayout(redundancy)
        rl.addWidget(QLabel('◇  Redundancy insights — metadata only, no full-drive hashing or deletion.'))
        result = analyze_redundancy(root)
        rl.addWidget(QLabel(f'{len(result.insights)} insights · {result.exact_duplicate_groups} verified duplicate groups in this report'))
        rt = QTreeWidget()
        rt.setAlternatingRowColors(True)
        rt.setColumnCount(4)
        rt.setHeaderLabels(['Type', 'Location', 'Size', 'Explanation'])
        rt.setColumnWidth(1, 350)
        for finding in result.insights:
            rt.addTopLevelItem(QTreeWidgetItem([finding.kind, finding.path, format_size(finding.size), finding.explanation]))
        rl.addWidget(rt)
        rl.addWidget(QLabel('Matching project versions or environments does NOT mean a copy is safe to delete.'))
        tabs.addTab(redundancy, '◇  Redundancy insights')
