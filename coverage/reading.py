from .rings import identifier
from .publication import load_publication
from .result_codec import decode_report
from .reconciliation import reconcile_report
from .coverage_union import geometry_from_data

def read_report(report_id):
    identifier(report_id)
    batch_id, payload, receipt = load_publication(report_id)
    report = decode_report(payload)
    if report['report_id'] != report_id or report['batch_id'] != batch_id or report['receipt'] != receipt:
        raise ValueError('stored publication identity mismatch')
    reconcile_report(report)
    return report

def read_fixed_geometry(report_id):
    return geometry_from_data(read_report(report_id)['components'])
