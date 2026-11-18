import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction as F
from coverage import open_archive, put_region, seal_batch, build_report, read_report, sample_boundary, export_report, open_package
from coverage.reconciliation import reconcile_report

def prepare():
    ring = [(0,0),(4,0),(4,3),(0,3)]
    put_region('A',ring)
    put_region('B',list(reversed(ring)))
    seal_batch('day',[('A',1),('B',1)])
    return build_report('r','day')

class TestDelivery(unittest.TestCase):
    def test_revision_reopen_isolation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'archive.sqlite'
            with open_archive(path):
                report = prepare()
                saved = export_report('r')
                boundary = report['components'][0]['boundaries'][0]['boundary_id']
                sample = sample_boundary('r',boundary,0,F(1,3))
                report['components'][0]['boundaries'][0]['segments'][0]['sources'].clear()
                report['inputs'][0]['rings'][0][0][0] = F(999)
                report['measurements']['areas'].clear()
                put_region('A',[(0,0),(8,0),(8,3),(0,3)])
                self.assertEqual(export_report('r'),saved)
                with self.assertRaises(KeyError):
                    read_report('absent')
            with open_archive(path) as archive:
                self.assertEqual(export_report('r'),saved)
                self.assertEqual(sample_boundary('r',boundary,0,F(1,3)),sample)
                detached = read_report('r')
                detached['binding'].clear()
                self.assertEqual(export_report('r'),saved)
                archive.connection.execute("UPDATE reports SET payload='{}' WHERE report_id='r'")
                with self.assertRaises(ValueError):
                    read_report('r')
                with self.assertRaises(ValueError):
                    build_report('r','day')

    def test_offline_package_validation(self):
        with open_archive(':memory:'):
            prepare()
            payload = export_report('r')
        result = open_package(payload)
        self.assertEqual(result['measurements']['total_area'],F(12))
        self.assertEqual(reconcile_report(result).component_count,1)
        result['inputs'].clear()
        self.assertEqual(open_package(payload)['measurements']['total_area'],F(12))
        mutations = []
        raw = json.loads(payload)
        for field in ('inputs','measurements','components','receipt','binding'):
            bad = copy.deepcopy(raw)
            del bad['report'][field]
            mutations.append(bad)
        bad = copy.deepcopy(raw)
        del bad['report']['measurements']['areas']
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['package_version'] = 99
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['format'] = 99
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['components'][0]['boundaries'][0]['segments'][0]['sources'].pop()
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['components'][0]['boundaries'][0]['segments'][0]['sources'][0]['region_id'] = 'missing'
        mutations.append(bad)
        for pair in ([2,2],[1,0],[1,-1],[True,1]):
            bad = copy.deepcopy(raw)
            bad['report']['measurements']['total_area'] = {'q':pair}
            mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['measurements']['total_area'] = {'q':[13,1]}
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['measurements']['boundary'][0]['length_squared'][0] = {'q':[999,1]}
        mutations.append(bad)
        bad = copy.deepcopy(raw)
        bad['report']['measurements']['areas'][0]['component_id'] = 'missing'
        mutations.append(bad)
        for bad in mutations:
            with self.subTest(package=bad):
                with self.assertRaises(ValueError):
                    open_package(json.dumps(bad))
        with self.assertRaises(ValueError):
            open_package('{"package_version":1,"package_version":1,"report":{}}')
        with self.assertRaises(ValueError):
            open_package('{"package_version":NaN,"report":{}}')

    def test_planar_scope(self):
        with open_archive(':memory:'):
            put_region('A',[(0,0),(6,0),(6,1),(0,1)])
            put_region('B',[(5,0),(11,0),(11,1),(5,1)])
            seal_batch('day',[('A',1),('B',1)])
            report = build_report('r','day')
            self.assertEqual(report['measurements']['total_area'],F(11))
            self.assertEqual(len(report['components']),1)

def demo():
    root = Path(__file__).resolve().parents[1]
    raw = json.loads((root/'examples/day_input.json').read_text(encoding='utf-8'))
    expected = json.loads((root/'examples/day_expected.json').read_text(encoding='utf-8'))
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory)/'day.sqlite'
        with open_archive(path):
            members = []
            for source in raw['regions']:
                rings = [[tuple(F(*q) for q in point) for point in ring] for ring in source['rings']]
                members.append((source['region_id'],put_region(source['region_id'],rings[0],rings[1:])))
            seal_batch(raw['batch_id'],members)
            report = build_report(raw['report_id'],raw['batch_id'])
            boundary_id = index = None
            for c in report['components']:
                for b in c['boundaries']:
                    for i,s in enumerate(b['segments']):
                        if s['start'] == [F(0),F(0)] and s['end'] == [F(4),F(0)]:
                            boundary_id,index = b['boundary_id'],i
            sample = sample_boundary(raw['report_id'],boundary_id,index,F(1,3))
            payload = export_report(raw['report_id'])
            actual = {'area':str(report['measurements']['total_area']), 'components':len(report['components'])}
            downstream = {'point':[str(v) for v in sample['point']],
                          'parameters':[str(s['parameter']) for s in sample['sources']],
                          'offline_area':str(open_package(payload)['measurements']['total_area'])}
            if actual != expected['actual'] or downstream != expected['downstream']:
                raise AssertionError((actual,downstream))
            report['components'].clear()
            put_region('A',[(0,0),(8,0),(8,3),(0,3)])
        with open_archive(path):
            if export_report(raw['report_id']) != payload:
                raise AssertionError('historical package drift')
            if sample_boundary(raw['report_id'],boundary_id,index,F(1,3)) != sample:
                raise AssertionError('historical sample drift')
        print('POINTWISE_SCENARIO '+json.dumps({
            'case_id':'v1', 'input':raw, 'expected':expected['actual'], 'actual':actual,
            'downstream_expected':expected['downstream'], 'downstream_actual':downstream,
            'code_paths':['coverage/regions.py','coverage/sealing.py','coverage/coverage_union.py',
                          'coverage/reports.py','coverage/sampling.py','coverage/package_reader.py'],
            'oracle':'12 + 12 - 4 = 20; bottom interpolation (4/3,0); saved bytes equal after reopen'
        },sort_keys=True))

if __name__ == '__main__':
    if sys.argv[1:] == ['--demo']:
        demo()
    else:
        unittest.main()
