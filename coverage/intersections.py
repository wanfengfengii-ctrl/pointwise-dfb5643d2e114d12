from dataclasses import dataclass
from fractions import Fraction
from .rings import cross, sub

@dataclass(frozen=True)
class SegmentIntersection:
    point: tuple
    first_parameter: Fraction
    second_parameter: Fraction

def parameter_on_segment(p, a, b):
    if a == b:
        raise ValueError('zero length segment')
    d = sub(b, a)
    if cross(d, sub(p, a)) != 0:
        raise ValueError('point is not collinear')
    t = (p[0]-a[0])/d[0] if d[0] else (p[1]-a[1])/d[1]
    return Fraction(t)

def point_on_segment(p, a, b):
    return a != b and cross(sub(b, a), sub(p, a)) == 0 and 0 <= parameter_on_segment(p, a, b) <= 1

def interpolate(a, b, t):
    return tuple(a[i] + t*(b[i]-a[i]) for i in range(2))

def segment_intersections(a, b, c, d):
    u, v = sub(b, a), sub(d, c)
    denominator = cross(u, v)
    if a == b or c == d:
        raise ValueError('zero length segment')
    if denominator:
        t = Fraction(cross(sub(c, a), v), denominator)
        s = Fraction(cross(sub(c, a), u), denominator)
        if 0 <= t <= 1 and 0 <= s <= 1:
            return (SegmentIntersection(interpolate(a, b, t), t, s),)
        return ()
    if cross(sub(c, a), u):
        return ()
    points = sorted({p for p in (a, b, c, d) if point_on_segment(p, a, b) and point_on_segment(p, c, d)})
    return tuple(SegmentIntersection(p, parameter_on_segment(p, a, b), parameter_on_segment(p, c, d)) for p in points)
