from dataclasses import dataclass
from .rings import identifier

@dataclass(frozen=True, order=True)
class BatchMember:
    region_id: str
    revision: int

def member_key(member):
    return member.region_id, member.revision

def normalize_members(members):
    result = []
    seen = set()
    try:
        for pair in members:
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise ValueError('member must be (region_id, revision)')
            region_id, revision = pair
            identifier(region_id)
            if type(revision) is not int or revision <= 0 or region_id in seen:
                raise ValueError('invalid revision or duplicate region')
            seen.add(region_id)
            result.append(BatchMember(region_id, revision))
    except TypeError as exc:
        raise ValueError('members must be iterable') from exc
    if not result:
        raise ValueError('empty batch')
    return tuple(sorted(result, key=member_key))
