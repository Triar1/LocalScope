"""Offline, explainable folder-purpose classification over an existing scan tree.

No filesystem reads, process inspection, cloud access, or mutations.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import PureWindowsPath

from .models import FileNode
from .storage_insights import category_for

PURPOSES = ('Games', 'Development', 'Media', 'Applications', 'System', 'Documents', 'Archives', 'Installers', 'Other')

@dataclass(frozen=True)
class PurposeFolder:
    node: FileNode
    purpose: str
    confidence: str
    explanation: str
    bytes: int
    files: int
    display_path: str = ""

@dataclass(frozen=True)
class PurposeTotal:
    purpose: str
    bytes: int
    files: int
    folders: int

@dataclass(frozen=True)
class PurposeReport:
    totals: tuple[PurposeTotal, ...]
    entries: tuple[PurposeFolder, ...]
    total_bytes: int
    classified_bytes: int

_GAME_MARKERS = {'steam_api.dll', 'steam_api64.dll', 'unityplayer.dll', 'gameassembly.dll', 'factorio.exe', 'godot.windows.opt.tools.64.exe'}
_DEV_MARKERS = {'pyproject.toml', 'requirements.txt', 'package.json', 'cargo.toml', 'go.mod', '.git', 'manage.py'}
_GAME_DIRS = {'steamapps', 'common', 'factorio', 'bepinex', 'mods'}
_DEV_DIRS = {'.venv', 'venv', 'node_modules', '__pycache__', '.git'}
_APP_DIRS = {'program files', 'program files (x86)', 'windowsapps'}
_GAME_LIBRARY_PARTS = {'common', 'steamapps', 'gog games', 'epic games', 'xboxgames', 'games'}
_GAME_EXECUTABLES = {'cyberpunk2077.exe', 'warhammer3.exe', 'factorio.exe', 'witcher3.exe', 'eldenring.exe'}
_GAME_SIGNATURES = {'steam_api.dll', 'steam_api64.dll', 'goggame.info', 'goggame.dll',
                    'unityplayer.dll', 'gameassembly.dll', 'galaxy64.dll'}
_LAUNCHER_HINTS = {'steam', 'epic games', 'gog galaxy', 'xbox', 'ea games'}

def _game_evidence(node: FileNode) -> tuple[str, str, str] | None:
    """Conservative detection; never classify the entire Program Files tree as Games."""
    name = node.name.casefold()
    parts = [p.casefold() for p in PureWindowsPath(node.path).parts]
    direct = {c.name.casefold() for c in node.children}
    # Library roots are containers, not individual games. Descend into them.
    if name in {'steamapps', 'common', 'epic games', 'gog games', 'xboxgames', 'games'}:
        return None
    if 'steamapps' in parts and 'common' in parts and parts.index('common') < len(parts) - 1:
        return 'Games', 'High', 'Inside Steam steamapps/common game directory'
    if (any(part in {'gog games', 'epic games', 'xboxgames'} for part in parts[:-1])
        or any(parts[i] == 'gog galaxy' and parts[i+1] == 'games'
               for i in range(len(parts)-2))):
        return 'Games', 'Medium', 'Inside a known local game library (path heuristic)'
    if direct & _GAME_EXECUTABLES:
        return 'Games', 'High', 'Recognized game executable in folder'
    if direct & _GAME_SIGNATURES and name not in _LAUNCHER_HINTS:
        return 'Games', 'Medium', 'Game runtime or store signature in folder'
    if name == 'factorio' or name.startswith(('factorio.', 'factorio_')):
        return 'Games', 'Medium', 'Factorio directory name heuristic'
    return None



def _context_for_path(path: str, is_dir: bool = False) -> tuple[str, str, str] | None:
    """Recognize ownership before extensions, without reading or changing the disk.

    Only known paths are attributed; an unknown file is not assumed disposable.
    """
    p = PureWindowsPath(path)
    parts = tuple(part.casefold() for part in p.parts)
    name = p.name.casefold()
    if not parts:
        return None
    # Root-level Windows-managed files and the Windows tree.
    if not is_dir and len(parts) == 2 and name in {'pagefile.sys', 'hiberfil.sys', 'swapfile.sys', 'dumpstack.log.tmp', 'memory.dmp'}:
        return 'System', 'High', 'Windows-managed system file; do not delete manually'
    if len(parts) > 1 and parts[1] == 'windows':
        return 'System', 'High', 'Inside Windows operating-system directory'
    # A game directory owns all its data regardless of extension.
    if ('steamapps' in parts and 'common' in parts and parts.index('common') < len(parts) - 1
        or any(parts[i:i+2] == ('gog galaxy', 'games') and i+2 < len(parts) for i in range(len(parts)-2))
        or any(part in {'gog games', 'xboxgames'} for part in parts[:-1])
        or 'epic games' in parts[:-1] and 'program files' not in parts[:-1]):
        return 'Games', 'High', 'Inside recognized installed-game directory'
    if '.minecraft' in parts or ('minecraft' in parts and any(x in parts for x in ('saves', 'resourcepacks', 'mods', 'versions'))):
        return 'Games', 'High', 'Minecraft game data or installation'
    if 'nvidia' in parts and 'dxcache' in parts:
        return 'Applications', 'High', 'NVIDIA graphics shader cache'
    if ('ollama' in parts or '.ollama' in parts) and ('models' in parts or 'lib' in parts):
        return 'Development', 'High', 'Local Ollama model or runtime data'
    if 'microsoft' in parts and 'outlook' in parts:
        return 'Applications', 'High', 'Outlook application data'
    if 'google' in parts and 'chrome' in parts:
        return 'Applications', 'High', 'Chrome application data'
    if 'dassaultsystemes' in parts or '3dexperiencelauncher' in parts:
        return 'Applications', 'High', 'Dassault Systèmes application data'
    if 'programdata' in parts and 'hogwarts legacy' in parts:
        return 'Games', 'Medium', 'Hogwarts Legacy game data'
    if 'appdata' in parts and any(x in parts for x in ('local', 'roaming', 'locallow')):
        # Broad AppData attribution is intentionally medium confidence.
        return 'Applications', 'Medium', 'Inside Windows user application-data directory'
    if any(x in parts for x in ('program files', 'program files (x86)', 'windowsapps')):
        return 'Applications', 'Medium', 'Inside Windows application installation directory'
    return None


def _classify(node: FileNode) -> tuple[str, str, str] | None:
    """Only strong contextual evidence overrides file-extension fallback."""
    name = node.name.casefold()
    path_parts = [p.casefold() for p in PureWindowsPath(node.path).parts]
    child_names = {c.name.casefold() for c in node.children}
    game = _game_evidence(node)
    if game:
        return game
    # Library and installation containers must remain traversable so their
    # children can be classified as Games instead of swallowed by Applications.
    if (name in _APP_DIRS or name in _GAME_LIBRARY_PARTS or name in _LAUNCHER_HINTS
        or child_names & {'steamapps', 'common', 'gog games', 'epic games', 'xboxgames', 'games'}
        or name in {'steam', 'gog galaxy'}):
        return None
    context = _context_for_path(node.path, True)
    if context:
        return context
    if game:
        return game
    # Application and game library containers must be traversed to find games.
    if name in _APP_DIRS or name in _GAME_LIBRARY_PARTS or name in _LAUNCHER_HINTS or child_names & {'steamapps', 'common', 'gog games', 'epic games', 'xboxgames', 'games'}:
        return None
    # A stray requirements.txt in Downloads must not classify all Downloads as a project.
    generic_containers = {'downloads', 'desktop', 'documents', 'bureau', 'users', 'home'}
    if (child_names & _DEV_MARKERS and name not in generic_containers and name not in _APP_DIRS) or name in _DEV_DIRS:
        return 'Development', 'High', 'Project or dependency directory markers'
    if any(part in _DEV_DIRS for part in path_parts):
        return 'Development', 'Medium', 'Inside development environment'
    if any(part in _APP_DIRS for part in path_parts):
        return 'Applications', 'Medium', 'Inside Windows application installation directory'
    return None


def _fallback(node: FileNode) -> tuple[str, str, str]:
    """Use the predominant file type only when it is strongly dominant."""
    counts: dict[str, int] = {}
    sizes: dict[str, int] = {}
    stack = [node]
    while stack:
        current = stack.pop()
        if current.is_dir:
            stack.extend(current.children)
        else:
            category = category_for(current.name)
            sizes[category] = sizes.get(category, 0) + max(0, current.size)
            counts[category] = counts.get(category, 0) + 1
    total = sum(sizes.values())
    if total <= 0:
        return 'Other', 'Low', 'Insufficient evidence'
    top = max(sizes, key=sizes.get)
    mapping = {'Videos': 'Media', 'Photos': 'Media', 'Audio': 'Media', 'Documents': 'Documents', 'Archives': 'Archives', 'Code': 'Development'}
    purpose = mapping.get(top)
    if purpose and sizes[top] / total >= 0.80:
        return purpose, 'Low', f'{top} account for at least 80% of file bytes (extension heuristic)'
    return 'Other', 'Low', 'Mixed or unidentified content'


def build_purpose_report(root: FileNode) -> PurposeReport:
    """Partition files exactly once into attributed folders; no overlapping parent sizes."""
    # A recognized parent owns its entire subtree. Otherwise descend to child folders.
    # Direct files at an unclassified level become one fallback bucket for that directory.
    entries: list[PurposeFolder] = []
    stack = [root]
    while stack:
        node = stack.pop()
        if not node.is_dir:
            continue
        found = _classify(node)
        if found:
            purpose, confidence, explanation = found
            files = 0
            pending = [node]
            while pending:
                item = pending.pop()
                if item.is_dir:
                    pending.extend(item.children)
                else:
                    files += 1
            entries.append(PurposeFolder(node, purpose, confidence, explanation, max(0, node.size), files))
            continue
        folders = [c for c in node.children if c.is_dir]
        direct = [c for c in node.children if not c.is_dir]
        if direct:
            # Attribute loose files individually by extension instead of treating
            # all of Downloads as one giant, unidentified bucket.
            buckets: dict[str, list[FileNode]] = {}
            for child in direct:
                context = _context_for_path(child.path or str(PureWindowsPath(node.path) / child.name))
                kind = category_for(child.name)
                purpose = context[0] if context else {
                    'Videos': 'Media', 'Photos': 'Media', 'Audio': 'Media',
                    'Documents': 'Documents', 'Archives': 'Archives',
                    'Code': 'Development', 'Installers': 'Installers',
                }.get(kind, 'Other')
                buckets.setdefault(purpose, []).append(child)
            for purpose, members in buckets.items():
                amount = sum(max(0, c.size) for c in members)
                sample = max(members, key=lambda c: max(0, c.size))
                context = _context_for_path(sample.path or str(PureWindowsPath(node.path) / sample.name))
                reason = (context[2] if context else f'{len(members)} direct file(s), grouped by extension; largest: {sample.name}')
                entries.append(PurposeFolder(node, purpose, 'High' if context else 'Low', reason,
                                             amount, len(members),
                                             f'{node.path}  [Direct: {purpose}]'))
        stack.extend(reversed(folders))
    sums = {p: [0, 0, 0] for p in PURPOSES}
    for entry in entries:
        stats = sums[entry.purpose]
        stats[0] += entry.bytes
        stats[1] += entry.files
        stats[2] += 1
    totals = tuple(PurposeTotal(p, *sums[p]) for p in PURPOSES)
    entries.sort(key=lambda e: (-e.bytes, e.node.path.casefold()))
    return PurposeReport(totals, tuple(entries), root.size, sum(t.bytes for t in totals))
