from fractions import Fraction
from .rings import signed_area2, point_location
from .priority_geometry import vertical_decomposition, split_convex, affine_integral
from .priority_fields import field_value

def subtract_coefficients(left, right):
    return tuple(a - b for a, b in zip(left, right))

def component_of_point(geometry, p):
    found = None
    for component in geometry.components:
        outer = None
        holes = []
        for boundary in component.boundaries:
            ring = tuple(s.start for s in boundary.segments)
            if signed_area2(ring) > 0:
                outer = ring
            else:
                holes.append(ring)
        if outer is None:
            raise ValueError('coverage component is missing its outer boundary')
        if point_location(p, outer) == 1 and all(point_location(p, ring) == -1 for ring in holes):
            if found is not None:
                raise ValueError('point belongs to two coverage components')
            found = component.component_id
    if found is None:
        raise ValueError('cell is outside every coverage component')
    return found

def compute_priority(geometry, binding, normalized_fields):
    revisions = binding.revisions
    regions = tuple(revision.rings for revision in revisions)
    coefficients = tuple(item[2] for item in normalized_fields)
    cells = []
    for polygon, covering, _witness in vertical_decomposition(regions):
        pieces = [polygon]
        for i, left in enumerate(covering):
            for right in covering[i+1:]:
                difference = subtract_coefficients(coefficients[left], coefficients[right])
                if difference[0] or difference[1]:
                    pieces = [cut for piece in pieces for cut in split_convex(piece, difference)]
        for piece in pieces:
            count = len(piece)
            centroid = (sum(p[0] for p in piece)/count, sum(p[1] for p in piece)/count)
            values = [field_value(coefficients[m], centroid) for m in covering]
            best = max(values)
            winners = tuple(m for m, value in zip(covering, values) if value == best)
            shared = coefficients[winners[0]]
            if any(coefficients[m] != shared for m in winners):
                raise ValueError('tied winners must share one affine function')
            ring = piece if signed_area2(piece) > 0 else tuple(reversed(piece))
            cells.append({'ring': ring, 'winners': winners, 'centroid': centroid,
                          'integral': affine_integral(shared, (ring,))})
    order = {component.component_id: index for index, component in enumerate(geometry.components)}
    for cell in cells:
        cell['component_id'] = component_of_point(geometry, cell['centroid'])
    cells.sort(key=lambda cell: (order[cell['component_id']], cell['ring'],
                                 tuple((revisions[m].region_id, revisions[m].revision) for m in cell['winners'])))
    items = []
    for index, cell in enumerate(cells):
        items.append({
            'cell_id': 'cell' + str(index),
            'component_id': cell['component_id'],
            'rings': [[list(p) for p in cell['ring']]],
            'winners': [{'region_id': revisions[m].region_id, 'revision': revisions[m].revision}
                        for m in cell['winners']],
            'integral': cell['integral'],
        })
    totals = {component.component_id: Fraction(0) for component in geometry.components}
    for cell in cells:
        totals[cell['component_id']] += cell['integral']
    return {
        'fields': [{'region_id': region_id, 'revision': revision, 'coefficients': list(coeffs)}
                   for region_id, revision, coeffs in normalized_fields],
        'cells': items,
        'integrals': [{'component_id': component.component_id, 'integral': totals[component.component_id]}
                      for component in geometry.components],
        'total_integral': sum(totals.values(), Fraction(0)),
    }
