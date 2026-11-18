from fractions import Fraction

def exact(value):
    if isinstance(value, bool) or not isinstance(value, (int, Fraction)):
        raise ValueError('coordinate must be an integer or Fraction')
    return Fraction(value)

def point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError('point requires two coordinates')
    return tuple(exact(v) for v in value)

def normalize_ring(values):
    try:
        ring = tuple(point(v) for v in values)
    except TypeError as exc:
        raise ValueError('ring must be iterable') from exc
    if len(ring) > 1 and ring[0] == ring[-1]:
        ring = ring[:-1]
    if len(ring) < 3 or len(set(ring)) != len(ring):
        raise ValueError('ring needs distinct vertices')
    return ring

def ring_edges(ring):
    return tuple(zip(ring, ring[1:] + ring[:1]))

def cross(a, b):
    return a[0]*b[1] - a[1]*b[0]

def sub(a, b):
    return a[0]-b[0], a[1]-b[1]

def signed_area2(ring):
    return sum((cross(a, b) for a, b in ring_edges(ring)), Fraction())

def orient(ring, positive=True):
    return ring if (signed_area2(ring) > 0) == positive else tuple(reversed(ring))

def point_location(p, ring):
    winding = 0
    for a, b in ring_edges(ring):
        c = cross(sub(b, a), sub(p, a))
        if c == 0 and min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[1] <= max(a[1], b[1]):
            return 0
        if a[1] <= p[1] < b[1] and c > 0:
            winding += 1
        elif b[1] <= p[1] < a[1] and c < 0:
            winding -= 1
    return 1 if winding else -1

def region_contains(p, rings):
    return point_location(p, rings[0]) == 1 and all(point_location(p, h) == -1 for h in rings[1:])

def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('identity must be a nonempty string')
    return value
