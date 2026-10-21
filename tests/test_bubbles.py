import math
from localscope.bubbles import layout_bubbles
from localscope.models import FileNode


def test_bubbles_do_not_overlap():
    nodes = [FileNode(str(i), str(i), size=100-i) for i in range(25)]
    result = layout_bubbles(nodes)
    assert len(result) == 25
    for i, (_, x, y, r) in enumerate(result):
        for _, xx, yy, rr in result[i+1:]:
            assert math.hypot(x+r-xx-rr, y+r-yy-rr) + 1e-6 >= r+rr


def test_bubble_area_ratio():
    nodes = [FileNode('a', 'a', size=400), FileNode('b', 'b', size=100)]
    result = layout_bubbles(nodes)
    assert math.isclose((result[0][3] / result[1][3]) ** 2, 4)


def test_empty_layout():
    assert layout_bubbles([]) == []
