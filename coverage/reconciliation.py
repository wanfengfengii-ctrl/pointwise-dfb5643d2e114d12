from dataclasses import dataclass
from fractions import Fraction
from .rings import ring_edges
from .segments import SourceSpan
from .intersections import point_on_segment, parameter_on_segment, segment_intersections
from .coverage_union import geometry_from_data
from .areas import area_items, coverage_area
from .boundary_measure import boundary_measurements

@dataclass(frozen=True)
class ReconciliationResult:
    component_count: int
    boundary_count: int
    segment_count: int
    total_area: Fraction

def verify_source_spans(report, geometry):
    originals = []
    for revision in report['inputs']:
        for ri, ring in enumerate(revision['rings']):
            for ei, (a, b) in enumerate(ring_edges(tuple(tuple(p) for p in ring))):
                originals.append((revision['region_id'], revision['revision'], ri, ei, a, b))
    for component in geometry.components:
        for loop in component.boundaries:
            for segment in loop.segments:
                expected = []
                for region_id, revision, ri, ei, a, b in originals:
                    hits = segment_intersections(segment.start, segment.end, a, b)
                    if len(hits) == 2:
                        if not (point_on_segment(segment.start, a, b) and point_on_segment(segment.end, a, b)):
                            raise ValueError('boundary omits an original endpoint split')
                        expected.append(SourceSpan(region_id, revision, ri, ei,
                            parameter_on_segment(segment.start, a, b), parameter_on_segment(segment.end, a, b)))
                    elif hits and 0 < hits[0].first_parameter < 1:
                        raise ValueError('boundary omits an intersection split')
                if tuple(sorted(expected)) != segment.sources:
                    raise ValueError('incomplete or incorrect boundary sources')

def verify_measurement_items(report, geometry):
    expected = {'areas': area_items(geometry), 'total_area': coverage_area(geometry),
                'boundary': boundary_measurements(geometry)}
    if report['measurements'] != expected:
        raise ValueError('measurement reconciliation failed')

def reconcile_report(report):
    from .result_codec import validate_report_structure
    geometry = validate_report_structure(report)
    verify_measurement_items(report, geometry)
    verify_source_spans(report, geometry)
    boundaries = [b for c in geometry.components for b in c.boundaries]
    return ReconciliationResult(len(geometry.components), len(boundaries),
        sum(len(b.segments) for b in boundaries), coverage_area(geometry))
