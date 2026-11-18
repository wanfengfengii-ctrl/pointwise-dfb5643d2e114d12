import unittest
from fractions import Fraction as F
from coverage import open_archive, put_region, seal_batch, build_report, sample_boundary

class TestSampling(unittest.TestCase):
    def setUp(self):
        self.session = open_archive(':memory:')
        self.session.__enter__()
        self.addCleanup(self.session.__exit__, None, None, None)
        ring = [(0,0),(4,0),(4,3),(0,3)]
        put_region('A',ring)
        put_region('B',list(reversed(ring)))
        seal_batch('day',[('B',1),('A',1)])
        self.report = build_report('r','day')

    def bottom(self):
        for c in self.report['components']:
            for b in c['boundaries']:
                for i,s in enumerate(b['segments']):
                    if s['start'] == [F(0),F(0)] and s['end'] == [F(4),F(0)]:
                        return b['boundary_id'], i
        self.fail('missing bottom boundary')

    def test_shared_source_segment(self):
        boundary, index = self.bottom()
        sample = sample_boundary('r',boundary,index,F(1,3))
        self.assertEqual(sample['point'],[F(4,3),F(0)])
        self.assertEqual([(s['region_id'],s['parameter']) for s in sample['sources']], [('A',F(1,3)),('B',F(2,3))])
        self.assertEqual(self.report['measurements']['total_area'],F(12))
        for t in (F(0),F(1)):
            sample = sample_boundary('r',boundary,index,t)
            self.assertEqual([s['parameter'] for s in sample['sources']],[t,1-t])
            self.assertEqual(len(sample['sources']),2)

    def test_parameter_errors_and_segment_identity(self):
        boundary,index = self.bottom()
        for t in (0, 0.5, True, F(-1), F(4,3)):
            with self.assertRaises(ValueError):
                sample_boundary('r',boundary,index,t)
        for report,b,idx in (('absent',boundary,index),('r','absent',index),('r',boundary,-1),('r',boundary,999),('r',boundary,True)):
            with self.assertRaises(KeyError):
                sample_boundary(report,b,idx,F(0))
        first = sample_boundary('r',boundary,index,F(0))
        first['sources'].clear()
        self.assertEqual(len(sample_boundary('r',boundary,index,F(0))['sources']),2)

if __name__ == '__main__':
    unittest.main()
