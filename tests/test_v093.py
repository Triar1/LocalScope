from localscope.models import FileNode
from localscope.smart_categories import build_purpose_report
from localscope.other_inspector import inspect_other, AnalysisCancelled
import pytest

def test_gog_galaxy_games_is_classified_as_games():
    game = FileNode('Cyberpunk 2077', r'C:\Program Files (x86)\GOG Galaxy\Games\Cyberpunk 2077', 100, True, [
        FileNode('content.bin', r'C:\Program Files (x86)\GOG Galaxy\Games\Cyberpunk 2077\content.bin', 100)])
    games = FileNode('Games', r'C:\Program Files (x86)\GOG Galaxy\Games', 100, True, [game])
    galaxy = FileNode('GOG Galaxy', r'C:\Program Files (x86)\GOG Galaxy', 100, True, [games])
    root = FileNode('Program Files (x86)', r'C:\Program Files (x86)', 100, True, [galaxy])
    report = build_purpose_report(root)
    assert next(t.bytes for t in report.totals if t.purpose == 'Games') == 100
    assert report.classified_bytes == 100

def test_top50_keeps_totals_and_all_extensions():
    children = [FileNode(f'item{i}.bin', rf'C:\Downloads\item{i}.bin', i+1) for i in range(100)]
    root = FileNode('Downloads', r'C:\Downloads', sum(x.size for x in children), True, children)
    result = inspect_other(root, limit=50)
    assert len(result.items) == 50
    assert result.file_count == 100
    assert result.total == 5050
    assert result.items[0].size == 100

def test_cancel_analysis():
    root = FileNode('Downloads', r'C:\Downloads', 10, True, [FileNode('a.bin', r'C:\Downloads\a.bin', 10)])
    with pytest.raises(AnalysisCancelled):
        inspect_other(root, cancelled=lambda: True)
