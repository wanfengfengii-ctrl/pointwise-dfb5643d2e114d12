from .rings import identifier
from .batches import read_sealed_batch
from .coverage_union import build_coverage, geometry_data
from .areas import area_items, coverage_area
from .boundary_measure import boundary_measurements
from .publication import publication_binding, publish_report
from .database import current_archive
from .reconciliation import reconcile_report

def assemble_report(report_id, binding, geometry):
    report = {
        'format': 1, 'report_id': report_id, 'batch_id': binding.batch_id,
        'binding': [{'region_id': m.region_id, 'revision': m.revision} for m in binding.members],
        'inputs': [{'region_id': r.region_id, 'revision': r.revision,
                    'rings': [[list(p) for p in ring] for ring in r.rings]} for r in binding.revisions],
        'components': geometry_data(geometry),
        'measurements': {'areas': area_items(geometry), 'total_area': coverage_area(geometry),
                         'boundary': boundary_measurements(geometry)},
        'receipt': {'report_id': report_id, 'batch_id': binding.batch_id, 'status': 'published'},
    }
    reconcile_report(report)
    return report

def build_report(report_id, batch_id):
    from .reading import read_report
    identifier(report_id)
    binding = read_sealed_batch(batch_id)
    previous = publication_binding(report_id)
    if previous is not None:
        if previous != batch_id:
            raise ValueError('report identity is already bound')
        return read_report(report_id)
    current_archive().checkpoint('report.before_compute')
    geometry = build_coverage(binding.revisions)
    report = assemble_report(report_id, binding, geometry)
    publish_report(report)
    return read_report(report_id)
