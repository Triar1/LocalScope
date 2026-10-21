from localscope.models import FileNode
from localscope.smart_categories import build_purpose_report

def test_direct_files_are_split_and_not_double_counted():
    files = [FileNode('setup.exe', 'C:/Downloads/setup.exe', 100),
             FileNode('movie.mp4', 'C:/Downloads/movie.mp4', 200),
             FileNode('report.pdf', 'C:/Downloads/report.pdf', 30),
             FileNode('unknown.blob', 'C:/Downloads/unknown.blob', 9)]
    root = FileNode('Downloads', 'C:/Downloads', 339, True, files)
    report = build_purpose_report(root)
    totals = {t.purpose: t.bytes for t in report.totals}
    assert totals['Installers'] == 100
    assert totals['Media'] == 200
    assert totals['Documents'] == 30
    assert totals['Other'] == 9
    assert report.classified_bytes == 339
    assert sum(t.files for t in report.totals) == 4
    assert all(row.node is root for row in report.entries)
