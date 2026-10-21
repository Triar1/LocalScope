from localscope.models import FileNode
from localscope.smart_categories import build_purpose_report
from localscope.relationship_model import family_name, group_project_families


def file(name, size, path):
    return FileNode(name, path, size)


def folder(name, path, *children):
    return FileNode(name, path, sum(c.size for c in children), True, list(children))


def test_steam_game_inside_program_files_not_swallowed():
    base = r'C:\Program Files (x86)'
    game = folder('Total War WARHAMMER III', base+r'\Steam\steamapps\common\Total War WARHAMMER III',
                  file('data.pack', 80, base+r'\Steam\steamapps\common\Total War WARHAMMER III\data.pack'))
    common = folder('common', base+r'\Steam\steamapps\common', game)
    steamapps = folder('steamapps', base+r'\Steam\steamapps', common)
    steam = folder('Steam', base+r'\Steam', steamapps)
    root = folder('Program Files (x86)', base, steam)
    result = build_purpose_report(root)
    assert {t.purpose: t.bytes for t in result.totals}['Games'] == 80


def test_epic_and_gog_and_xbox():
    games = [folder('Cyberpunk 2077', r'C:\Epic Games\Cyberpunk 2077', file('blob', 50, 'blob')),
             folder('Witcher 3', r'D:\GOG Games\Witcher 3', file('blob', 60, 'blob')),
             folder('Halo', r'E:\XboxGames\Halo', file('blob', 70, 'blob'))]
    for game in games:
        root = folder('root', r'C:\root', game)
        assert next(t.bytes for t in build_purpose_report(root).totals if t.purpose == 'Games') == game.size


def test_game_signature_overrides_program_files():
    game = folder('Unknown', r'C:\Program Files\Unknown', file('steam_api64.dll', 100, 'dll'))
    root = folder('Program Files', r'C:\Program Files', game)
    assert next(t.bytes for t in build_purpose_report(root).totals if t.purpose == 'Games') == 100


def test_family_grouping_keeps_unrelated_projects():
    nodes = {
        'a': ('LocalScope_v0.8', 'Project', 'C:/LocalScope_v0.8', ''),
        'b': ('LocalScope_v0.9', 'Project', 'C:/LocalScope_v0.9', ''),
        'c': ('MailPilot_v0.3', 'Project', 'C:/MailPilot_v0.3', ''),
    }
    groups = group_project_families(nodes, {'c:/localscope_v0.8': 100, 'c:/localscope_v0.9': 200})
    assert len(groups) == 1
    assert groups[0].label == 'localscope'
    assert groups[0].total_size == 300
    assert len(groups[0].paths) == 2
    assert family_name('project_alpha') != family_name('project_beta')
