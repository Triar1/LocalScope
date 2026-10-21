from localscope.models import FileNode
from localscope.redundancy import analyze_redundancy


def test_version_family(tmp_path):
    def project(name):
        p = tmp_path / name
        p.mkdir()
        marker = p / 'pyproject.toml'
        marker.write_text('[project]')
        return FileNode(name, str(p), 100, True, [FileNode(marker.name, str(marker), 9)])
    root = FileNode('root', str(tmp_path), is_dir=True,
                    children=[project('mailpilot-v0.1'), project('mailpilot-v0.3')])
    report = analyze_redundancy(root)
    assert any(x.kind == 'Project versions' for x in report.insights)
    assert report.duplicate_extra_bytes == 0


def test_exact_duplicates_are_explicit_and_read_only(tmp_path):
    files = []
    for name in ('a.txt', 'b.txt', 'c.txt'):
        p = tmp_path / name
        p.write_bytes(b'same bytes' if name != 'c.txt' else b'other data')
        files.append(FileNode(name, str(p), p.stat().st_size))
    root = FileNode('root', str(tmp_path), is_dir=True, children=files)
    assert analyze_redundancy(root).exact_duplicate_groups == 0
    report = analyze_redundancy(root, hash_duplicates=True)
    assert report.exact_duplicate_groups == 1
    assert report.duplicate_extra_bytes == len(b'same bytes')
    assert all((tmp_path / name).exists() for name in ('a.txt', 'b.txt', 'c.txt'))


def test_different_bytes_same_size(tmp_path):
    nodes = []
    for name, data in [('a.bin', b'123'), ('b.bin', b'456')]:
        p = tmp_path / name
        p.write_bytes(data)
        nodes.append(FileNode(name, str(p), 3))
    report = analyze_redundancy(FileNode('root', str(tmp_path), is_dir=True, children=nodes), hash_duplicates=True)
    assert report.exact_duplicate_groups == 0
