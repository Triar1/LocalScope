"""Read-only filesystem scanner. Directory links and Windows junctions are skipped."""
from __future__ import annotations
import os
from collections.abc import Callable
from .models import FileNode


class ScanCancelled(Exception):
    """Raised when a user requests cancellation."""


def scan(path: str, progress: Callable[[str], None] | None = None,
         cancelled: Callable[[], bool] | None = None) -> FileNode:
    path = os.path.abspath(path)
    if not os.path.isdir(path):
        raise ValueError(f"Not a directory: {path}")
    root = FileNode(os.path.basename(os.path.normpath(path)) or path, path, is_dir=True)
    stack: list[tuple[FileNode, bool]] = [(root, False)]
    visited = 0
    while stack:
        if cancelled and cancelled():
            raise ScanCancelled()
        node, done = stack.pop()
        if done:
            node.size = sum(c.size for c in node.children)
            node.errors += sum(c.errors for c in node.children)
            continue
        stack.append((node, True))
        try:
            with os.scandir(node.path) as entries:
                for entry in entries:
                    if cancelled and cancelled():
                        raise ScanCancelled()
                    try:
                        if entry.is_symlink() or (hasattr(entry, "is_junction") and entry.is_junction()):
                            continue
                        if entry.is_dir(follow_symlinks=False):
                            child = FileNode(entry.name, entry.path, is_dir=True)
                            node.children.append(child)
                            stack.append((child, False))
                        elif entry.is_file(follow_symlinks=False):
                            node.children.append(FileNode(entry.name, entry.path, size=entry.stat(follow_symlinks=False).st_size))
                        visited += 1
                        if progress and visited % 300 == 0:
                            progress(f"Scanned {visited:,} entries — {node.path}")
                    except (OSError, PermissionError):
                        node.errors += 1
        except (OSError, PermissionError):
            node.errors += 1
    if progress:
        progress(f"Completed: {visited:,} entries")
    return root
