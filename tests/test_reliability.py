from localscope.auditor import _classify_project, _version_candidates, Finding
from localscope.python_intelligence import inspect_python
from localscope.models import FileNode

def test_windows_app_is_bundled():
    assert _classify_project(r'C:\Users\grego\AppData\Local\AnkiProgramFiles', r'C:\Users\grego').startswith('bundled')
    assert _classify_project(r'C:\MAMP\bin\python\Tools', 'C:\\').startswith('bundled')

def test_real_personal_project():
    assert _classify_project(r'C:\Users\grego\OneDrive\Bureau\localscope_v0.1', r'C:\Users\grego').startswith('personal')

def test_version_groups_across_folders():
    projects = [Finding('Project', r'C:\Users\grego\Downloads\LocalScope_v0.3', 10, ''),
                Finding('Project', r'C:\Users\grego\Bureau\localscope_v0.5', 20, '')]
    assert len(_version_candidates(projects)) == 2

def test_temp_fixture_detection(tmp_path):
    from localscope.auditor import _is_temporary
    assert _is_temporary(r'C:\Users\grego\AppData\Local\Temp\pytest-of-grego\pytest-10\x')
    assert not _is_temporary(r'C:\Users\grego\OneDrive\Bureau\localscope_v0.1')
