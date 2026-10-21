"""Read-only, cancellable exact duplicate discovery. No network or file writes."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
import hashlib
import os
import stat
import time
from .models import FileNode

class AnalysisCancelled(Exception):
    pass

@dataclass(frozen=True)
class DuplicateGroup:
    size: int
    paths: tuple[str, ...]
    digest: str

    @property
    def extra_bytes(self) -> int:
        return self.size * (len(self.paths) - 1)


def _check(cancelled):
    if cancelled and cancelled():
        raise AnalysisCancelled()


def _offline(path):
    """Skip cloud placeholders without opening/hydrating them (Windows)."""
    try:
        st = os.stat(path, follow_symlinks=False)
        attrs = getattr(st, 'st_file_attributes', 0)
        # FILE_ATTRIBUTE_OFFLINE / RECALL_ON_OPEN / RECALL_ON_DATA_ACCESS
        return bool(attrs & (0x1000 | 0x40000 | 0x400000))
    except OSError:
        return True


def _hash(path, size, cancelled, *, sample=False, bytes_read=None, reading=None):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        if sample and size > 2 * 1024 * 1024:
            positions = (0, max(0, size // 2 - 32768), max(0, size - 65536))
            for pos in positions:
                _check(cancelled)
                f.seek(pos)
                if reading: reading(path)
                data = f.read(65536)
                h.update(data)
                if bytes_read:
                    bytes_read(len(data))
        else:
            while True:
                _check(cancelled)
                if reading: reading(path)
                data = f.read(1024 * 1024)
                if not data:
                    break
                h.update(data)
                if bytes_read:
                    bytes_read(len(data))
    return h.hexdigest()


def find_duplicates(root: FileNode, *, max_file_bytes=2*1024**3, cancelled=None,
                    progress=None, status=None, group_found=None, skip_offline=True, diagnostic=None):
    """Return (groups, fully_hashed_count, skipped_count). Partial hashes never prove duplicates.

    progress(done,total) remains compatible with v0.7; status(phase,done,total,path,bytes_read)
    provides phase-aware UI updates. group_found(group) streams confirmed results.
    """
    # Indexing can visit >1 million nodes. Report progress BEFORE hashing begins.
    # A bounded cadence avoids flooding Qt's event queue.
    by_size = defaultdict(list)
    stack = [root]
    indexed = 0
    last_index_emit = 0.0
    if status:
        status('Indexing file tree', 0, 0, root.path, 0)
    while stack:
        _check(cancelled)
        node = stack.pop()
        indexed += 1
        if node.is_dir:
            stack.extend(node.children)
        elif 0 < node.size <= max_file_bytes:
            by_size[node.size].append(node.path)
        now = time.monotonic()
        if status and now - last_index_emit >= 0.25:
            status('Indexing file tree', indexed, 0, node.path, 0)
            last_index_emit = now
    if status:
        status('Indexing complete', indexed, indexed, root.path, 0)
    candidates = [(size, p) for size, paths in by_size.items() if len(paths) > 1 for p in paths]
    total = len(candidates)
    skipped = 0
    bytes_total = 0
    last_emit = 0.0

    def report(phase, done, count, path='', force=False):
        nonlocal last_emit
        now = time.monotonic()
        if status and (force or now - last_emit >= 0.12):
            status(phase, done, count, path, bytes_total)
            last_emit = now

    def reading(path):
        report(current_phase, current_done, current_total, path)

    def counted(n):
        nonlocal bytes_total
        bytes_total += n

    # Phase 1: short samples only, then phase 2: full SHA-256 for matching samples.
    # Files <=2 MiB are fully hashed in both phases for simplicity and correctness.
    samples = defaultdict(list)
    current_phase, current_done, current_total = "Sampling", 0, total
    report("Sampling", 0, total, force=True)
    for i, (size, path) in enumerate(candidates, 1):
        current_done = i
        _check(cancelled)
        try:
            if os.path.islink(path) or (skip_offline and _offline(path)) or not os.path.isfile(path) or os.path.getsize(path) != size:
                skipped += 1
                continue
            started = time.monotonic()
            digest = _hash(path, size, cancelled, sample=True, bytes_read=counted, reading=reading)
            if diagnostic and time.monotonic() - started >= 2:
                diagnostic("slow-read", path, round(time.monotonic()-started, 2))
            samples[(size, digest)].append(path)
        except OSError as exc:
            if diagnostic: diagnostic("read-error", path, str(exc))
            skipped += 1
        finally:
            report('Sampling', i, total, path)
    report('Sampling', total, total, force=True)
    full_candidates = [(size, p) for (size, _), paths in samples.items() if len(paths) > 1 for p in paths]
    full_total = len(full_candidates)
    hashes = defaultdict(list)
    hashed = 0
    report('Verifying SHA-256', 0, full_total, force=True)
    current_phase, current_done, current_total = "Verifying SHA-256", 0, full_total
    for i, (size, path) in enumerate(full_candidates, 1):
        current_done = i
        _check(cancelled)
        try:
            if os.path.islink(path) or (skip_offline and _offline(path)) or os.path.getsize(path) != size:
                skipped += 1
                continue
            started = time.monotonic()
            digest = _hash(path, size, cancelled, bytes_read=counted, reading=reading)
            if diagnostic and time.monotonic() - started >= 2:
                diagnostic("slow-read", path, round(time.monotonic()-started, 2))
            hashes[(size, digest)].append(path)
            hashed += 1
        except OSError as exc:
            if diagnostic: diagnostic("read-error", path, str(exc))
            skipped += 1
        finally:
            report('Verifying SHA-256', i, full_total, path)
            if progress and i % 20 == 0:
                progress(i, full_total)
    groups = [DuplicateGroup(size, tuple(sorted(paths)), digest)
              for (size, digest), paths in hashes.items() if len(paths) > 1]
    groups.sort(key=lambda g: (-g.extra_bytes, -len(g.paths), g.paths[0].casefold()))
    if group_found:
        for group in groups:
            group_found(group)
    report('Complete', full_total, full_total, force=True)
    if progress:
        progress(full_total, full_total)
    return groups, hashed, skipped
