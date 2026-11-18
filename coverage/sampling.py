from fractions import Fraction
from dataclasses import asdict
from .reading import read_fixed_geometry
from .boundary_measure import find_boundary_segment
from .intersections import interpolate

def validate_sample_parameter(t):
    if type(t) is not Fraction or not 0 <= t <= 1:
        raise ValueError('t must be a Fraction in [0,1]')
    return t

def interpolate_source_span(source, t):
    result = asdict(source)
    result['parameter'] = source.t0 + t*(source.t1-source.t0)
    return result

def sample_boundary(report_id, boundary_id, segment_index, t):
    validate_sample_parameter(t)
    geometry = read_fixed_geometry(report_id)
    segment = find_boundary_segment(geometry, boundary_id, segment_index)
    return {'point': list(interpolate(segment.start, segment.end, t)),
            'sources': [interpolate_source_span(source, t) for source in segment.sources]}
