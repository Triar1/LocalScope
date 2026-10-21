"""Read-only, bounded top-N inspection of an existing FileNode index."""
from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict
from pathlib import PureWindowsPath
import heapq
from .models import FileNode
from .smart_categories import PurposeReport, build_purpose_report

@dataclass(frozen=True)
class UnknownItem:
    path: str
    size: int
    reason: str
    node: FileNode
    parent: FileNode | None = None

@dataclass(frozen=True)
class UnknownReport:
    total: int
    items: tuple[UnknownItem, ...]
    extensions: tuple[tuple[str, int, int], ...]
    file_count: int

class AnalysisCancelled(Exception):
    pass

def inspect_other(root: FileNode, purpose_report: PurposeReport | None = None,
                  limit: int = 50, cancelled=None) -> UnknownReport:
    """All unknown bytes are counted; at most `limit` locations are retained.

    No disk access. `cancelled` is a callable polled while traversing nodes.
    """
    from .storage_insights import category_for
    if limit < 1:
        raise ValueError('limit must be positive')
    report = purpose_report if purpose_report is not None else build_purpose_report(root)
    heap = []
    extensions = defaultdict(lambda: [0, 0])
    file_count = 0
    sequence = 0
    def check():
        if cancelled is not None and cancelled():
            raise AnalysisCancelled()
    def keep(item):
        nonlocal sequence
        sequence += 1
        record = (item.size, sequence, item)
        if len(heap) < limit:
            heapq.heappush(heap, record)
        elif record[0] > heap[0][0]:
            heapq.heapreplace(heap, record)
    for entry in report.entries:
        check()
        if entry.purpose != 'Other':
            continue
        node = entry.node
        if not entry.display_path:
            keep(UnknownItem(node.path, entry.bytes, entry.explanation, node))
        pending = [node]
        processed = 0
        while pending:
            current = pending.pop()
            processed += 1
            if processed % 512 == 0:
                check()
            if current.is_dir:
                # Direct bucket: only direct files, not children of nested folders.
                if entry.display_path:
                    pending.extend(c for c in current.children if not c.is_dir)
                else:
                    pending.extend(current.children)
                continue
            if entry.display_path:
                kind = category_for(current.name)
                if kind in {'Videos', 'Photos', 'Audio', 'Documents', 'Archives', 'Code', 'Installers'}:
                    continue
                keep(UnknownItem(current.path, max(0, current.size),
                                 'Unrecognized or ambiguous file extension', current, node))
            file_count += 1
            ext = PureWindowsPath(current.name).suffix.casefold() or '[no extension]'
            extensions[ext][0] += max(0, current.size)
            extensions[ext][1] += 1
    check()
    rows = sorted((record[2] for record in heap), key=lambda x: (-x.size, x.path.casefold()))
    ext_rows = sorted(((k, v[0], v[1]) for k, v in extensions.items()),
                      key=lambda x: (-x[1], x[0]))[:limit]
    total = sum(t.bytes for t in report.totals if t.purpose == 'Other')
    return UnknownReport(total, tuple(rows), tuple(ext_rows), file_count)
