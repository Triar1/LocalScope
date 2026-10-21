from localscope.auditor import audit_tree
from localscope.models import FileNode


def test_bundled_component_not_personal(tmp_path):
    root = FileNode('C:', 'C:\\', is_dir=True, children=[
        FileNode('module', 'C:\\Program Files\\Example\\module', is_dir=True, size=100,
                 children=[FileNode('pyproject.toml', 'C:\\Program Files\\Example\\module\\pyproject.toml')])])
    report = audit_tree(root)
    assert len(report.protected) == 1
    assert not report.projects


def test_version_candidates(tmp_path):
    def project(name):
        return FileNode(name, str(tmp_path / name), is_dir=True, size=100,
                        children=[FileNode('pyproject.toml', str(tmp_path / name / 'pyproject.toml'))])
    root = FileNode('root', str(tmp_path), is_dir=True,
                    children=[project('mailpilot-v0.1'), project('mailpilot-v0.3')])
    report = audit_tree(root)
    assert len(report.possible_versions) == 2
    assert all('NOT compared' in x.detail for x in report.possible_versions)


def test_root_marker_not_personal(tmp_path):
    root = FileNode('Downloads', str(tmp_path), is_dir=True,
                    children=[FileNode('requirements.txt', str(tmp_path / 'requirements.txt'))])
    report = audit_tree(root)
    assert not report.projects
    assert len(report.protected) == 1


def test_windows_temp_path_does_not_hide_personal_projects():
    from localscope.auditor import _classify_project
    root = r'C:\Users\grego\AppData\Local\Temp\pytest-fixture'
    assert _classify_project(root + r'\mailpilot-v0.1', root).startswith('personal')
    assert _classify_project(root + r'\mailpilot-v0.3', root).startswith('personal')
    assert _classify_project(r'C:\Users\grego\AppData\Local\Programs\Anki', r'C:\Users\grego').startswith('bundled')
