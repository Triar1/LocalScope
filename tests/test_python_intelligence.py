from localscope.models import FileNode
from localscope.python_intelligence import inspect_python, parse_cfg

def test_cfg_parsing(tmp_path):
    cfg = tmp_path / 'pyvenv.cfg'
    cfg.write_text('home = C:\\Python312\nversion = 3.12.1\n')
    assert parse_cfg(str(cfg))['version'] == '3.12.1'

def test_link_project_and_env(tmp_path):
    project = tmp_path / 'project'
    env = project / '.venv'
    env.mkdir(parents=True)
    (project / 'pyproject.toml').write_text('[project]')
    (env / 'pyvenv.cfg').write_text('home = C:\\Python312\nversion = 3.12.1\n')
    node = FileNode('project', str(project), is_dir=True, children=[
        FileNode('pyproject.toml', str(project/'pyproject.toml')),
        FileNode('.venv', str(env), is_dir=True, children=[
            FileNode('pyvenv.cfg', str(env/'pyvenv.cfg'))])])
    root = FileNode('root', str(tmp_path), is_dir=True, children=[node])
    result = inspect_python(root)
    assert len(result.links) == 1
    assert result.links[0].project == str(project)
    assert result.links[0].state == 'Linked'
    assert result.links[0].version == '3.12.1'

def test_unlinked_environment(tmp_path):
    env = tmp_path / 'lonely'
    env.mkdir()
    (env/'pyvenv.cfg').write_text('home = /usr/bin\n')
    root = FileNode('root', str(tmp_path), is_dir=True, children=[
        FileNode('lonely', str(env), is_dir=True, children=[FileNode('pyvenv.cfg', str(env/'pyvenv.cfg'))])])
    assert inspect_python(root).links[0].state == 'Review'


def test_pytest_fixture_root_keeps_synthetic_environments(monkeypatch, tmp_path):
    from localscope import python_intelligence as pi
    env = tmp_path / 'project' / '.venv'
    env.mkdir(parents=True)
    (env / 'pyvenv.cfg').write_text('home = C:\\Python312\nversion = 3.12.1\n')
    root = FileNode('root', str(tmp_path), is_dir=True, children=[
        FileNode('project', str(env.parent), is_dir=True, children=[
            FileNode('.venv', str(env), is_dir=True, children=[
                FileNode('pyvenv.cfg', str(env / 'pyvenv.cfg'))])])])
    monkeypatch.setattr(pi, '_is_temporary', lambda path: True)
    report = pi.inspect_python(root)
    assert len(report.links) == 1
    assert not report.temporary_links
