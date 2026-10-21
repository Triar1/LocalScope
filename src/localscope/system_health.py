"""Read-only Windows system storage explanations from the scanned tree."""
from __future__ import annotations
from dataclasses import dataclass
import os

@dataclass(frozen=True)
class Finding:
    name: str
    size: int
    explanation: str
    guidance: str
    path: str

RULES = {
    'pagefile.sys': ('Windows virtual memory', 'Managed by Windows; do not manually delete or resize without understanding memory needs.'),
    'hiberfil.sys': ('Hibernation and Fast Startup data', 'Windows power settings control this file. Disabling hibernation may also disable Fast Startup; use Windows settings or official guidance.'),
    'swapfile.sys': ('Windows swap data', 'Windows-managed file; do not manually delete.'),
    'memory.dmp': ('System crash dump', 'Review Windows Storage > Temporary files or Disk Cleanup; retain if investigating crashes.'),
}


def system_findings(root) -> list[Finding]:
    """Inspect existing scan metadata only: no disk access and no mutations."""
    found = []
    stack = [root]
    while stack:
        node = stack.pop()
        if node.is_dir:
            stack.extend(node.children)
            continue
        key = node.name.casefold()
        if key in RULES:
            explanation, guidance = RULES[key]
            found.append(Finding(node.name, node.size, explanation, guidance, node.path))
    return sorted(found, key=lambda f: f.size, reverse=True)

@dataclass(frozen=True)
class StorageArea:
    name: str
    size: int
    path: str
    explanation: str
    advice: str

AREA_RULES = {
    'windows': ('Windows installation and component store', 'Inspect Windows Storage recommendations; never manually delete Windows or WinSxS files.'),
    'programdata': ('Shared application data and caches', 'Review the owning application before changing its data; caches may be regenerated.'),
    '$recycle.bin': ('Windows Recycle Bin', 'Review the Recycle Bin in Windows before choosing to empty it; deleted items may be needed.'),
    'system volume information': ('Restore points and system metadata', 'Review System Protection settings; do not modify this protected folder directly.'),
}


def windows_storage_areas(root) -> list[StorageArea]:
    """Summarize relevant Windows storage areas from the scanned tree, without I/O.

    Only report directly observed folders and files; never infer missing sizes.
    A scan rooted inside an area cannot reliably identify the entire area.
    """
    result: list[StorageArea] = []
    # A drive-root scan has children such as C:/Windows and C:/ProgramData.
    if root.path.replace('\\', '/').rstrip('/').endswith(':'):
        for node in root.children:
            key = node.name.casefold()
            if node.is_dir and key in AREA_RULES:
                explanation, advice = AREA_RULES[key]
                result.append(StorageArea(node.name, node.size, node.path, explanation, advice))
            elif not node.is_dir and key in RULES:
                explanation, advice = RULES[key]
                result.append(StorageArea(node.name, node.size, node.path, explanation, advice))
    return sorted(result, key=lambda x: x.size, reverse=True)
