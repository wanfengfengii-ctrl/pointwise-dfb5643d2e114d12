from fractions import Fraction
from .coverage_union import require_keys
from .region_validation import validate_region
from .rings import identifier, point_location, ring_edges, signed_area2
from .intersections import segment_intersections, interpolate
from .areas import component_area
from .priority_fields import field_value
from .priority_geometry import vertical_decomposition, affine_integral, region_moments

def validate_priority_structure(report, geometry):
    priority = report['priority']
    require_keys(priority, ('fields', 'cells', 'integrals', 'total_integral'))
    binding = report['binding']
    fields = priority['fields']
    if not isinstance(fields, list) or len(fields) != len(binding):
        raise ValueError('priority fields must follow the binding')
    for field, member in zip(fields, binding):
        require_keys(field, ('region_id', 'revision', 'coefficients'))
        if field['region_id'] != member['region_id'] or field['revision'] != member['revision']:
            raise ValueError('priority fields must follow the binding')
        coefficients = field['coefficients']
        if not isinstance(coefficients, list) or len(coefficients) != 3 \
                or any(type(v) is not Fraction for v in coefficients):
            raise ValueError('coefficients must be three rationals')
    component_ids = [component.component_id for component in geometry.components]
    cells = priority['cells']
    if not isinstance(cells, list) or not cells:
        raise ValueError('priority cells must be a nonempty list')
    binding_keys = {(member['region_id'], member['revision']) for member in binding}
    seen = set()
    for cell in cells:
        require_keys(cell, ('cell_id', 'component_id', 'rings', 'winners', 'integral'))
        identifier(cell['cell_id'])
        if cell['cell_id'] in seen:
            raise ValueError('duplicate cell identity')
        seen.add(cell['cell_id'])
        identifier(cell['component_id'])
        if cell['component_id'] not in component_ids:
            raise ValueError('cell references an unknown component')
        rings = cell['rings']
        if not isinstance(rings, list) or not rings:
            raise ValueError('cell requires rings')
        for ring in rings:
            if not isinstance(ring, list):
                raise ValueError('invalid cell ring')
            for p in ring:
                if not isinstance(p, list) or len(p) != 2 or any(type(v) is not Fraction for v in p):
                    raise ValueError('invalid cell point')
        validated = validate_region(rings[0], rings[1:])
        if any(len(a) != len(b) for a, b in zip(validated.rings, rings)):
            raise ValueError('cell rings must omit the closing duplicate')
        winners = cell['winners']
        if not isinstance(winners, list) or not winners:
            raise ValueError('cell winners must be a nonempty list')
        keys = []
        for winner in winners:
            require_keys(winner, ('region_id', 'revision'))
            identifier(winner['region_id'])
            if type(winner['revision']) is not int or winner['revision'] <= 0:
                raise ValueError('invalid winner revision')
            keys.append((winner['region_id'], winner['revision']))
        if keys != sorted(keys) or len(set(keys)) != len(keys):
            raise ValueError('cell winners must be sorted and unique')
        if any(key not in binding_keys for key in keys):
            raise ValueError('cell winner is not a batch member')
        if type(cell['integral']) is not Fraction:
            raise ValueError('cell integral must be a Fraction')
    integrals = priority['integrals']
    if not isinstance(integrals, list) or len(integrals) != len(component_ids):
        raise ValueError('priority integrals must follow the components')
    for item, component_id in zip(integrals, component_ids):
        require_keys(item, ('component_id', 'integral'))
        if item['component_id'] != component_id or type(item['integral']) is not Fraction:
            raise ValueError('priority integrals must follow the components')
    if type(priority['total_integral']) is not Fraction:
        raise ValueError('total integral must be a Fraction')

def cell_rings(cell):
    return tuple(tuple(tuple(p) for p in ring) for ring in cell['rings'])

def component_regions(geometry):
    regions = {}
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
        regions[component.component_id] = (outer,) + tuple(holes)
    return regions

def strictly_inside(p, rings):
    return point_location(p, rings[0]) == 1 and all(point_location(p, hole) == -1 for hole in rings[1:])

def bounding_box(rings):
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    return min(xs), min(ys), max(xs), max(ys)

def clip_line_to_box(coefficients, box):
    a, b, c = coefficients
    x0, y0, x1, y1 = box
    points = set()
    if b:
        for x in (x0, x1):
            y = -(a*x + c)/b
            if y0 <= y <= y1:
                points.add((x, y))
    if a:
        for y in (y0, y1):
            x = -(b*y + c)/a
            if x0 <= x <= x1:
                points.add((x, y))
    if len(points) < 2:
        return None
    ordered = sorted(points)
    return ordered[0], ordered[-1]

