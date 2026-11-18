from .rings import identifier
from .members import normalize_members
from .sealing import prepare_seal, commit_seal
from .bindings import load_binding

def seal_batch(batch_id, members):
    identifier(batch_id)
    normalized = normalize_members(members)
    binding, replay = prepare_seal(batch_id, normalized)
    return commit_seal(binding, replay)

def read_sealed_batch(batch_id):
    identifier(batch_id)
    return load_binding(batch_id)
