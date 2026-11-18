import json
from fractions import Fraction
from dataclasses import dataclass
from .database import current_archive
from .rings import identifier
from .region_validation import validate_region

@dataclass(frozen=True)
class RegionRevision:
    region_id: str
    revision: int
    rings: tuple

def dump_rings(rings):
    return json.dumps([[[[v.numerator, v.denominator] for v in p] for p in ring] for ring in rings], separators=(',', ':'))

def load_rings(payload):
    try:
        raw = json.loads(payload)
        rings = tuple(tuple(tuple(Fraction(*q) for q in p) for p in ring) for ring in raw)
        region = validate_region(rings[0], rings[1:])
        return region.rings
    except (TypeError, IndexError, ZeroDivisionError, ValueError) as exc:
        raise ValueError('corrupt stored region') from exc

def append_revision(region_id, geometry):
    archive = current_archive()
    with archive.transaction() as connection:
        head = connection.execute('SELECT revision FROM region_heads WHERE region_id=?', (region_id,)).fetchone()
        revision = head[0] + 1 if head else 1
        connection.execute('INSERT INTO region_revisions VALUES(?,?,?)', (region_id, revision, dump_rings(geometry.rings)))
        connection.execute('INSERT INTO region_heads VALUES(?,?) ON CONFLICT(region_id) DO UPDATE SET revision=excluded.revision', (region_id, revision))
        archive.checkpoint('revision.before_commit')
    return revision

def get_revision(region_id, revision):
    identifier(region_id)
    if type(revision) is not int or revision <= 0:
        raise ValueError('positive integer revision required')
    row = current_archive().connection.execute('SELECT geometry FROM region_revisions WHERE region_id=? AND revision=?', (region_id, revision)).fetchone()
    if row is None:
        raise KeyError((region_id, revision))
    return RegionRevision(region_id, revision, load_rings(row[0]))

def get_current_revision(region_id):
    identifier(region_id)
    row = current_archive().connection.execute('SELECT revision FROM region_heads WHERE region_id=?', (region_id,)).fetchone()
    if row is None:
        raise KeyError(region_id)
    return get_revision(region_id, row[0])
