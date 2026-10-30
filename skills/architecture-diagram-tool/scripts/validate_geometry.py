#!/usr/bin/env python3
"""Validate an orthogonal architecture layout using only the Python stdlib.

Input JSON:
  {"nodes": [{"id": "a", "x": 0, "y": 0, "w": 120, "h": 80}],
   "edges": [{"id": "e", "points": [[120, 40], [180, 40]]}]}

Exit code 0 means the layout passes. Exit code 1 means a collision or invalid
route was found. Touching borders is valid; positive-area overlaps and
connector crossings are not.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


EPS = 1e-9


@dataclass(frozen=True)
class Rect:
    ident: str
    x: float
    y: float
    w: float
    h: float

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h


Point = tuple[float, float]
Segment = tuple[Point, Point]


def number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a number")
    return float(value)


def parse_rect(raw: dict) -> Rect:
    ident = str(raw.get("id", ""))
    if not ident:
        raise ValueError("each node needs a non-empty id")
    rect = Rect(
        ident,
        number(raw.get("x"), f"node {ident}.x"),
        number(raw.get("y"), f"node {ident}.y"),
        number(raw.get("w"), f"node {ident}.w"),
        number(raw.get("h"), f"node {ident}.h"),
    )
    if rect.w <= 0 or rect.h <= 0:
        raise ValueError(f"node {ident} must have positive width and height")
    return rect


def parse_point(raw: Sequence[object], label: str) -> Point:
    if len(raw) != 2:
        raise ValueError(f"{label} must be [x, y]")
    return (number(raw[0], f"{label}.x"), number(raw[1], f"{label}.y"))


def parse_edges(raw_edges: Iterable[dict]) -> list[tuple[str, list[Point]]]:
    edges: list[tuple[str, list[Point]]] = []
    for raw in raw_edges:
        ident = str(raw.get("id", f"edge-{len(edges) + 1}"))
        raw_points = raw.get("points")
        if not isinstance(raw_points, list) or len(raw_points) < 2:
            raise ValueError(f"edge {ident} needs at least two points")
        points = [parse_point(point, f"edge {ident}.points[{idx}]") for idx, point in enumerate(raw_points)]
        edges.append((ident, points))
    return edges


def positive_overlap(a: Rect, b: Rect) -> bool:
    return min(a.x2, b.x2) - max(a.x, b.x) > EPS and min(a.y2, b.y2) - max(a.y, b.y) > EPS


def is_axis_aligned(a: Point, b: Point) -> bool:
    return abs(a[0] - b[0]) <= EPS or abs(a[1] - b[1]) <= EPS


def segment_intersects_rect_interior(segment: Segment, rect: Rect) -> bool:
    (x1, y1), (x2, y2) = segment
    if abs(x1 - x2) <= EPS:
        low, high = sorted((y1, y2))
        return rect.x + EPS < x1 < rect.x2 - EPS and high > rect.y + EPS and low < rect.y2 - EPS
    if abs(y1 - y2) <= EPS:
        low, high = sorted((x1, x2))
        return rect.y + EPS < y1 < rect.y2 - EPS and high > rect.x + EPS and low < rect.x2 - EPS
    return False


def collinear_overlap(a: Point, b: Point, c: Point, d: Point) -> bool:
    if abs(a[0] - b[0]) <= EPS and abs(c[0] - d[0]) <= EPS:
        if abs(a[0] - c[0]) > EPS:
            return False
        return min(max(a[1], b[1]), max(c[1], d[1])) - max(min(a[1], b[1]), min(c[1], d[1])) > EPS
    if abs(a[1] - b[1]) <= EPS and abs(c[1] - d[1]) <= EPS:
        if abs(a[1] - c[1]) > EPS:
            return False
        return min(max(a[0], b[0]), max(c[0], d[0])) - max(min(a[0], b[0]), min(c[0], d[0])) > EPS
    return False


def proper_perpendicular_crossing(a: Point, b: Point, c: Point, d: Point) -> bool:
    a_vertical = abs(a[0] - b[0]) <= EPS
    c_vertical = abs(c[0] - d[0]) <= EPS
    if a_vertical == c_vertical:
        return False
    if a_vertical:
        vx, vy_low, vy_high = a[0], min(a[1], b[1]), max(a[1], b[1])
        hy, hx_low, hx_high = c[1], min(c[0], d[0]), max(c[0], d[0])
    else:
        vx, vy_low, vy_high = c[0], min(c[1], d[1]), max(c[1], d[1])
        hy, hx_low, hx_high = a[1], min(a[0], b[0]), max(a[0], b[0])
    return hx_low + EPS < vx < hx_high - EPS and vy_low + EPS < hy < vy_high - EPS


def main() -> int:
    source = sys.stdin.read() if len(sys.argv) < 2 or sys.argv[1] == "-" else Path(sys.argv[1]).read_text(encoding="utf-8")
    try:
        payload = json.loads(source)
        nodes = [parse_rect(item) for item in payload.get("nodes", [])]
        edges = parse_edges(payload.get("edges", []))
    except (OSError, json.JSONDecodeError, TypeError, ValueError, AttributeError) as exc:
        print(f"geometry: INVALID INPUT — {exc}")
        return 1

    errors: list[str] = []
    for index, left in enumerate(nodes):
        for right in nodes[index + 1 :]:
            if positive_overlap(left, right):
                errors.append(f"node overlap: {left.ident} / {right.ident}")

    segments_by_edge: dict[str, list[Segment]] = {}
    for edge_id, points in edges:
        segments: list[Segment] = []
        for start, end in zip(points, points[1:]):
            if math.isclose(start[0], end[0], abs_tol=EPS) and math.isclose(start[1], end[1], abs_tol=EPS):
                errors.append(f"zero-length segment: {edge_id}")
                continue
            if not is_axis_aligned(start, end):
                errors.append(f"diagonal segment: {edge_id} {start} -> {end}")
            segments.append((start, end))
        segments_by_edge[edge_id] = segments
        for segment in segments:
            for node in nodes:
                if segment_intersects_rect_interior(segment, node):
                    errors.append(f"connector enters node interior: {edge_id} / {node.ident}")

    edge_items = list(segments_by_edge.items())
    for index, (left_id, left_segments) in enumerate(edge_items):
        for right_id, right_segments in edge_items[index + 1 :]:
            for left in left_segments:
                for right in right_segments:
                    if collinear_overlap(*left, *right) or proper_perpendicular_crossing(*left, *right):
                        errors.append(f"connector crossing or overlap: {left_id} / {right_id}")

    unique_errors = list(dict.fromkeys(errors))
    if unique_errors:
        for error in unique_errors:
            print(f"FAIL: {error}")
        print(f"geometry: FAIL ({len(unique_errors)} issue(s))")
        return 1
    print(f"geometry: PASS ({len(nodes)} nodes, {len(edges)} edges)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
