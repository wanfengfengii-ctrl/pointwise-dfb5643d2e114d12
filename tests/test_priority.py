"""Independent hand-computed priority cases and offline reconciliation checks."""
import copy
import json
import sqlite3
import tempfile
import unittest
from fractions import Fraction as F
from pathlib import Path

import coverage as api
from coverage.intersections import point_on_segment, parameter_on_segment


def box(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


REGIONS_P1 = [('A', box(0, 0, 2, 1), []), ('B', box(1, 0, 3, 1), [])]
FIELDS_P1 = {'A': [1, 0, 0], 'B': [-1, 0, 2]}
REGIONS_P2 = [('A', box(0, 0, 3, 3), [box(1, 1, 2, 2)]),
              ('B', box(1, 1, 2, 2), []), ('C', box(1, 1, 2, 2), [])]
FIELDS_P2 = {'A': [0, 0, 1], 'B': [0, 0, 5], 'C': [0, 0, 5]}
REGIONS_P3 = [('A', box(0, 0, 1, 1), []), ('B', box(2, 0, 3, 1), [])]
FIELDS_P3 = {'A': [0, 0, 1], 'B': [0, 0, 2]}


def prepare(regions):
    members = [(name, api.put_region(name, outer, holes)) for name, outer, holes in regions]
    api.seal_batch('day', members)


def cell_area(rings):
    def unsigned(ring):
        return abs(sum((p[0]*q[1] - p[1]*q[0]
                        for p, q in zip(ring, ring[1:] + ring[:1])), F(0))) / 2
    return unsigned(rings[0]) - sum((unsigned(hole) for hole in rings[1:]), F(0))


def boundary_requests(report, point):
    point = tuple(F(v) for v in point)
    found = []
    for component in report['components']:
        for boundary in component['boundaries']:
            for index, segment in enumerate(boundary['segments']):
                a, b = tuple(segment['start']), tuple(segment['end'])
                if point_on_segment(point, a, b):
                    found.append((boundary['boundary_id'], index,
                                  parameter_on_segment(point, a, b)))
    return found


class TestPriorityHandover(unittest.TestCase):
    def check_case(self, report, fields, total, component_integrals, winner_areas, samples):
        self.assertEqual(report['format'], 2)
        priority = report['priority']
        self.assertEqual(priority['total_integral'], total)
        self.assertEqual(sorted(item['integral'] for item in priority['integrals']),
                         sorted(component_integrals))
        self.assertEqual([item['component_id'] for item in priority['integrals']],
                         [c['component_id'] for c in report['components']])
        expected_fields = [dict(region_id=m['region_id'], revision=m['revision'],
                                coefficients=[F(v) for v in fields[m['region_id']]])
                           for m in report['binding']]
        self.assertEqual(priority['fields'], expected_fields)
        areas, sums, ids = {}, {}, set()
        for cell in priority['cells']:
            self.assertNotIn(cell['cell_id'], ids)
            ids.add(cell['cell_id'])
            names = tuple(w['region_id'] for w in cell['winners'])
            self.assertEqual(names, tuple(sorted(set(names))))
            for winner in cell['winners']:
                self.assertIn(winner, report['binding'])
            area = cell_area(cell['rings'])
            self.assertGreater(area, 0)
            areas[names] = areas.get(names, F(0)) + area
            sums[cell['component_id']] = sums.get(cell['component_id'], F(0)) + cell['integral']
        self.assertEqual(areas, winner_areas)
        self.assertEqual(sums, {i['component_id']: i['integral'] for i in priority['integrals']})
        for point, value, names in samples:
            requests = boundary_requests(report, point)
            self.assertTrue(requests)
            for boundary_id, index, t in requests:
                result = api.sample_priority(report['report_id'], boundary_id, index, t)
                self.assertEqual(result, dict(
                    point=[F(v) for v in point], value=value,
                    winners=[dict(region_id=n, revision=1) for n in names]))

    def test_offset_reversal_with_negative(self):
        # A=[0,2]x[0,1] f=x; B=[1,3]x[0,1] f=2-x. A wins on [0,2] (integral 2),
        # B wins on [2,3] (integral -1/2); total 3/2; negative reading survives.
        with api.open_archive(':memory:'):
            prepare(REGIONS_P1)
            normal = api.build_report('plain', 'day')
            report = api.build_priority_report('prio', 'day', copy.deepcopy(FIELDS_P1))
            for key in ('binding', 'inputs', 'components', 'measurements'):
                self.assertEqual(report[key], normal[key])
            self.check_case(report, FIELDS_P1, F(3, 2), [F(3, 2)],
                            {('A',): F(2), ('B',): F(1)},
                            [((F(1, 2), 0), F(1, 2), ('A',)),
                             ((1, 0), F(1), ('A', 'B')),
                             ((F(3, 2), 0), F(3, 2), ('A',)),
                             ((F(5, 2), 0), F(-1, 2), ('B',)),
                             ((3, F(1, 2)), F(-1), ('B',))])
            self.assertEqual(api.read_report('prio'), report)
            self.assertEqual(api.open_package(api.export_report('prio')), report)

    def test_hole_fill_identical_tie(self):
        # A=[0,3]^2 minus hole (1,2)^2 f=1; B=C=[1,2]^2 f=5 fill the hole.
        # Filled square winners B,C counted once; total 8*1 + 1*5 = 13.
        with api.open_archive(':memory:'):
            prepare(REGIONS_P2)
            self.assertEqual(api.build_report('plain', 'day')['measurements']['total_area'], F(9))
            report = api.build_priority_report('prio', 'day', FIELDS_P2)
            self.check_case(report, FIELDS_P2, F(13), [F(13)],
                            {('A',): F(8), ('B', 'C'): F(1)},
                            [((0, 0), F(1), ('A',)), ((3, 0), F(1), ('A',)),
                             ((3, 3), F(1), ('A',)), ((0, 3), F(1), ('A',)),
                             ((1, 0), F(1), ('A',))])

    def test_two_components(self):
        # Disjoint unit squares f=1 and f=2 stay separate components.
        with api.open_archive(':memory:'):
            prepare(REGIONS_P3)
            report = api.build_priority_report('prio', 'day', FIELDS_P3)
            self.assertEqual(len(report['components']), 2)
            self.check_case(report, FIELDS_P3, F(3), [F(1), F(2)],
                            {('A',): F(1), ('B',): F(1)},
                            [((0, 0), F(1), ('A',)), ((1, 1), F(1), ('A',)),
                             ((2, 0), F(2), ('B',)), ((3, 1), F(2), ('B',))])

    def test_replay_and_kind_conflicts(self):
        with api.open_archive(':memory:'):
            prepare(REGIONS_P1)
            api.build_report('plain', 'day')
            report = api.build_priority_report('prio', 'day', FIELDS_P1)
            replay = {'B': (-1, 0, 2), 'A': (1, 0, 0)}
            self.assertEqual(api.build_priority_report('prio', 'day', replay), report)
            with self.assertRaises(ValueError):
                api.build_priority_report('prio', 'day', {'A': [1, 0, 0], 'B': [-1, 0, 3]})
            with self.assertRaises(ValueError):
                api.build_report('prio', 'day')
            with self.assertRaises(ValueError):
                api.build_priority_report('plain', 'day', FIELDS_P1)
            api.seal_batch('other', [('A', 1), ('B', 1)])
            with self.assertRaises(ValueError):
                api.build_priority_report('prio', 'other', FIELDS_P1)
            request = boundary_requests(report, (1, 0))[0]
            self.assertEqual(api.sample_boundary('prio', *request)['point'], [F(1), F(0)])
            with self.assertRaises(ValueError):
                api.sample_priority('plain', *request)
            for bad in ({'A': [1, 0, 0]}, {'A': [1, 0, 0], 'B': [-1, 0, 2], 'C': [0, 0, 0]},
                        {'A': [1, 0], 'B': [-1, 0, 2]}, {'A': [1.0, 0, 0], 'B': [-1, 0, 2]},
                        {'A': [True, 0, 0], 'B': [-1, 0, 2]}, None, ['not-a-dict']):
                with self.subTest(fields=bad), self.assertRaises(ValueError):
                    api.build_priority_report('bad', 'day', bad)
            with self.assertRaises(KeyError):
                api.build_priority_report('absent', 'missing', FIELDS_P1)

    def test_failure_atomicity(self):
        with api.open_archive(':memory:') as archive:
            prepare(REGIONS_P1)
            api.build_report('plain', 'day')
            old = api.export_report('plain')

            def block_commit(name, connection):
                if name == 'report.before_commit':
                    raise RuntimeError('blocked commit')
            archive.failure_hook = block_commit
            with self.assertRaises(RuntimeError):
                api.build_priority_report('atomic', 'day', FIELDS_P1)
            archive.failure_hook = None
            for table in ('reports', 'receipts'):
                self.assertEqual(archive.connection.execute(
                    'SELECT count(*) FROM ' + table + ' WHERE report_id=?', ('atomic',)).fetchone()[0], 0)
            self.assertEqual(api.export_report('plain'), old)
            report = api.build_priority_report('atomic', 'day', FIELDS_P1)
            self.assertEqual(report['priority']['total_integral'], F(3, 2))

            def corrupt_sql(name, connection):
                if name == 'report.after_payload':
                    connection.execute('INSERT INTO missing_priority_table VALUES(1)')
            archive.failure_hook = corrupt_sql
            with self.assertRaises(sqlite3.OperationalError):
                api.build_priority_report('sql-fail', 'day', FIELDS_P1)
            archive.failure_hook = None
            self.assertEqual(archive.connection.execute(
                "SELECT count(*) FROM reports WHERE report_id='sql-fail'").fetchone()[0], 0)
            self.assertEqual(api.build_priority_report('sql-fail', 'day', FIELDS_P1),
                             api.read_report('sql-fail'))

    def test_fixed_delivery_reopen(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'handover.sqlite'
            with api.open_archive(path):
                prepare(REGIONS_P1)
                api.build_report('plain', 'day')
                plain = api.export_report('plain')
                report = api.build_priority_report('prio', 'day', FIELDS_P1)
                saved = api.export_report('prio')
                request = boundary_requests(report, (1, 0))[0]
                reading = api.sample_priority('prio', *request)
                snapshot = copy.deepcopy(reading)
                report['priority']['cells'].clear()
                report['inputs'].clear()
                reading['winners'].clear()
                api.put_region('A', box(0, 0, 9, 9))
            with api.open_archive(path):
                self.assertEqual(api.export_report('plain'), plain)
                self.assertEqual(api.export_report('prio'), saved)
                self.assertEqual(api.sample_priority('prio', *request), snapshot)
                self.assertEqual(api.open_package(saved), api.read_report('prio'))

    def test_offline_reconciliation_rejects(self):
        with api.open_archive(':memory:'):
            prepare(REGIONS_P1)
            api.build_priority_report('prio', 'day', FIELDS_P1)
            raw = json.loads(api.export_report('prio'))
            priority = raw['report']['priority']
            mutations = []

            def bump(pair):
                pair[0] += pair[1]

            bad = copy.deepcopy(raw)
            bump(bad['report']['priority']['total_integral']['q'])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            bump(bad['report']['priority']['integrals'][0]['integral']['q'])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            bump(bad['report']['priority']['cells'][0]['integral']['q'])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            twin = copy.deepcopy(bad['report']['priority']['cells'][0])
            twin['cell_id'] += '.twin'
            bad['report']['priority']['cells'].append(twin)
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            bad['report']['priority']['cells'].pop(0)
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            cells = bad['report']['priority']['cells']
            first, second = next((i, j) for i in range(len(cells)) for j in range(i + 1, len(cells))
                                 if cells[i]['integral'] != cells[j]['integral'])
            cells[first]['integral'], cells[second]['integral'] = (
                cells[second]['integral'], cells[first]['integral'])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            a_only = next(cell for cell in bad['report']['priority']['cells']
                          if [w['region_id'] for w in cell['winners']] == ['A'])
            a_only['winners'] = [dict(region_id='B', revision=1)]
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            field_a = next(f for f in bad['report']['priority']['fields'] if f['region_id'] == 'A')
            bump(field_a['coefficients'][0]['q'])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            del bad['report']['priority']['fields']
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            del bad['report']['priority']['cells']
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            ring = bad['report']['priority']['cells'][0]['rings'][0]
            ring.append(ring[0])
            mutations.append(bad)
            bad = copy.deepcopy(raw)
            bad['report']['priority']['cells'][0]['winners'] = [dict(region_id='Z', revision=1)]
            mutations.append(bad)
            for bad in mutations:
                with self.subTest(package=bad), self.assertRaises(ValueError):
                    api.open_package(json.dumps(bad))
            self.assertEqual(api.open_package(json.dumps(raw)), api.read_report('prio'))

        with api.open_archive(':memory:'):
            prepare(REGIONS_P2)
            api.build_priority_report('tied', 'day', FIELDS_P2)
            raw2 = json.loads(api.export_report('tied'))
            tied = next(cell for cell in raw2['report']['priority']['cells']
                        if len(cell['winners']) == 2)
            bad = copy.deepcopy(raw2)
            next(cell for cell in bad['report']['priority']['cells']
                 if len(cell['winners']) == 2)['winners'].pop()
            with self.assertRaises(ValueError):
                api.open_package(json.dumps(bad))
            bad = copy.deepcopy(raw2)
            next(cell for cell in bad['report']['priority']['cells']
                 if len(cell['winners']) == 2)['winners'].reverse()
            with self.assertRaises(ValueError):
                api.open_package(json.dumps(bad))
            self.assertEqual(tied['winners'], [dict(region_id='B', revision=1),
                                               dict(region_id='C', revision=1)])

        with api.open_archive(':memory:'):
            prepare(REGIONS_P3)
            api.build_priority_report('pair', 'day', FIELDS_P3)
            raw3 = json.loads(api.export_report('pair'))
            other = raw3['report']['components'][1]['component_id']
            bad = copy.deepcopy(raw3)
            bad['report']['priority']['cells'][0]['component_id'] = other \
                if bad['report']['priority']['cells'][0]['component_id'] != other else \
                raw3['report']['components'][0]['component_id']
            with self.assertRaises(ValueError):
                api.open_package(json.dumps(bad))
            bad = copy.deepcopy(raw3)
            bad['report']['priority']['cells'][0]['component_id'] = 'c99'
            with self.assertRaises(ValueError):
                api.open_package(json.dumps(bad))
            self.assertEqual(api.open_package(json.dumps(raw3)), api.read_report('pair'))


if __name__ == '__main__':
    unittest.main()
