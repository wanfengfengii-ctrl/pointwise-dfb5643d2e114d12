from .result_codec import parse_json, unpack, validate_report_structure
from .coverage_union import require_keys
from .reconciliation import reconcile_report

SUPPORTED_PACKAGE_VERSION = 1

def parse_package(payload):
    raw = parse_json(payload)
    require_keys(raw, ('package_version', 'report'))
    if type(raw['package_version']) is not int or raw['package_version'] != SUPPORTED_PACKAGE_VERSION:
        raise ValueError('unsupported package version')
    report = unpack(raw['report'])
    validate_report_structure(report)
    return report

def open_package(payload):
    report = parse_package(payload)
    reconcile_report(report)
    return report
