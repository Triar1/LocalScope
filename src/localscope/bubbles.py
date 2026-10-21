"""Deterministic, non-overlapping circle layout for immediate child nodes."""
from __future__ import annotations
import math
from .models import FileNode


def layout_bubbles(nodes: list[FileNode], width: float = 850, height: float = 590, limit: int = 45):
    if width <= 0 or height <= 0 or limit <= 0:
        return []
    ranked = sorted((n for n in nodes if n.size > 0), key=lambda n: n.size, reverse=True)[:limit]
    if not ranked:
        return []
    # The area of each circle is proportional to the underlying file size.
    total = sum(n.size for n in ranked)
    radii = [math.sqrt(n.size / total) for n in ranked]
    placed = []
    for node, radius in zip(ranked, radii):
        if not placed:
            x, y = 0.0, 0.0
        else:
            x = y = 0.0
            for i in range(1, 14000):
                angle = i * 2.399963229728653
                distance = 0.013 * math.sqrt(i)
                px, py = distance * math.cos(angle), distance * math.sin(angle)
                if all(math.hypot(px - ox, py - oy) >= radius + other + .012 for _, ox, oy, other in placed):
                    x, y = px, py
                    break
            else:
                # Always place the node, even for pathological distributions.
                x = max(ox + other for _, ox, _, other in placed) + radius + .02
                y = 0.0
        placed.append((node, x, y, radius))
    left = min(x-r for _, x, y, r in placed)
    right = max(x+r for _, x, y, r in placed)
    top = min(y-r for _, x, y, r in placed)
    bottom = max(y+r for _, x, y, r in placed)
    scale = min((width-24)/max(right-left, 1e-8), (height-24)/max(bottom-top, 1e-8))
    return [(n, 12+(x-r-left)*scale, 12+(y-r-top)*scale, r*scale) for n,x,y,r in placed]
