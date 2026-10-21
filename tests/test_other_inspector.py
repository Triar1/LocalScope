from localscope.models import FileNode
from localscope.other_inspector import inspect_other


def test_unknown_direct_files_and_known_categories_do_not_overlap():
    root = FileNode('Downloads', r'C:\Users\a\Downloads', 130, True, [
        FileNode('mystery.bin', r'C:\Users\a\Downloads\mystery.bin', 70),
        FileNode('notes.pdf', r'C:\Users\a\Downloads\notes.pdf', 60),
    ])
    report = inspect_other(root)
    assert report.total == 70
    assert report.file_count == 1
    assert report.extensions == (('.bin', 70, 1),)
    assert len(report.items) == 1


def test_unknown_folder_is_reported_once():
    root = FileNode('root', r'C:\root', 30, True, [
        FileNode('unclassified', r'C:\root\unclassified', 30, True, [
            FileNode('a.dat', r'C:\root\unclassified\a.dat', 30)
        ])
    ])
    report = inspect_other(root)
    assert report.total == 30
    assert sum(i.size for i in report.items) == 30


def test_empty_tree():
    report = inspect_other(FileNode('root', r'C:\root', 0, True))
    assert report.total == 0
    assert report.items == ()
