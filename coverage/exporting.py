import json
from .reading import read_report
from .result_codec import encode_report

PACKAGE_VERSION = 1

def make_package(report):
    return json.dumps({'package_version': PACKAGE_VERSION, 'report': json.loads(encode_report(report))},
                      sort_keys=True, separators=(',', ':'), ensure_ascii=False)

def export_report(report_id):
    return make_package(read_report(report_id))
