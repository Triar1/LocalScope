from pathlib import Path
import pytest
from localscope.scanner import scan
from localscope.optimization import find_duplicates, AnalysisCancelled


def test_duplicate_groups(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'alpha')
    (tmp_path/'b.txt').write_bytes(b'alpha')
    (tmp_path/'c.txt').write_bytes(b'bravo')
    groups, hashed, skipped = find_duplicates(scan(str(tmp_path)))
    assert len(groups) == 1
    assert groups[0].extra_bytes == 5
    assert len(groups[0].paths) == 2
    assert hashed == 2  # one unique sample avoids a full second hash
    assert skipped == 0


def test_no_false_positive_same_size(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'one')
    (tmp_path/'b.txt').write_bytes(b'two')
    groups, *_ = find_duplicates(scan(str(tmp_path)))
    assert groups == []


def test_cancel(tmp_path):
    (tmp_path/'a.txt').write_bytes(b'hello')
    (tmp_path/'b.txt').write_bytes(b'hello')
    with pytest.raises(AnalysisCancelled):
        find_duplicates(scan(str(tmp_path)), cancelled=lambda: True)


def test_phase_reporting_and_confirmed_groups(tmp_path):
    (tmp_path/'a.bin').write_bytes(b'a' * (3*1024*1024))
    (tmp_path/'b.bin').write_bytes(b'a' * (3*1024*1024))
    (tmp_path/'c.bin').write_bytes(b'b' * (3*1024*1024))
    events, emitted = [], []
    groups, hashed, skipped = find_duplicates(scan(str(tmp_path)),
        status=lambda *args: events.append(args), group_found=emitted.append)
    assert len(groups) == 1 and groups == emitted
    assert hashed == 2 and skipped == 0
    assert {event[0] for event in events} >= {'Sampling', 'Verifying SHA-256', 'Complete'}


def test_offline_flag_skips_without_open(tmp_path, monkeypatch):
    from localscope import optimization
    (tmp_path/'a').write_bytes(b'same')
    (tmp_path/'b').write_bytes(b'same')
    monkeypatch.setattr(optimization, '_offline', lambda p: p.endswith('a'))
    groups, hashed, skipped = find_duplicates(scan(str(tmp_path)))
    assert not groups and skipped == 1


def test_indexing_reports_before_hashing(tmp_path):
    (tmp_path/'one.txt').write_text('abc')
    (tmp_path/'two.txt').write_text('abc')
    phases = []
    find_duplicates(scan(str(tmp_path)), status=lambda phase, *args: phases.append(phase))
    assert phases[0] == 'Indexing file tree'
    assert 'Indexing complete' in phases
    assert phases.index('Indexing complete') < phases.index('Sampling')

def test_cancel_during_indexing(tmp_path):
    (tmp_path/'one.txt').write_text('abc')
    (tmp_path/'two.txt').write_text('abc')
    seen = []
    def status(phase, *args):
        seen.append(phase)
    with pytest.raises(AnalysisCancelled):
        find_duplicates(scan(str(tmp_path)), status=status, cancelled=lambda: bool(seen))
    assert seen == ['Indexing file tree']
