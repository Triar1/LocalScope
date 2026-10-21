"""Offline, read-only developer workspace audit. Never executes discovered binaries."""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import os
import re
from collections.abc import Callable
from .models import FileNode

PROJECT_MARKERS = ('pyproject.toml', 'requirements.txt', 'Pipfile', 'setup.py', 'poetry.lock', 'uv.lock')
VENV_MARKER = 'pyvenv.cfg'
CACHE_NAMES = {'__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.tox', '.nox'}

@dataclass
class Finding:
    kind: str
    path: str
    size: int
    detail: str
    severity: str = 'info'

@dataclass
class AuditReport:
    projects: list[Finding] = field(default_factory=list)
    environments: list[Finding] = field(default_factory=list)
    caches: list[Finding] = field(default_factory=list)
    python_executables: list[Finding] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    protected: list[Finding] = field(default_factory=list)
    possible_versions: list[Finding] = field(default_factory=list)
    access_errors: int = 0

    @property
    def findings(self) -> list[Finding]:
        return self.projects + self.environments + self.caches + self.python_executables + self.protected + self.possible_versions


def _parse_venv_cfg(path: str) -> str:
    try:
        with open(path, encoding='utf-8', errors='replace') as stream:
            for line in stream:
                if line.lower().startswith('home') and '=' in line:
                    return line.split('=', 1)[1].strip()[:250]
    except OSError:
        pass
    return 'unknown base Python'


def audit_tree(root: FileNode, cancelled: Callable[[], bool] | None = None) -> AuditReport:
    """Use the existing scanned tree, without a second filesystem crawl."""
    report = AuditReport(notes=[
        'Results cover only the selected scan root, not every drive.',
        'Virtual environments are usually intentional; do not delete them just because they repeat packages.',
        'Cache sizes are estimates from the scan. No cleanup is performed.',
        'Python executables are detected by filename, not executed or validated.',
    ])
    report.access_errors = _sum_access_errors(root)
    stack = [root]
    while stack:
        if cancelled and cancelled():
            raise RuntimeError('Audit cancelled')
        node = stack.pop()
        if not node.is_dir:
            continue
        files = {child.name.lower(): child for child in node.children if not child.is_dir}
        names = set(files)
        markers = sorted(names.intersection(PROJECT_MARKERS))
        if markers:
            classification = _classify_project(node.path, root.path)
            finding = Finding('Project' if classification.startswith('personal') else 'Bundled component',
                node.path, node.size, 'Markers: ' + ', '.join(markers) + ' | Classification: ' + classification,
                'info' if classification.startswith('personal') else 'protected')
            if classification.startswith('personal'):
                report.projects.append(finding)
            else:
                report.protected.append(finding)
        if VENV_MARKER in files:
            cfg = files[VENV_MARKER]
            report.environments.append(Finding('Virtual environment', node.path, node.size,
                'Base interpreter: ' + _parse_venv_cfg(cfg.path)))
            # Avoid counting venv packages as separate projects/caches or bundled executables.
            continue
        if node.name.lower() in CACHE_NAMES:
            report.caches.append(Finding('Cache', node.path, node.size,
                'Generated development cache; verify before removing', 'review'))
            continue
        for child in node.children:
            if child.is_dir:
                stack.append(child)
            elif child.name.lower() in {'python.exe', 'python3.exe', 'pythonw.exe'}:
                report.python_executables.append(Finding('Python executable', child.path, child.size,
                    'Executable found; may be part of an installation or an embedded runtime'))
    report.possible_versions = _version_candidates(report.projects)
    for key in ('projects', 'environments', 'caches', 'python_executables', 'protected', 'possible_versions'):
        getattr(report, key).sort(key=lambda f: (-f.size, f.path.casefold()))
    return report


def _segments(path: str) -> list[str]:
    return [part.casefold() for part in path.replace('\\', '/').split('/') if part]


def _is_temporary(path: str) -> bool:
    parts = _segments(path)
    # Windows test-run artifacts, not generic Linux pytest fixtures used in tests.
    return ('appdata' in parts and 'temp' in parts and
            any(part.startswith('pytest-') for part in parts))


def _classify_project(path: str, root: str) -> str:
    """Classify using both the absolute location and the scan boundary.

    Temporary pytest fixture roots are allowed to contain synthetic projects;
    this preserves unit tests without treating real AppData installs as personal.
    """
    if _norm_path(path) == _norm_path(root):
        return 'scan root (unverified)'
    absolute = _segments(path)
    relative = absolute[len(_segments(root)):] if absolute[:len(_segments(root))] == _segments(root) else absolute
    if _is_temporary(path) and _is_temporary(root):
        return 'personal candidate (unverified)'
    if _is_temporary(path):
        return 'temporary test artifact'
    protected = {'program files', 'program files (x86)', 'windows', 'site-packages',
                 'node_modules', 'unityhub', 'mamp'}
    if any(segment in protected for segment in absolute):
        return 'bundled/software (heuristic)'
    if 'appdata' in absolute and any(x in absolute for x in ('programs', 'ankiprogramfiles', 'uv', 'cache')):
        return 'bundled/software (heuristic)'
    if relative in (['downloads'], ['desktop'], ['bureau']):
        return 'general-purpose folder (unverified)'
    return 'personal candidate (unverified)'


def _norm_path(path: str) -> str:
    return path.replace('\\', '/').casefold().rstrip('/')

def _sum_access_errors(root: FileNode) -> int:
    # Scanner records aggregate errors on directories; don't sum nested totals.
    return root.errors


def _version_candidates(projects: list[Finding]) -> list[Finding]:
    """Group explicit vN versions across directories; no equivalence claim."""
    groups: dict[str, list[Finding]] = {}
    for item in projects:
        name = item.path.replace('\\', '/').rstrip('/').split('/')[-1]
        match = re.match(r'^(.*?)[-_. ]v(\d+(?:[._]\d+)*)$', name, re.I)
        if not match or not match.group(1):
            continue
        family = re.sub(r'[^a-z0-9]', '', match.group(1).casefold())
        groups.setdefault(family, []).append(item)
    result = []
    for family, items in groups.items():
        if len(items) < 2:
            continue
        names = ', '.join(i.path.replace('\\', '/').split('/')[-1] for i in items)
        for item in items:
            result.append(Finding('Version candidate', item.path, item.size,
                f'Family: {family} | Versions: {names} | Contents NOT compared; do not delete.', 'review'))
    return result
