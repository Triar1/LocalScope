from localscope.models import FileNode
from localscope.treemap import layout

def test_layout_area():
    nodes = [FileNode("a", "a", 75), FileNode("b", "b", 25)]
    rects = layout(nodes, 0, 0, 400, 100)
    assert len(rects) == 2
    assert abs(sum(w * h for _, _, _, w, h in rects) - 40000) < 0.001
    assert rects[0][3] == 300

def test_zero_sizes():
    assert layout([FileNode("empty", "empty", 0)], 0, 0, 100, 100) == []
