import sqlite3
from contextlib import contextmanager
from contextvars import ContextVar
from .schema import initialize_schema

_session = ContextVar('coverage_archive', default=None)

class Archive:
    def __init__(self, path):
        self.connection = sqlite3.connect(path, isolation_level=None)
        self.failure_hook = None
        try:
            self.connection.execute('PRAGMA foreign_keys=ON')
            initialize_schema(self.connection)
        except BaseException:
            self.connection.close()
            raise

    @contextmanager
    def transaction(self):
        if self.connection.in_transaction:
            raise RuntimeError('nested write transaction')
        self.connection.execute('BEGIN IMMEDIATE')
        try:
            yield self.connection
            self.connection.commit()
        except BaseException:
            self.connection.rollback()
            raise

    def checkpoint(self, name):
        if self.failure_hook is not None:
            self.failure_hook(name, self.connection)

    def close(self):
        if self.connection.in_transaction:
            self.connection.rollback()
        self.connection.close()

def current_archive():
    archive = _session.get()
    if archive is None:
        raise RuntimeError('use with open_archive(path)')
    return archive

@contextmanager
def open_archive(path):
    archive = Archive(path)
    token = _session.set(archive)
    try:
        yield archive
    finally:
        _session.reset(token)
        archive.close()
