import sqlite3
import tempfile
import unittest
from pathlib import Path
from fractions import Fraction as F
from coverage import open_archive, put_region, seal_batch, build_report, read_report, export_report
from coverage.revisions import get_current_revision

class TestPublication(unittest.TestCase):
    def prepare(self):
        put_region('A',[(0,0),(2,0),(2,2),(0,2)])
        seal_batch('a',[('A',1)])
        seal_batch('b',[('A',1)])

    def test_report_receipt_rollback(self):
        with open_archive(':memory:') as archive:
            self.prepare()
            build_report('old','a')
            old = export_report('old')
            def fail(name, connection):
                if name == 'report.after_payload':
                    connection.execute('INSERT INTO missing_publication_table VALUES(1)')
            archive.failure_hook = fail
            with self.assertRaises(sqlite3.OperationalError):
                build_report('new','a')
            for table in ('reports','receipts'):
                self.assertEqual(archive.connection.execute('SELECT count(*) FROM '+table+' WHERE report_id=?',('new',)).fetchone()[0],0)
            self.assertEqual(export_report('old'),old)
            archive.failure_hook = None
            result = build_report('new','a')
            self.assertEqual(result,build_report('new','a'))
            with self.assertRaises(ValueError):
                build_report('new','b')
            with self.assertRaises(KeyError):
                build_report('new','missing')
            self.assertEqual(read_report('new'),result)

    def test_compute_failure(self):
        with open_archive(':memory:') as archive:
            self.prepare()
            def fail(name, connection):
                if name == 'report.before_compute':
                    raise ArithmeticError('quality calculation unavailable')
            archive.failure_hook = fail
            with self.assertRaises(ArithmeticError):
                build_report('r','a')
            self.assertEqual(archive.connection.execute('SELECT count(*) FROM reports').fetchone()[0],0)
            self.assertEqual(archive.connection.execute('SELECT count(*) FROM receipts').fetchone()[0],0)
            archive.failure_hook = None
            self.assertEqual(build_report('r','a')['measurements']['total_area'],F(4))

    def test_initialization_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'archive.sqlite'
            with open_archive(path) as archive:
                self.prepare()
                build_report('r','a')
                saved = export_report('r')
                archive.connection.execute('CREATE TABLE user_notes(note TEXT)')
                archive.connection.execute("INSERT INTO user_notes VALUES('keep me')")
            with open_archive(path) as archive:
                self.assertEqual(get_current_revision('A').revision,1)
                self.assertEqual(export_report('r'),saved)
                self.assertEqual(archive.connection.execute('SELECT note FROM user_notes').fetchone()[0],'keep me')
                archive.connection.execute('PRAGMA user_version=99')
            with self.assertRaises(ValueError):
                with open_archive(path):
                    pass

if __name__ == '__main__':
    unittest.main()