def interior_edge_intervals(a, b, rings):
    cuts = {Fraction(0), Fraction(1)}
    for ring in rings:
        for c, d in ring_edges(ring):
            for hit in segment_intersections(a, b, c, d):
                cuts.add(hit.first_parameter)
    ordered = sorted(cuts)
    return [(t0, t1) for t0, t1 in zip(ordered, ordered[1:])
            if strictly_inside(interpolate(a, b, (t0 + t1)/2), rings)]

def reconcile_priority(report, geometry):
    priority = report['priority']
    fields = {(f['region_id'], f['revision']): tuple(f['coefficients']) for f in priority['fields']}
    binding_keys = [(member['region_id'], member['revision']) for member in report['binding']]
    member_rings = {}
    for source in report['inputs']:
        member_rings[(source['region_id'], source['revision'])] = tuple(
            tuple(tuple(p) for p in ring) for ring in source['rings'])
    cells = priority['cells']
    prepared = []
    for cell in cells:
        winners = tuple((w['region_id'], w['revision']) for w in cell['winners'])
        functions = {fields[key] for key in winners}
        if len(functions) != 1:
            raise ValueError('tied winners must share one affine function')
        shared = functions.pop()
        rings = cell_rings(cell)
        if region_moments(rings)[0] <= 0:
            raise ValueError('cell area must be positive')
        if affine_integral(shared, rings) != cell['integral']:
            raise ValueError('cell integral does not match its winner function')
        prepared.append((rings, winners, shared))
    regions_by_component = component_regions(geometry)
    pseudo_regions = [rings for rings, _winners, _shared in prepared]
    pseudo_regions += [regions_by_component[component.component_id] for component in geometry.components]
    component_slot = {component.component_id: len(cells) + i
                      for i, component in enumerate(geometry.components)}
    for _polygon, covering, _witness in vertical_decomposition(pseudo_regions):
        covered_cells = [k for k in covering if k < len(cells)]
        if len(covered_cells) > 1:
            raise ValueError('cells overlap with positive area')
        for k in covered_cells:
            if component_slot[cells[k]['component_id']] not in covering:
                raise ValueError('cell escapes its coverage component')
    area_sums = {component.component_id: Fraction(0) for component in geometry.components}
    for k, cell in enumerate(cells):
        area_sums[cell['component_id']] += region_moments(prepared[k][0])[0]
    for component in geometry.components:
        if area_sums[component.component_id] != component_area(component):
            raise ValueError('cells do not cover their coverage component')
    for k, cell in enumerate(cells):
        rings, winners, shared = prepared[k]
        winner_set = set(winners)
        box = bounding_box(rings)
        extra = []
        for key in binding_keys:
            difference = tuple(a - b for a, b in zip(fields[key], shared))
            if difference[0] or difference[1]:
                segment = clip_line_to_box(difference, box)
                if segment is not None:
                    extra.append(segment)
        regions = [rings] + [member_rings[key] for key in binding_keys]
        for _polygon, covering, witness in vertical_decomposition(regions, extra):
            if 0 not in covering:
                continue
            covered = {binding_keys[m - 1] for m in covering if m >= 1}
            for key in winners:
                if key not in covered:
                    raise ValueError('winner is not fixed over the cell interior')
            for key in covered:
                function = fields[key]
                if function == shared:
                    if key not in winner_set:
                        raise ValueError('a tied member is missing from the cell winners')
                elif field_value(function, witness) >= field_value(shared, witness):
                    raise ValueError('a member exceeds the cell winners')
        for key in binding_keys:
            function = fields[key]
            for ring in member_rings[key]:
                for vertex in ring:
                    if strictly_inside(vertex, rings):
                        gap = field_value(function, vertex) - field_value(shared, vertex)
                        if gap > 0 or (gap == 0 and key not in winner_set):
                            raise ValueError('member vertex changes the cell winners')
            if key in winner_set:
                continue
            for ring in member_rings[key]:
                for a, b in ring_edges(ring):
                    for t0, t1 in interior_edge_intervals(a, b, rings):
                        mid = interpolate(a, b, (t0 + t1)/2)
                        if field_value(function, mid) >= field_value(shared, mid):
                            raise ValueError('member edge ties or exceeds the cell winners')
    totals = {component.component_id: Fraction(0) for component in geometry.components}
    for cell in cells:
        totals[cell['component_id']] += cell['integral']
    for item in priority['integrals']:
        if item['integral'] != totals[item['component_id']]:
            raise ValueError('component integral does not match its cells')
    if priority['total_integral'] != sum(totals.values(), Fraction(0)):
        raise ValueError('total integral does not match the components')
