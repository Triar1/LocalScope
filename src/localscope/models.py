from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class FileNode:
    name: str
    path: str
    size: int = 0
    is_dir: bool = False
    children: list[FileNode] = field(default_factory=list)
    errors: int = 0

    @property
    def total_files(self) -> int:
        return sum(child.total_files for child in self.children) if self.is_dir else 1


def format_size(value: int) -> str:
    size = float(value)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB", "PiB"):
        if size < 1024 or unit == "PiB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return "0 B"
