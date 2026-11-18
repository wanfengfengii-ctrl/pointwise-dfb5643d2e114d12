from fractions import Fraction

def segment_length_squared(segment):
    return sum(((b-a)**2 for a, b in zip(segment.start, segment.end)), Fraction())

def validate_planar_loops(geometry):
    for component in geometry.components:
        for boundary in component.boundaries:
            segments = boundary.segments
            if len(segments) < 3:
                raise ValueError('a planar loop needs at least three segments')
            for first, second in zip(segments, segments[1:]+segments[:1]):
                if first.start == first.end or first.end != second.start or not first.sources:
                    raise ValueError('open or invalid planar loop')
            displacement = tuple(sum((s.end[i]-s.start[i] for s in segments), Fraction()) for i in range(2))
            if displacement != (0, 0):
                raise ValueError('planar displacement must be zero')
    return geometry

def boundary_measurements(geometry):
    validate_planar_loops(geometry)
    return [{'boundary_id': b.boundary_id, 'length_squared': [segment_length_squared(s) for s in b.segments]}
            for c in geometry.components for b in c.boundaries]

def find_boundary_segment(geometry, boundary_id, segment_index):
    if type(segment_index) is not int or segment_index < 0:
        raise KeyError((boundary_id, segment_index))
    for component in geometry.components:
        for boundary in component.boundaries:
            if boundary.boundary_id == boundary_id:
                if segment_index >= len(boundary.segments):
                    raise KeyError((boundary_id, segment_index))
                return boundary.segments[segment_index]
    raise KeyError(boundary_id)
