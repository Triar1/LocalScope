from localscope.scanner import scan
from localscope.models import format_size

def test_scan_sizes(tmp_path):
    (tmp_path / "hello.txt").write_bytes(b"abc")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "data.bin").write_bytes(b"12345")
    result = scan(str(tmp_path))
    assert result.size == 8
    assert result.total_files == 2
    assert next(c for c in result.children if c.name == "nested").size == 5

def test_empty_folder(tmp_path):
    result = scan(str(tmp_path))
    assert result.size == 0
    assert result.total_files == 0

def test_format_size():
    assert format_size(1024) == "1.0 KiB"
