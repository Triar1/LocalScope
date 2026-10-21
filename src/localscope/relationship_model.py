from pathlib import PureWindowsPath
from .models import format_size

def relationship_data(report):
    """Pure graph model: never infer that two environments are interchangeable."""
    nodes, edges = {}, set()
    def add(key, label, kind, path, detail):
        nodes[key] = (label, kind, path, detail)
    for env in report.links:
        eid = 'env:' + env.path.casefold()
        add(eid, PureWindowsPath(env.path).name or env.path, 'Environment', env.path,
            f'{format_size(env.size)} | {env.state} | {env.confidence} confidence | Python {env.version or "unknown"} | {env.installed_packages} package metadata entries')
        if env.project:
            pid = 'project:' + env.project.casefold()
            add(pid, PureWindowsPath(env.project).name or env.project, 'Project', env.project, 'Detected project marker')
            edges.add((pid, eid))
        if env.base_executable:
            bid = 'base:' + env.base_executable.casefold()
            add(bid, PureWindowsPath(env.base_executable).name or env.base_executable, 'Base reference', env.base_executable,
                'Path from pyvenv.cfg; installation not independently verified')
            edges.add((eid, bid))
    for finding in report.audit.projects:
        pid = 'project:' + finding.path.casefold()
        if pid not in nodes:
            add(pid, PureWindowsPath(finding.path).name or finding.path, 'Project', finding.path, 'No detected environment link')
    return nodes, sorted(edges)


import re
from dataclasses import dataclass

@dataclass(frozen=True)
class ProjectFamily:
    label: str
    paths: tuple[str, ...]
    total_size: int


def family_name(name: str) -> str:
    """Group only explicit trailing version tokens; avoid merging unrelated projects."""
    base = re.sub(r'(?i)(?:[-_. ]+v?\d+(?:[._-]\d+){0,3})$', '', name).strip(' ._-')
    return base.casefold() or name.casefold()


def group_project_families(nodes, project_sizes=None):
    """Return families of 2+ versions; preserve singleton projects separately."""
    project_sizes = project_sizes or {}
    buckets = {}
    for key, (label, kind, path, detail) in nodes.items():
        if kind != 'Project':
            continue
        buckets.setdefault(family_name(label), []).append(path)
    return tuple(ProjectFamily(label, tuple(sorted(paths, key=str.casefold)),
                               sum(project_sizes.get(path.casefold(), 0) for path in paths))
                 for label, paths in sorted(buckets.items()) if len(paths) > 1)
