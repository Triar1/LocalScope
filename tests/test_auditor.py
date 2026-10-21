from localscope.auditor import audit_tree
from localscope.models import FileNode


def test_audit_projects_env_and_cache(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    (project / 'pyproject.toml').write_text('[project]\nname="demo"')
    env = project / '.venv'
    env.mkdir()
    (env / 'pyvenv.cfg').write_text('home = C:\\Python312\n')
    cache = project / '__pycache__'
    cache.mkdir()
    root = FileNode('root', str(tmp_path), is_dir=True, children=[
        FileNode('project', str(project), is_dir=True, size=300, children=[
            FileNode('pyproject.toml', str(project / 'pyproject.toml'), size=20),
            FileNode('.venv', str(env), size=200, is_dir=True, children=[FileNode('pyvenv.cfg', str(env / 'pyvenv.cfg'), size=30)]),
            FileNode('__pycache__', str(cache), size=80, is_dir=True),
        ])])
    report = audit_tree(root)
    assert len(report.projects) == 1
    assert len(report.environments) == 1
    assert len(report.caches) == 1
    assert 'Python312' in report.environments[0].detail


def test_no_false_venv_from_folder_name(tmp_path):
    root = FileNode('.venv', str(tmp_path / '.venv'), is_dir=True)
    assert audit_tree(root).environments == []


def test_python_executable_outside_venv(tmp_path):
    root = FileNode('root', str(tmp_path), is_dir=True, children=[FileNode('python.exe', str(tmp_path / 'python.exe'), size=42)])
    assert len(audit_tree(root).python_executables) == 1
