import unittest
from fractions import Fraction as F
from coverage import open_archive, put_region, seal_batch, build_report
from coverage.coverage_union import geometry_from_data
from coverage.rings import cross

def rect(x0, y0, x1, y1):
    return [(x0,y0),(x1,y0),(x1,y1),(x0,y1)]

def independent_area(shapes):
    edges = []
    for outer, holes in shapes:
        for ring in (outer,) + tuple(holes):
            points = [tuple(F(v) for v in p) for p in ring]
            edges.extend(zip(points, points[1:]+points[:1]))
    cuts = {p[0] for edge in edges for p in edge}
    for a,b in edges:
        ux,uy = b[0]-a[0],b[1]-a[1]
        for c,d in edges:
            vx,vy = d[0]-c[0],d[1]-c[1]
            denominator = ux*vy-uy*vx
            if denominator:
                dx,dy = c[0]-a[0],c[1]-a[1]
                t,u = (dx*vy-dy*vx)/denominator,(dx*uy-dy*ux)/denominator
                if 0 <= t <= 1 and 0 <= u <= 1:
                    cuts.add(a[0]+t*ux)
    ordered = sorted(cuts)
    total = F(0)
    for lo,hi in zip(ordered,ordered[1:]):
        x = (lo+hi)/2
        intervals = []
        for outer,holes in shapes:
            crossings = []
            for ring in (outer,) + tuple(holes):
                for a,b in zip(ring,ring[1:]+ring[:1]):
                    if min(a[0],b[0]) < x < max(a[0],b[0]):
                        crossings.append(F(a[1])+(x-a[0])*F(b[1]-a[1],b[0]-a[0]))
            crossings.sort()
            intervals.extend(zip(crossings[::2],crossings[1::2]))
        merged = []
        for a,b in sorted(intervals):
            if merged and a <= merged[-1][1]:
                merged[-1] = (merged[-1][0],max(b,merged[-1][1]))
            else:
                merged.append((a,b))
        total += (hi-lo)*sum((b-a for a,b in merged),F(0))
    return total

class TestCoverage(unittest.TestCase):
    def setUp(self):
        self.session = open_archive(':memory:')
        self.archive = self.session.__enter__()
        self.addCleanup(self.session.__exit__, None, None, None)

    def report(self, shapes, report_id='r'):
        members = []
        for name, outer, holes in shapes:
            members.append((name, put_region(name, outer, holes)))
        seal_batch(report_id, members)
        return build_report(report_id, report_id)

    def test_overlapping_rectangles(self):
        report = self.report([('A',rect(0,0,4,3),()),('B',rect(2,1,6,4),())])
        self.assertEqual(report['measurements']['total_area'], F(20))
        self.assertEqual(len(report['components']), 1)
        segments = report['components'][0]['boundaries'][0]['segments']
        self.assertEqual(len(segments), 8)
        self.assertFalse(any(s['start'][0] == s['end'][0] == 2 and min(s['start'][1],s['end'][1]) < 3 and max(s['start'][1],s['end'][1]) > 1 for s in segments))

    def test_fractional_split_and_internal_edges(self):
        report = self.report([('T',[(0,0),(3,0),(0,2)],()),('R',rect(1,0,3,1),())])
        self.assertEqual(report['measurements']['total_area'], F(15,4))
        self.assertEqual(F(3)+F(2)-report['measurements']['total_area'], F(5,4))
        endpoints = [tuple(s['start']) for c in report['components'] for b in c['boundaries'] for s in b['segments']]
        self.assertIn((F(3,2),F(1)), endpoints)
        containing = self.report([('O',rect(0,0,5,5),()),('I',rect(1,1,2,2),())], 'contains')
        self.assertEqual(containing['measurements']['total_area'], F(25))
        self.assertEqual(sum(len(c['boundaries']) for c in containing['components']), 1)
        adjacent = self.report([('L',rect(0,0,1,1),()),('D',rect(1,0,2,1),())], 'adjacent')
        self.assertEqual(adjacent['measurements']['total_area'], F(2))
        self.assertEqual(len(adjacent['components']), 1)
        for c in adjacent['components']:
            for b in c['boundaries']:
                self.assertFalse(any(s['start'][0] == s['end'][0] == 1 for s in b['segments']))

    def test_hole_and_point_contact(self):
        base = ('A',rect(0,0,6,6),(rect(2,2,4,4),))
        point = self.report([base,('P',rect(6,6,7,7),())], 'point')
        edge = self.report([base,('E',rect(6,0,7,1),())], 'edge')
        for report, count in ((point,2),(edge,1)):
            self.assertEqual(report['measurements']['total_area'], F(33))
            self.assertEqual(len(report['components']), count)
        geometry = geometry_from_data(point['components'])
        signs = [sum(cross(s.start,s.end) for s in b.segments) for c in geometry.components for b in c.boundaries]
        self.assertEqual(sorted(signs), [F(-8),F(2),F(72)])
        filled = self.report([base,('F',rect(2,2,4,4),())], 'filled')
        self.assertEqual(filled['measurements']['total_area'], F(36))
        self.assertEqual(sum(len(c['boundaries']) for c in filled['components']), 1)

    def test_independent_vertical_slice_oracle(self):
        for shift in range(-3,4):
            shapes = [
                ([(0,0),(5,0),(1,4)],()),
                ([(shift,1),(shift+4,3),(shift+1,5)],()),
                (rect(-1,-1,3,3),(rect(0,0,1,1),)),
            ]
            report = self.report([(str(i),outer,holes) for i,(outer,holes) in enumerate(shapes)], 'slice'+str(shift))
            self.assertEqual(report['measurements']['total_area'],independent_area(shapes))

    def test_order_and_small_rectangle_oracle(self):
        put_region('A', rect(0,0,2,2))
        put_region('B', rect(1,1,3,3))
        seal_batch('a', [('A',1),('B',1)])
        seal_batch('b', [('B',1),('A',1)])
        first, second = build_report('one','a'), build_report('two','b')
        self.assertEqual(first['components'], second['components'])
        self.assertEqual(first['measurements'], second['measurements'])
        self.assertEqual(first, build_report('one','a'))
        for shift in range(-2,3):
            boxes = [(0,0,2,2),(shift,1,shift+2,3)]
            expected = sum(any(x0 <= x < x1 and y0 <= y < y1 for x0,y0,x1,y1 in boxes)
                           for x in range(-2,5) for y in range(3))
            report = self.report([(str(i),rect(*box),()) for i,box in enumerate(boxes)], 'grid'+str(shift))
            self.assertEqual(report['measurements']['total_area'], F(expected))

if __name__ == '__main__':
    unittest.main()
