import json
from dataclasses import dataclass
from .members import BatchMember, member_key
from .revisions import get_revision
from .database import current_archive

@dataclass(frozen=True)
class SealedBinding:
    batch_id: str
    members: tuple
    revisions: tuple

def signature(members):
    return json.dumps([member_key(m) for m in members], separators=(',', ':'))

def resolve_members(batch_id, members):
    return SealedBinding(batch_id, members, tuple(get_revision(m.region_id, m.revision) for m in members))

def bindings_equal(binding, members):
    return binding.members == members

def load_binding(batch_id):
    connection = current_archive().connection
    row = connection.execute('SELECT status FROM batches WHERE batch_id=?', (batch_id,)).fetchone()
    if row is None:
        raise KeyError(batch_id)
    seal = connection.execute('SELECT signature FROM sealed_bindings WHERE batch_id=?', (batch_id,)).fetchone()
    members = tuple(BatchMember(*r) for r in connection.execute('SELECT region_id,revision FROM batch_members WHERE batch_id=? ORDER BY region_id,revision', (batch_id,)))
    if row[0] != 'sealed' or not members or seal is None or seal[0] != signature(members):
        raise ValueError('corrupt sealed batch')
    return resolve_members(batch_id, members)

def insert_binding(connection, binding):
    connection.execute("INSERT INTO batches VALUES(?,'sealed')", (binding.batch_id,))
    connection.executemany('INSERT INTO batch_members VALUES(?,?,?)', [(binding.batch_id, m.region_id, m.revision) for m in binding.members])
    connection.execute('INSERT INTO sealed_bindings VALUES(?,?)', (binding.batch_id, signature(binding.members)))
