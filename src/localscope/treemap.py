"""Deterministic slice-and-dice treemap layout; coordinates are in scene units."""
from __future__ import annotations
from .models import FileNode


def layout(nodes: list[FileNode], x: float, y: float, w: float, h: float):
    positive = sorted((n for n in nodes if n.size > 0), key=lambda n: n.size, reverse=True)
    total = sum(n.size for n in positive)
    if not total or w <= 0 or h <= 0:
        return []
    result = []
    cursor = 0.0
    horizontal = w >= h
    for i, node in enumerate(positive):
        fraction = node.size / total
        if horizontal:
            width = (w - cursor) if i == len(positive) - 1 else w * fraction
            result.append((node, x + cursor, y, width, h))
            cursor += width
        else:
            height = (h - cursor) if i == len(positive) - 1 else h * fraction
            result.append((node, x, y + cursor, w, height))
            cursor += height
    return result
