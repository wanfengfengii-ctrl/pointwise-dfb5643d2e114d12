from .rings import identifier
from .batches import read_sealed_batch
from .coverage_union import build_coverage
from .reports import assemble_report
from .publication import publication_binding, publish_report
from .database import current_archive
from .reconciliation import reconcile_report
from .priority_fields import normalize_fields
from .priority_cells import compute_priority

PRIORITY_FORMAT_VERSION = 2

def saved_field_tuples(report):
    return tuple((field['region_id'], field['revision'], tuple(field['coefficients']))
                 for field in report['priority']['fields'])

def build_priority_report(report_id, batch_id, fields):
    from .reading import read_report
    identifier(report_id)
    binding = read_sealed_batch(batch_id)
    normalized = normalize_fields(fields, binding)
    previous = publication_binding(report_id)
    if previous is not None:
        saved = read_report(report_id)
        if previous != batch_id or saved['format'] != PRIORITY_FORMAT_VERSION \
                or saved_field_tuples(saved) != normalized:
            raise ValueError('report identity is already bound')
        return saved
    current_archive().checkpoint('report.before_compute')
    geometry = build_coverage(binding.revisions)
    report = assemble_report(report_id, binding, geometry)
    report['format'] = PRIORITY_FORMAT_VERSION
    report['priority'] = compute_priority(geometry, binding, normalized)
    reconcile_report(report)
    publish_report(report)
    return read_report(report_id)
