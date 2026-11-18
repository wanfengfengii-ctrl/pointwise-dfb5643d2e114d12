from .rings import identifier
from .region_validation import validate_region
from .revisions import append_revision

def put_region(region_id, outer, holes=()):
    identifier(region_id)
    geometry = validate_region(outer, holes)
    return append_revision(region_id, geometry)
