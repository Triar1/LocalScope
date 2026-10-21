from localscope.models import FileNode
from localscope.system_health import system_findings

def test_system_findings_from_metadata_only():
    root = FileNode('C:', 'C:/', is_dir=True)
    root.children = [FileNode('pagefile.sys', 'C:/pagefile.sys', size=4096), FileNode('photo.jpg', 'C:/photo.jpg', size=50), FileNode('hiberfil.sys', 'C:/hiberfil.sys', size=8192)]
    findings = system_findings(root)
    assert [x.name for x in findings] == ['hiberfil.sys', 'pagefile.sys']
    assert all(x.guidance for x in findings)

def test_no_findings_when_scope_does_not_include_system_files():
    root = FileNode('Downloads', 'C:/Downloads', is_dir=True)
    assert system_findings(root) == []

from localscope.system_health import windows_storage_areas

def test_windows_areas_only_observed_drive_root_nodes():
    root = FileNode('C:', 'C:/', is_dir=True)
    root.children = [
        FileNode('Windows', 'C:/Windows', size=100, is_dir=True),
        FileNode('ProgramData', 'C:/ProgramData', size=80, is_dir=True),
        FileNode('pagefile.sys', 'C:/pagefile.sys', size=60),
        FileNode('Users', 'C:/Users', size=200, is_dir=True),
    ]
    areas = windows_storage_areas(root)
    assert [x.name for x in areas] == ['Windows', 'ProgramData', 'pagefile.sys']
    assert all(x.advice for x in areas)
    assert windows_storage_areas(root.children[0]) == []

def test_windows_areas_accept_backslash_drive_root():
    root = FileNode('C:', 'C:\\\\', is_dir=True)
    root.children = [FileNode('hiberfil.sys', 'C:/hiberfil.sys', size=10)]
    assert len(windows_storage_areas(root)) == 1
