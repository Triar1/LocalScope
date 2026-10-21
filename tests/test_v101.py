from localscope.models import FileNode
from pathlib import Path
import ast

def _guides():
    path = Path(__file__).parents[1] / "src/localscope/system_ui.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    assignments = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name) and node.targets[0].id in {"GUIDES", "GENERAL"}:
            assignments[node.targets[0].id] = ast.literal_eval(node.value)
    return assignments["GUIDES"], assignments["GENERAL"]
from localscope.storage_insights import build_insights
from localscope.smart_categories import build_purpose_report

def test_health_guides_explain_tradeoffs():
    GUIDES, GENERAL = _guides()
    assert 'powercfg /a' in GUIDES['hiberfil.sys']
    assert 'Fast Startup' in GUIDES['hiberfil.sys']
    assert 'System managed' in GUIDES['pagefile.sys']
    assert 'WinSxS' in GENERAL and 'DISM' in GENERAL

def test_views_use_existing_scan_without_mutation():
    file = FileNode('report.pdf', 'C:/data/report.pdf', 123, False)
    root = FileNode('data', 'C:/data', 123, True, [file])
    before = (root.size, file.size, len(root.children))
    assert build_insights(root).total_bytes == 123
    assert build_purpose_report(root).total_bytes == 123
    assert before == (root.size, file.size, len(root.children))
