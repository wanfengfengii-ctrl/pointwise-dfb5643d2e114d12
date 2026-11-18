from dataclasses import dataclass, replace
from fractions import Fraction
from .rings import ring_edges
from .intersections import segment_intersections, interpolate

@dataclass(frozen=True, order=True)
class SourceSpan:
    region_id: str
    revision: int
    ring_index: int
    edge_index: int
    t0: Fraction
    t1: Fraction
    def reversed(self):
        return replace(self, t0=self.t1, t1=self.t0)

@dataclass(frozen=True)
class AtomicSegment:
    start: tuple
    end: tuple
    sources: tuple
    def reversed(self):
        return AtomicSegment(self.end, self.start, tuple(sorted(s.reversed() for s in self.sources)))

def source_segments(revisions):
    result = []
    for revision in revisions:
        for ri, ring in enumerate(revision.rings):
            for ei, (a, b) in enumerate(ring_edges(ring)):
                result.append(AtomicSegment(a, b, (SourceSpan(revision.region_id, revision.revision, ri, ei, Fraction(0), Fraction(1)),)))
    return tuple(result)

def merge_segment_sources(segments):
    grouped = {}
    for segment in segments:
        if segment.start > segment.end:
            segment = segment.reversed()
        grouped.setdefault((segment.start, segment.end), set()).update(segment.sources)
    return tuple(AtomicSegment(a, b, tuple(sorted(sources))) for (a, b), sources in sorted(grouped.items()))

def split_segments(segments):
    parameters = [{Fraction(0), Fraction(1)} for _ in segments]
    for i, first in enumerate(segments):
        for j in range(i+1, len(segments)):
            second = segments[j]
            for hit in segment_intersections(first.start, first.end, second.start, second.end):
                parameters[i].add(hit.first_parameter)
                parameters[j].add(hit.second_parameter)
    pieces = []
    for segment, cuts in zip(segments, parameters):
        ordered = sorted(cuts)
        for t0, t1 in zip(ordered, ordered[1:]):
            spans = tuple(replace(s, t0=s.t0+(s.t1-s.t0)*t0, t1=s.t0+(s.t1-s.t0)*t1) for s in segment.sources)
            pieces.append(AtomicSegment(interpolate(segment.start, segment.end, t0), interpolate(segment.start, segment.end, t1), spans))
    return merge_segment_sources(pieces)
