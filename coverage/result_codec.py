import json
from math import gcd
from fractions import Fraction
from .coverage_union import geometry_from_data, require_keys
from .region_validation import validate_region
from .rings import identifier

REPORT_FORMAT_VERSION = 1

def encode_fraction(value):
    if type(value) is not Fraction:
        raise ValueError('Fraction required')
    return [value.numerator, value.denominator]

def decode_fraction(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('rational pair required')
    n, d = value
    if type(n) is not int or type(d) is not int or d <= 0 or gcd(n, d) != 1:
        raise ValueError('noncanonical rational')
    return Fraction(n, d)

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result

def parse_json(payload):
    if not isinstance(payload, (str, bytes)):
        raise ValueError('JSON text required')
    try:
        return json.loads(payload, object_pairs_hook=unique_object, parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('invalid JSON') from exc

def pack(value):
    if type(value) is Fraction:
        return {'q': encode_fraction(value)}
    if isinstance(value, dict):
        return {k: pack(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [pack(v) for v in value]
    if type(value) in (str, int):
        return value
    raise ValueError('unsupported report value')

def unpack(value):
    if isinstance(value, dict):
        if 'q' in value:
            require_keys(value, ('q',))
            return decode_fraction(value['q'])
        return {k: unpack(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unpack(v) for v in value]
    if type(value) in (str, int):
        return value
    raise ValueError('unsupported JSON value')

def validate_report_structure(report):
    require_keys(report, ('format', 'report_id', 'batch_id', 'binding', 'inputs', 'components', 'measurements', 'receipt'))
    if type(report['format']) is not int or report['format'] != REPORT_FORMAT_VERSION:
        raise ValueError('unsupported report format')
    identifier(report['report_id'])
    identifier(report['batch_id'])
    if not isinstance(report['binding'], list) or not report['binding'] or not isinstance(report['inputs'], list):
        raise ValueError('missing fixed inputs')
    keys = []
    for member in report['binding']:
        require_keys(member, ('region_id', 'revision'))
        identifier(member['region_id'])
        if type(member['revision']) is not int or member['revision'] <= 0:
            raise ValueError('invalid revision')
        keys.append((member['region_id'], member['revision']))
    if keys != sorted(keys) or len({k[0] for k in keys}) != len(keys):
        raise ValueError('duplicate or unordered binding')
    snapshots = []
    for source in report['inputs']:
        require_keys(source, ('region_id', 'revision', 'rings'))
        identifier(source['region_id'])
        if type(source['revision']) is not int or source['revision'] <= 0:
            raise ValueError('invalid snapshot revision')
        rings = source['rings']
        if not isinstance(rings, list) or not rings:
            raise ValueError('missing input rings')
        for ring in rings:
            if not isinstance(ring, list):
                raise ValueError('invalid input ring')
            for p in ring:
                if not isinstance(p, list) or len(p) != 2 or any(type(v) is not Fraction for v in p):
                    raise ValueError('invalid input point')
        validated = validate_region(rings[0], rings[1:])
        if any(len(a) != len(b) for a, b in zip(validated.rings, rings)):
            raise ValueError('snapshot must omit closing duplicate')
        snapshots.append((source['region_id'], source['revision']))
    if snapshots != keys:
        raise ValueError('snapshot binding mismatch')
    geometry = geometry_from_data(report['components'])
    measurements = report['measurements']
    require_keys(measurements, ('areas', 'total_area', 'boundary'))
    if type(measurements['total_area']) is not Fraction or not isinstance(measurements['areas'], list) or not isinstance(measurements['boundary'], list):
        raise ValueError('missing measurement items')
    for item in measurements['areas']:
        require_keys(item, ('component_id', 'area'))
        if type(item['area']) is not Fraction:
            raise ValueError('invalid area')
    for item in measurements['boundary']:
        require_keys(item, ('boundary_id', 'length_squared'))
        if not isinstance(item['length_squared'], list) or any(type(v) is not Fraction for v in item['length_squared']):
            raise ValueError('invalid squared lengths')
    require_keys(report['receipt'], ('report_id', 'batch_id', 'status'))
    if report['receipt'] != {'report_id': report['report_id'], 'batch_id': report['batch_id'], 'status': 'published'}:
        raise ValueError('receipt binding mismatch')
    return geometry

def encode_report(report):
    validate_report_structure(report)
    return json.dumps(pack(report), sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def decode_report(payload):
    report = unpack(parse_json(payload))
    validate_report_structure(report)
    return report
