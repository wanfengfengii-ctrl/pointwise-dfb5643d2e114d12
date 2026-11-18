from dataclasses import dataclass
from fractions import Fraction
from functools import cmp_to_key
from .rings import sub, cross, region_contains
from .segments import source_segments, split_segments

def direction_compare(a, b):
    upper_a = a[1] > 0 or (a[1] == 0 and a[0] >= 0)
    upper_b = b[1] > 0 or (b[1] == 0 and b[0] >= 0)
    if upper_a != upper_b:
        return -1 if upper_a else 1
    turn = cross(a, b)
    return -1 if turn > 0 else (1 if turn < 0 else 0)

@dataclass(frozen=True)
class FaceSide:
    witness: tuple
    covering: tuple

@dataclass(frozen=True)
class PlanarArrangement:
    segments: tuple
    revisions: tuple
    sides: tuple
    vertex_fans: dict

def face_witness(segment, side, segments):
    midpoint = tuple((a+b)/2 for a, b in zip(segment.start, segment.end))
    dx, dy = sub(segment.end, segment.start)
    normal = (-dy*side, dx*side)
    distances = [Fraction(1)]
    for other in segments:
        delta = sub(other.start, midpoint)
        edge = sub(other.end, other.start)
        denominator = cross(normal, edge)
        if denominator:
            t = cross(delta, edge)/denominator
            u = cross(delta, normal)/denominator
            if t > 0 and 0 <= u <= 1:
                distances.append(t)
        elif cross(delta, normal) == 0:
            axis = 0 if normal[0] else 1
            for endpoint in (other.start, other.end):
                t = (endpoint[axis]-midpoint[axis])/normal[axis]
                if t > 0:
                    distances.append(t)
    step = min(distances)/2
    return tuple(midpoint[i]+step*normal[i] for i in range(2))

def classify_faces(segments, revisions):
    result = []
    for segment in segments:
        pair = []
        for side in (1, -1):
            witness = face_witness(segment, side, segments)
            covering = tuple(i for i, rev in enumerate(revisions) if region_contains(witness, rev.rings))
            pair.append(FaceSide(witness, covering))
        result.append(tuple(pair))
    return tuple(result)

def build_arrangement(revisions):
    revisions = tuple(sorted(revisions, key=lambda r: (r.region_id, r.revision)))
    segments = split_segments(source_segments(revisions))
    fans = {}
    for index, segment in enumerate(segments):
        fans.setdefault(segment.start, []).append((sub(segment.end, segment.start), index, 1))
        fans.setdefault(segment.end, []).append((sub(segment.start, segment.end), index, -1))
    fans = {p: tuple(sorted(edges, key=cmp_to_key(lambda a, b: direction_compare(a[0], b[0])))) for p, edges in fans.items()}
    return PlanarArrangement(segments, revisions, classify_faces(segments, revisions), fans)

def trace_boundary_cycles(segments):
    outgoing = {}
    for index, segment in enumerate(segments):
        outgoing.setdefault(segment.start, []).append(index)
    successors = {}
    for index, segment in enumerate(segments):
        candidates = outgoing.get(segment.end, [])
        if not candidates:
            raise ValueError('open coverage boundary')
        reverse = sub(segment.start, segment.end)
        vectors = [(sub(segments[j].end, segments[j].start), j) for j in candidates] + [(reverse, -1)]
        vectors.sort(key=cmp_to_key(lambda a, b: direction_compare(a[0], b[0])))
        position = next(k for k, item in enumerate(vectors) if item[1] == -1)
        successors[index] = vectors[position-1][1]
    if sorted(successors.values()) != list(range(len(segments))):
        raise ValueError('boundary continuation is not a permutation')
    remaining = set(range(len(segments)))
    cycles = []
    while remaining:
        start = min(remaining)
        current = start
        cycle = []
        while current in remaining:
            remaining.remove(current)
            cycle.append(segments[current])
            current = successors[current]
        if current != start:
            raise ValueError('boundary joins another walk')
        cycles.append(tuple(cycle))
    return tuple(cycles)
