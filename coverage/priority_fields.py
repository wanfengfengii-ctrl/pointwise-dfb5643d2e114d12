from .rings import exact, point_location

MAX_PRIORITY_MEMBERS = 8
MAX_PRIORITY_EDGES = 80

def normalize_fields(fields, binding):
    if not isinstance(fields, dict):
        raise ValueError('fields must be a dict of region_id to [a, b, c]')
    members = binding.members
    if len(members) > MAX_PRIORITY_MEMBERS:
        raise ValueError('priority batch allows at most 8 members')
    edge_count = sum(len(ring) for revision in binding.revisions for ring in revision.rings)
    if edge_count > MAX_PRIORITY_EDGES:
        raise ValueError('priority batch allows at most 80 original edges')
    if set(fields) != {member.region_id for member in members}:
        raise ValueError('fields keys must be exactly the sealed batch region ids')
    normalized = []
    for member in members:
        value = fields[member.region_id]
        if not isinstance(value, (list, tuple)) or len(value) != 3:
            raise ValueError('coefficients must be a list or tuple of three rationals')
        normalized.append((member.region_id, member.revision, tuple(exact(v) for v in value)))
    return tuple(normalized)

def field_value(coefficients, p):
    a, b, c = coefficients
    return a*p[0] + b*p[1] + c

def closed_region_contains(p, rings):
    if point_location(p, rings[0]) == -1:
        return False
    return all(point_location(p, hole) != 1 for hole in rings[1:])
