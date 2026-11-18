from .reading import read_report
from .sampling import validate_sample_parameter
from .coverage_union import geometry_from_data
from .boundary_measure import find_boundary_segment
from .intersections import interpolate
from .priority_fields import field_value, closed_region_contains

def sample_priority(report_id, boundary_id, segment_index, t):
    validate_sample_parameter(t)
    report = read_report(report_id)
    if report['format'] != 2:
        raise ValueError('not a priority report')
    geometry = geometry_from_data(report['components'])
    segment = find_boundary_segment(geometry, boundary_id, segment_index)
    point = interpolate(segment.start, segment.end, t)
    coefficients = {(field['region_id'], field['revision']): field['coefficients']
                    for field in report['priority']['fields']}
    best = None
    winners = []
    for source in report['inputs']:
        key = (source['region_id'], source['revision'])
        rings = tuple(tuple(tuple(p) for p in ring) for ring in source['rings'])
        if not closed_region_contains(point, rings):
            continue
        value = field_value(coefficients[key], point)
        if best is None or value > best:
            best, winners = value, [key]
        elif value == best:
            winners.append(key)
    if best is None:
        raise ValueError('boundary point is not covered by any saved input')
    return {'point': list(point), 'value': best,
            'winners': [{'region_id': region_id, 'revision': revision} for region_id, revision in winners]}
