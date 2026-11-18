import unittest
from fractions import Fraction as F
from coverage import open_archive, put_region, seal_batch, build_report
from coverage.revisions import get_current_revision, get_revision
from coverage.batches import read_sealed_batch

def box(a,b,c,d):
    return [(a,b),(c,b),(c,d),(a,d)]

class TestIntake(unittest.TestCase):
    def setUp(self):
        self.session = open_archive(':memory:')
        self.archive = self.session.__enter__()
        self.addCleanup(self.session.__exit__, None, None, None)

    def test_invalid_ring_atomic(self):
        self.assertEqual(put_region('A',box(0,0,6,6)), 1)
        invalid = [
            ([(0,0),(3,3),(0,3),(3,0)],()),
            (box(0,0,6,6),(box(5,5,7,7),)),
            (box(0,0,6,6),(box(0,1,2,2),)),
            (box(0,0,6,6),(box(1,1,5,5),box(2,2,3,3))),
            (box(0,0,6,6),(box(1,1,3,3),box(3,1,4,2))),
            ([(0,0),(6,0),(6,6),(4,6),(4,2),(2,2),(2,6),(0,6)],(box(1,3,5,4),)),
            ([(0,0),(2,0),(1,0),(2,2),(0,2)],()),
            ([(0,0),(2,0),(2,2),(1,0),(0,2)],()),
        ]
        for outer, holes in invalid:
            with self.subTest(outer=outer, holes=holes):
                with self.assertRaises(ValueError):
                    put_region('A',outer,holes)
                self.assertEqual(get_current_revision('A').revision,1)
        for value in (0.5, True, None):
            with self.assertRaises(ValueError):
                put_region('A',[(value,0),(2,0),(0,2)])
        with self.assertRaises(ValueError):
            put_region('A',[(0,0),(0,0),(1,1),(0,1)])
        self.assertEqual(put_region('A',list(reversed(box(0,0,6,6)))), 2)
        self.assertEqual(put_region('A',list(reversed(box(0,0,6,6)))), 3)
        self.assertEqual(get_revision('A',1).rings[0][0], (F(0),F(0)))
        self.assertEqual(self.archive.connection.execute('SELECT count(*) FROM region_revisions').fetchone()[0],3)

    def test_missing_revision_and_replay(self):
        put_region('A',box(0,0,1,1))
        with self.assertRaises(KeyError):
            seal_batch('day',[('A',1),('B',1)])
        for table in ('batches','batch_members','sealed_bindings'):
            self.assertEqual(self.archive.connection.execute('SELECT count(*) FROM '+table).fetchone()[0],0)
        put_region('B',box(2,0,3,1))
        binding = seal_batch('day',[('B',1),('A',1)])
        self.assertEqual(binding,seal_batch('day',[('A',1),('B',1)]))
        for members in ([], [('A',1),('A',1)], [('A',True)], [('B',1)]):
            with self.assertRaises(ValueError):
                seal_batch('day',members)
        put_region('A',box(0,0,2,2))
        self.assertEqual(read_sealed_batch('day').members[0].revision,1)
        self.assertEqual(build_report('old','day')['measurements']['total_area'], F(2))
        seal_batch('new',[('A',2)])
        self.assertEqual(build_report('new','new')['measurements']['total_area'], F(4))

    def test_write_failures_leave_no_candidate(self):
        put_region('A',box(0,0,1,1))
        def fail(name, connection):
            if name in ('revision.before_commit','batch.before_commit'):
                connection.execute('INSERT INTO table_that_does_not_exist VALUES(1)')
        self.archive.failure_hook = fail
        import sqlite3
        with self.assertRaises(sqlite3.OperationalError):
            put_region('A',box(0,0,2,2))
        with self.assertRaises(sqlite3.OperationalError):
            seal_batch('bad',[('A',1)])
        self.assertEqual(get_current_revision('A').revision,1)
        with self.assertRaises(KeyError):
            read_sealed_batch('bad')
        self.archive.failure_hook = None
        self.assertEqual(put_region('A',box(0,0,2,2)),2)
        seal_batch('bad',[('A',2)])

if __name__ == '__main__':
    unittest.main()
