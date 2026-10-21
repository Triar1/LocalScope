from localscope.models import FileNode
from localscope.storage_insights import build_insights, category_for


def test_categories_case_insensitive_and_unknown():
    assert category_for('MOVIE.MP4') == 'Videos'
    assert category_for('photo.JPEG') == 'Photos'
    assert category_for('noextension') == 'Other'


def test_breakdown_and_folder_ranking():
    a = FileNode('a', '/a', 130, True, [
        FileNode('movie.mp4', '/a/movie.mp4', 100),
        FileNode('photo.jpg', '/a/photo.jpg', 30)])
    b = FileNode('b', '/b', 40, True, [FileNode('notes.pdf', '/b/notes.pdf', 40)])
    root = FileNode('root', '/', 170, True, [a, b], 2)
    result = build_insights(root)
    sizes = {c.category: c.bytes for c in result.categories}
    assert sizes['Videos'] == 100
    assert sizes['Photos'] == 30
    assert sizes['Documents'] == 40
    assert result.total_files == 3
    assert result.folders[0].path == '/a'
    assert result.access_errors == 2


def test_empty_scan():
    result = build_insights(FileNode('empty', '/', 0, True))
    assert result.total_files == 0
    assert not result.folders
