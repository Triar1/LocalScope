"""Pure, offline, read-only storage statistics from an existing FileNode scan."""
from __future__ import annotations
from collections import defaultdict
from dataclasses import dataclass
from pathlib import PurePath
from .models import FileNode

CATEGORIES = ('Videos', 'Photos', 'Audio', 'Documents', 'Archives', 'Code', 'Installers', 'Other')
EXTENSIONS = {
    'Videos': {'.mp4', '.mkv', '.mov', '.avi', '.webm', '.wmv', '.m4v'},
    'Photos': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.heic', '.tif', '.tiff', '.bmp', '.raw', '.cr2'},
    'Audio': {'.mp3', '.wav', '.flac', '.ogg', '.aac', '.m4a', '.wma'},
    'Documents': {'.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt', '.rtf', '.odt', '.csv'},
    'Archives': {'.zip', '.7z', '.rar', '.tar', '.gz', '.bz2', '.xz'},
    'Code': {'.py', '.ipynb', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.toml', '.yaml', '.yml', '.rs', '.go', '.java', '.cpp', '.c', '.h', '.sql', '.sh', '.ps1'},
    'Installers': {'.exe', '.msi', '.msix', '.appx', '.deb', '.rpm', '.dmg', '.iso'},
}
_EXTENSION_CATEGORY = {ext: category for category, extensions in EXTENSIONS.items() for ext in extensions}


def category_for(name: str) -> str:
    return _EXTENSION_CATEGORY.get(PurePath(name).suffix.lower(), 'Other')


@dataclass(frozen=True)
class CategoryStats:
    category: str
    bytes: int
    files: int


@dataclass(frozen=True)
class FolderStats:
    path: str
    name: str
    bytes: int
    files: int
    node: FileNode


@dataclass(frozen=True)
class InsightsReport:
    categories: tuple[CategoryStats, ...]
    folders: tuple[FolderStats, ...]
    total_bytes: int
    total_files: int
    access_errors: int


def build_insights(root: FileNode, *, max_folders: int = 100) -> InsightsReport:
    """Single iterative traversal; never touches disk or follows links."""
    totals = defaultdict(int)
    counts = defaultdict(int)
    folder_rows = []
    stack = [(root, False)]
    aggregate = {}
    while stack:
        node, visited = stack.pop()
        if node.is_dir and not visited:
            stack.append((node, True))
            stack.extend((child, False) for child in node.children)
        elif not node.is_dir:
            category = category_for(node.name)
            totals[category] += max(0, node.size)
            counts[category] += 1
            aggregate[id(node)] = (max(0, node.size), 1)
        else:
            file_count = sum(aggregate[id(child)][1] for child in node.children)
            aggregate[id(node)] = (node.size, file_count)
            if node is not root:
                folder_rows.append(FolderStats(node.path, node.name, node.size, file_count, node))
    folder_rows.sort(key=lambda row: (-row.bytes, row.path.lower()))
    categories = tuple(CategoryStats(category, totals[category], counts[category]) for category in CATEGORIES)
    return InsightsReport(categories, tuple(folder_rows[:max_folders]), root.size,
                          aggregate[id(root)][1], root.errors)
