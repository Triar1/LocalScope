from localscope.models import FileNode
from localscope.smart_categories import build_purpose_report


def f(name, size, path=''):
    return FileNode(name, path or name, size)


def d(name, children, path=''):
    return FileNode(name, path or name, sum(c.size for c in children), True, children)


def test_factorio_classified_as_game_without_double_counting():
    game = d('Factorio.v2.0.72.ALL.DLC (1)', [f('factorio.exe', 200), d('data', [f('texture.png', 300)])], r'C:\Users\x\Downloads\Factorio.v2.0.72.ALL.DLC (1)')
    root = d('Downloads', [game, f('readme.pdf', 20)], r'C:\Users\x\Downloads')
    report = build_purpose_report(root)
    totals = {t.purpose: t.bytes for t in report.totals}
    assert totals['Games'] == 500
    assert sum(t.bytes for t in report.totals) == 520
    assert sum(t.files for t in report.totals) == 3
    assert len([e for e in report.entries if e.purpose == 'Games']) == 1


def test_project_and_unknown_and_empty():
    project = d('work', [f('pyproject.toml', 10), f('main.py', 20)])
    root = d('root', [project, f('blob.xyz', 3)])
    result = build_purpose_report(root)
    assert {t.purpose: t.bytes for t in result.totals}['Development'] == 30
    assert {t.purpose: t.bytes for t in result.totals}['Other'] == 3
    assert sum(t.bytes for t in build_purpose_report(d('empty', [])).totals) == 0


def test_steam_path_and_file_type_fallback():
    steam = d('game', [f('asset.bin', 80)], r'C:\Steam\steamapps\common\game')
    media = d('pictures', [f('one.jpg', 20), f('two.jpg', 30)])
    root = d('root', [steam, media])
    report = build_purpose_report(root)
    assert {t.purpose: t.bytes for t in report.totals}['Games'] == 80
    assert {t.purpose: t.bytes for t in report.totals}['Media'] == 50


def test_downloads_with_requirements_is_not_whole_development_project():
    root = d('Downloads', [f('requirements.txt', 4), d('Factorio.v2', [f('factorio.exe', 50)])], r'C:\Users\x\Downloads')
    result = build_purpose_report(root)
    assert {t.purpose: t.bytes for t in result.totals}['Games'] == 50
