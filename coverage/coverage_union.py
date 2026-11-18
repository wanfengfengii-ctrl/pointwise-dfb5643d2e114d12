from dataclasses import dataclass
from fractions import Fraction
from .arrangement import build_arrangement, trace_boundary_cycles
from .segments import AtomicSegment, SourceSpan
from .rings import identifier

@dataclass(frozen=True)
class BoundaryLoop:
    boundary_id: str
    segments: tuple

@dataclass(frozen=True)
class CoverageComponent:
    component_id: str
    boundaries: tuple

@dataclass(frozen=True)
class CoverageGeometry:
    components: tuple

def cycle_key(cycle):
    return tuple((s.start, s.end, s.sources) for s in cycle)

def canonical_cycle(cycle):
    candidates = [cycle[i:]+cycle[:i] for i in range(len(cycle))]
    return min(candidates, key=cycle_key)

def canonicalize_coverage(groups):
    groups = [tuple(sorted((canonical_cycle(c) for c in cycles), key=cycle_key)) for cycles in groups]
    groups.sort(key=lambda cycles: tuple(cycle_key(c) for c in cycles))
    components = []
    number = 0
    for ci, cycles in enumerate(groups):
        loops = []
        for cycle in cycles:
            loops.append(BoundaryLoop('b'+str(number), cycle))
            number += 1
        components.append(CoverageComponent('c'+str(ci), tuple(loops)))
    return CoverageGeometry(tuple(components))

def build_coverage(revisions):
    arrangement = build_arrangement(revisions)
    parent = list(range(len(arrangement.revisions)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    def join(indices):
        if indices:
            first = root(indices[0])
            for index in indices[1:]:
                parent[root(index)] = first
    for left, right in arrangement.sides:
        join(left.covering)
        join(right.covering)
        if left.covering and right.covering:
            join(left.covering + right.covering)
    groups = {}
    for segment, (left, right) in zip(arrangement.segments, arrangement.sides):
        if bool(left.covering) == bool(right.covering):
            continue
        covered = left.covering or right.covering
        oriented = segment if left.covering else segment.reversed()
        groups.setdefault(root(covered[0]), []).append(oriented)
    if len({root(i) for i in parent}) != len(groups):
        raise ValueError('component has no boundary')
    return canonicalize_coverage([trace_boundary_cycles(tuple(segments)) for segments in groups.values()])

def geometry_data(geometry):
    return [{'component_id': c.component_id, 'boundaries': [
        {'boundary_id': b.boundary_id, 'segments': [
            {'start': list(s.start), 'end': list(s.end), 'sources': [
                {'region_id': o.region_id, 'revision': o.revision, 'ring_index': o.ring_index,
                 'edge_index': o.edge_index, 't0': o.t0, 't1': o.t1} for o in s.sources]} for s in b.segments]}
        for b in c.boundaries]} for c in geometry.components]

def require_keys(value, keys):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ValueError('invalid object fields')

def rational_point(value):
    if not isinstance(value, list) or len(value) != 2 or any(type(v) is not Fraction for v in value):
        raise ValueError('invalid exact point')
    return tuple(value)

def geometry_from_data(data):
    if not isinstance(data, list) or not data:
        raise ValueError('missing components')
    components, component_ids, boundary_ids = [], set(), set()
    for c in data:
        require_keys(c, ('component_id', 'boundaries'))
        identifier(c['component_id'])
        if c['component_id'] in component_ids or not isinstance(c['boundaries'], list) or not c['boundaries']:
            raise ValueError('duplicate component or missing boundaries')
        component_ids.add(c['component_id'])
        loops = []
        for b in c['boundaries']:
            require_keys(b, ('boundary_id', 'segments'))
            identifier(b['boundary_id'])
            if b['boundary_id'] in boundary_ids or not isinstance(b['segments'], list) or len(b['segments']) < 3:
                raise ValueError('duplicate boundary or missing segments')
            boundary_ids.add(b['boundary_id'])
            segments = []
            for s in b['segments']:
                require_keys(s, ('start', 'end', 'sources'))
                a, z = rational_point(s['start']), rational_point(s['end'])
                if a == z or not isinstance(s['sources'], list) or not s['sources']:
                    raise ValueError('zero segment or missing sources')
                sources = []
                for o in s['sources']:
                    require_keys(o, ('region_id', 'revision', 'ring_index', 'edge_index', 't0', 't1'))
                    identifier(o['region_id'])
                    for key, lower in (('revision', 1), ('ring_index', 0), ('edge_index', 0)):
                        if type(o[key]) is not int or o[key] < lower:
                            raise ValueError('invalid source identity')
                    if any(type(o[k]) is not Fraction or not 0 <= o[k] <= 1 for k in ('t0', 't1')) or o['t0'] == o['t1']:
                        raise ValueError('invalid source interval')
                    sources.append(SourceSpan(**o))
                if sources != sorted(set(sources)):
                    raise ValueError('duplicate or unordered sources')
                segments.append(AtomicSegment(a, z, tuple(sources)))
            loops.append(BoundaryLoop(b['boundary_id'], tuple(segments)))
        components.append(CoverageComponent(c['component_id'], tuple(loops)))
    return CoverageGeometry(tuple(components))
