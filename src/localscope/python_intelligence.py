"""Explain Python project -> environment -> interpreter relationships, offline and read-only.

The input is the scanned FileNode tree. Only pyvenv.cfg files are opened for
metadata; discovered executables are NEVER launched.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import ntpath
import os
import re
from .models import FileNode
from .auditor import AuditReport, audit_tree, _is_temporary, _classify_project

@dataclass
class EnvironmentLink:
    path: str
    size: int
    project: str | None
    base_home: str | None
    base_executable: str | None
    version: str | None
    installed_packages: int
    state: str
    explanation: str
    confidence: str = 'Low'

@dataclass
class PythonReport:
    audit: AuditReport
    links: list[EnvironmentLink] = field(default_factory=list)
    installation_candidates: list[str] = field(default_factory=list)
    embedded_executables: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    temporary_links: list[EnvironmentLink] = field(default_factory=list)

def _norm(path: str) -> str:
    return path.replace('\\', '/').rstrip('/').casefold()

def _under(path: str, parent: str) -> bool:
    p, root = _norm(path), _norm(parent)
    return p == root or p.startswith(root + '/')

def parse_cfg(path: str) -> dict[str, str]:
    result = {}
    try:
        with open(path, encoding='utf-8-sig', errors='replace') as fh:
            for line in fh:
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    result[key.strip().lower()] = value.strip()
    except (OSError, ValueError):
        pass
    return result

def _index(root: FileNode) -> dict[str, FileNode]:
    result = {}
    stack = [root]
    while stack:
        node = stack.pop()
        result[_norm(node.path)] = node
        if node.is_dir:
            stack.extend(node.children)
    return result

def _package_count(env: FileNode) -> int:
    # Count package metadata folders, not imported modules; avoid double counting.
    count = 0
    stack = [env]
    while stack:
        node = stack.pop()
        if node.is_dir:
            if node.name.lower().endswith(('.dist-info', '.egg-info')):
                count += 1
            else:
                stack.extend(node.children)
    return count

def inspect_python(root: FileNode) -> PythonReport:
    audit = audit_tree(root)
    report = PythonReport(audit=audit, notes=[
        'All relationships are inferred from scanned paths and pyvenv.cfg; no executables are run.',
        'A virtual environment is not redundant merely because it shares a base Python.',
        'Package counts are estimates based on .dist-info/.egg-info directories.',
        'Unknown base paths and access errors limit certainty. Nothing is deleted.',
    ])
    nodes = _index(root)
    projects = [f.path for f in audit.projects]
    all_execs = [f.path for f in audit.python_executables]
    for env in audit.environments:
        node = nodes.get(_norm(env.path))
        cfg = parse_cfg(os.path.join(env.path, 'pyvenv.cfg'))
        home = cfg.get('home') or None
        exe = cfg.get('executable') or None
        version = cfg.get('version') or None
        # Longest containing project wins. Do not associate unrelated siblings.
        matching = [p for p in projects if _under(env.path, p)]
        project = max(matching, key=len) if matching else None
        if exe:
            base = exe
        elif home:
            base = ntpath.join(home, 'python.exe') if '\\' in home or ':' in home else os.path.join(home, 'python.exe')
        else:
            base = None
        packages = _package_count(node) if node else 0
        if _is_temporary(env.path) and not _is_temporary(root.path):
            state = 'Temporary'
            explanation = 'Pytest temporary environment; excluded from active environment count.'
        elif _classify_project(env.path, root.path).startswith('bundled'):
            state = 'Embedded'
            explanation = 'Environment appears to belong to installed software; do not remove manually.'
        elif not project:
            state = 'Review'
            explanation = 'No detected project contains this environment; it may belong to a tool or an unmarked project.'
        elif not base:
            state = 'Unknown'
            explanation = 'Project found, but pyvenv.cfg does not identify a base interpreter.'
        else:
            state = 'Linked'
            explanation = 'Project and base interpreter path inferred; installation existence has not been verified.'
        confidence = 'High' if state == 'Linked' and version and base else ('Medium' if state in ('Linked', 'Embedded', 'Temporary') else 'Low')
        link = EnvironmentLink(env.path, env.size, project, home, base, version, packages, state, explanation, confidence)
        if state == 'Temporary':
            report.temporary_links.append(link)
        else:
            report.links.append(link)
    report.links.sort(key=lambda e: (-e.size, e.path.casefold()))
    # A binary inside Program Files/AppData/site-packages is not automatically a separate installation.
    for exe in all_execs:
        lower = _norm(exe)
        if any(token in lower for token in ('/site-packages/', '/program files/', '/program files (x86)/', '/unityhub/', '/pycharm/')):
            report.embedded_executables.append(exe)
        else:
            report.installation_candidates.append(exe)
    # A base interpreter outside the scanned tree is a reference, not a confirmed installation.
    return report
