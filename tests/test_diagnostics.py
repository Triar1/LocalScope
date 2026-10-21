from localscope.scanner import scan
from localscope.optimization import find_duplicates

def test_status_reports_hash_phase_and_bytes(tmp_path):
    (tmp_path / "a").write_bytes(b"abc" * 1000)
    (tmp_path / "b").write_bytes(b"abc" * 1000)
    events = []
    groups, hashed, skipped = find_duplicates(scan(str(tmp_path)), status=lambda *x: events.append(x))
    assert groups and hashed == 2 and skipped == 0
    assert any(x[0] == "Sampling" and x[2] == 2 for x in events)
    assert events[-1][0] == "Complete" and events[-1][4] > 0
