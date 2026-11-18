from .database import current_archive
from .bindings import resolve_members, load_binding, insert_binding, bindings_equal

def prepare_seal(batch_id, members):
    connection = current_archive().connection
    if connection.execute('SELECT 1 FROM batches WHERE batch_id=?', (batch_id,)).fetchone():
        binding = load_binding(batch_id)
        if not bindings_equal(binding, members):
            raise ValueError('batch identity is already bound')
        return binding, True
    return resolve_members(batch_id, members), False

def commit_seal(binding, replay=False):
    if replay:
        return binding
    archive = current_archive()
    with archive.transaction() as connection:
        insert_binding(connection, binding)
        archive.checkpoint('batch.before_commit')
    return load_binding(binding.batch_id)
