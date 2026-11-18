from dataclasses import dataclass
from .rings import normalize_ring, ring_edges, signed_area2, point_location
from .intersections import segment_intersections

@dataclass(frozen=True)
class ValidatedRegion:
    outer: tuple
    holes: tuple
    @property
    def rings(self):
        return (self.outer,) + self.holes

def validate_simple_ring(ring):
    edges = ring_edges(ring)
    if not signed_area2(ring):
        raise ValueError('zero area ring')
    for i, (a, b) in enumerate(edges):
        if a == b:
            raise ValueError('zero length edge')
        for j in range(i+1, len(edges)):
            c, d = edges[j]
            hits = segment_intersections(a, b, c, d)
            adjacent = j == i+1 or (i == 0 and j == len(edges)-1)
            if adjacent:
                common = {a, b} & {c, d}
                if len(hits) != 1 or hits[0].point not in common:
                    raise ValueError('adjacent backtracking')
            elif hits:
                raise ValueError('self crossing or nonadjacent contact')
    return ring

def rings_meet(first, second):
    return any(segment_intersections(a, b, c, d) for a, b in ring_edges(first) for c, d in ring_edges(second))

def validate_hole_relations(outer, holes):
    for i, hole in enumerate(holes):
        if rings_meet(outer, hole) or any(point_location(p, outer) != 1 for p in hole):
            raise ValueError('hole must be strictly inside outer ring')
        for other in holes[:i]:
            if rings_meet(hole, other) or point_location(hole[0], other) != -1 or point_location(other[0], hole) != -1:
                raise ValueError('holes touch, overlap or nest')

def validate_region(outer, holes=()):
    try:
        outside = validate_simple_ring(normalize_ring(outer))
        inside = tuple(validate_simple_ring(normalize_ring(h)) for h in holes)
    except TypeError as exc:
        raise ValueError('invalid ring collection') from exc
    validate_hole_relations(outside, inside)
    return ValidatedRegion(outside, inside)
