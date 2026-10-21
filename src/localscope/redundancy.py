"""Offline, read-only redundancy analysis. No files are removed or modified."""
from __future__ import annotations
from dataclasses import dataclass, field
from collections import defaultdict
from pathlib import Path
import hashlib
import os
import re
from .models import FileNode
from .auditor import audit_tree, _is_temporary
from .python_intelligence import inspect_python

@dataclass
class Insight:
    kind: str
    path: str
    size: int
    status: str
    explanation: str

@dataclass
class RedundancyReport:
    insights: list[Insight] = field(default_factory=list)
    exact_duplicate_groups: int = 0
    duplicate_extra_bytes: int = 0
    hashed_files: int = 0
    skipped_files: int = 0
    notes: list[str] = field(default_factory=list)


def _walk(root):
    stack = [root]
    while stack:
        node = stack.pop()
        yield node
        if node.is_dir:
            stack.extend(node.children)


def _hash(path, chunk_size=1024 * 1024):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while data := stream.read(chunk_size):
            digest.update(data)
    return digest.hexdigest()


def _packages(env: FileNode):
    """Package names/versions from directory names, never execute Python."""
    result = set()
    for node in _walk(env):
        if not node.is_dir:
            continue
        name = node.name
        if name.lower().endswith('.dist-info'):
            result.add(name[:-10].casefold().replace('_', '-'))
        elif name.lower().endswith('.egg-info'):
            result.add(name[:-9].casefold().replace('_', '-'))
    return result


def _family(name: str):
    match = re.match(r'^(.*?)[-_. ]v(\d+(?:[._]\d+)*)$', name, re.I)
    if not match or not match.group(1):
        return None
    return re.sub('[^a-z0-9]', '', match.group(1).casefold())


def analyze_redundancy(root: FileNode, *, hash_duplicates: bool = False,
                       max_hash_bytes: int = 2 * 1024**3, cancelled=None) -> RedundancyReport:
    """Compare scanned metadata; hash exact duplicates only when explicitly requested.

    Files are hashed only if their size is shared by another regular file, and
    individual files exceed neither max_hash_bytes nor the available scan scope.
    """
    report = RedundancyReport(notes=[
        'Candidates are NOT deletion recommendations; no data is changed.',
        'File hashes establish identical bytes, not whether either copy is safe to remove.',
        'Package overlap is based on metadata directory names, not runtime dependency resolution.',
        'Results are incomplete where scanning reported access errors or files changed since scanning.',
    ])
    audit = audit_tree(root)
    python = inspect_python(root)
    nodes = {n.path.replace('\\', '/').casefold(): n for n in _walk(root)}
    families = defaultdict(list)
    for finding in audit.projects:
        name = finding.path.replace('\\', '/').rstrip('/').split('/')[-1]
        fam = _family(name)
        if fam:
            families[fam].append(finding)
    for fam, projects in sorted(families.items()):
        if len(projects) > 1:
            paths = ', '.join(p.path for p in projects)
            report.insights.append(Insight('Project versions', projects[0].path,
                sum(p.size for p in projects), 'Review',
                f'{len(projects)} versions in family {fam}: {paths}. Contents not compared.'))

    linked = [e for e in python.links if e.state == 'Linked']
    for i, a in enumerate(linked):
        anode = nodes.get(a.path.replace('\\', '/').casefold())
        if not anode:
            continue
        pa = _packages(anode)
        for b in linked[i+1:]:
            bnode = nodes.get(b.path.replace('\\', '/').casefold())
            if not bnode:
                continue
            pb = _packages(bnode)
            if not pa or not pb:
                continue
            common = pa & pb
            if not common:
                continue
            similarity = len(common) / len(pa | pb)
            if similarity >= 0.5:
                report.insights.append(Insight('Environment overlap', a.path,
                    min(a.size, b.size), 'Informational',
                    f'{len(common)} shared of {len(pa | pb)} distinct package metadata entries '
                    f'({similarity:.0%} overlap) with {b.path}. Environments may need separate versions; '
                    'size is NOT reclaimable estimate.'))

    if hash_duplicates:
        by_size = defaultdict(list)
        for node in _walk(root):
            if not node.is_dir and node.size > 0 and node.size <= max_hash_bytes:
                by_size[node.size].append(node.path)
        for size, paths in by_size.items():
            if len(paths) < 2:
                continue
            by_digest = defaultdict(list)
            for path in paths:
                if cancelled and cancelled():
                    raise RuntimeError('Duplicate analysis cancelled')
                try:
                    if os.path.islink(path) or not os.path.isfile(path) or os.path.getsize(path) != size:
                        report.skipped_files += 1
                        continue
                    by_digest[_hash(path)].append(path)
                    report.hashed_files += 1
                except (OSError, PermissionError):
                    report.skipped_files += 1
            for matching in by_digest.values():
                if len(matching) < 2:
                    continue
                report.exact_duplicate_groups += 1
                extra = size * (len(matching)-1)
                report.duplicate_extra_bytes += extra
                report.insights.append(Insight('Exact duplicates', matching[0], extra,
                    'Review', f'{len(matching)} files have identical SHA-256 bytes: ' + ' | '.join(matching) +
                    '. Potential duplicate bytes, NOT confirmed recoverable space.'))
    report.insights.sort(key=lambda x: (-x.size, x.kind, x.path.casefold()))
    return report
