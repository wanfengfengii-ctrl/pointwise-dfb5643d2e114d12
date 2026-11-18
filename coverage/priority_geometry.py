from fractions import Fraction
from .rings import ring_edges, signed_area2, region_contains
from .segments import AtomicSegment, split_segments

def signed_moments(ring):
    area = Fraction(0)
    moment_x = Fraction(0)
    moment_y = Fraction(0)
    for p, q in ring_edges(tuple(tuple(v) for v in ring)):
        cr = p[0]*q[1] - q[0]*p[1]
        area += cr
        moment_x += (p[0] + q[0])*cr
        moment_y += (p[1] + q[1])*cr
    return area/2, moment_x/6, moment_y/6

def region_moments(rings):
    def upright(ring):
        area, moment_x, moment_y = signed_moments(ring)
        if area < 0:
            return -area, -moment_x, -moment_y
        return area, moment_x, moment_y
    area, moment_x, moment_y = upright(rings[0])
    for hole in rings[1:]:
        hole_area, hole_mx, hole_my = upright(hole)
        area -= hole_area
        moment_x -= hole_mx
        moment_y -= hole_my
    return area, moment_x, moment_y

def affine_integral(coefficients, rings):
    a, b, c = coefficients
    area, moment_x, moment_y = region_moments(rings)
    return a*moment_x + b*moment_y + c*area

def segment_y_at(segment, x):
    (ax, ay), (bx, by) = segment.start, segment.end
    if (ax, ay) > (bx, by):
        ax, ay, bx, by = bx, by, ax, ay
    return ay + (by - ay)*(x - ax)/(bx - ax)

def vertical_decomposition(regions, extra_edges=()):
    edges = []
    for rings in regions:
        for ring in rings:
            edges.extend(ring_edges(tuple(tuple(v) for v in ring)))
    edges.extend(tuple(tuple(v) for v in edge) for edge in extra_edges)
    segments = split_segments(tuple(AtomicSegment(a, b, ()) for a, b in edges))
    xs = sorted({s.start[0] for s in segments} | {s.end[0] for s in segments})
    slabs = []
    for x0, x1 in zip(xs, xs[1:]):
        xm = (x0 + x1)/2
        crossing = [s for s in segments if s.start[0] != s.end[0]
                    and min(s.start[0], s.end[0]) <= x0 and max(s.start[0], s.end[0]) >= x1]
        crossing.sort(key=lambda s: segment_y_at(s, xm))
        for low, high in zip(crossing, crossing[1:]):
            yl, yh = segment_y_at(low, xm), segment_y_at(high, xm)
            witness = (xm, (yl + yh)/2)
            covering = tuple(i for i, rings in enumerate(regions) if region_contains(witness, rings))
            if not covering:
                continue
            points = []
            for p in ((x0, segment_y_at(low, x0)), (x1, segment_y_at(low, x1)),
                      (x1, segment_y_at(high, x1)), (x0, segment_y_at(high, x0))):
                if not points or points[-1] != p:
                    points.append(p)
            if len(points) > 1 and points[0] == points[-1]:
                points.pop()
            if len(points) >= 3 and signed_area2(tuple(points)) != 0:
                slabs.append((tuple(points), covering, witness))
    return slabs

def clip_halfplane(points, coefficients, keep_positive):
    a, b, c = coefficients
    values = [a*p[0] + b*p[1] + c for p in points]
    result = []
    count = len(points)
    for i in range(count):
        j = (i + 1) % count
        vi, vj = values[i], values[j]
        inside = (vi >= 0) if keep_positive else (vi <= 0)
        if inside:
            result.append(points[i])
        if (vi > 0 and vj < 0) or (vi < 0 and vj > 0):
            t = vi/(vi - vj)
            result.append((points[i][0] + t*(points[j][0] - points[i][0]),
                           points[i][1] + t*(points[j][1] - points[i][1])))
    cleaned = []
    for p in result:
        if not cleaned or cleaned[-1] != p:
            cleaned.append(p)
    if len(cleaned) > 1 and cleaned[0] == cleaned[-1]:
        cleaned.pop()
    if len(cleaned) < 3 or signed_area2(tuple(cleaned)) == 0:
        return None
    return tuple(cleaned)

def split_convex(points, coefficients):
    return [piece for piece in (clip_halfplane(points, coefficients, True),
                                clip_halfplane(points, coefficients, False)) if piece is not None]
