from .database import current_archive
from .result_codec import encode_report

def load_publication(report_id):
    connection = current_archive().connection
    row = connection.execute('SELECT batch_id,payload FROM reports WHERE report_id=?', (report_id,)).fetchone()
    receipt = connection.execute('SELECT batch_id,status FROM receipts WHERE report_id=?', (report_id,)).fetchone()
    if row is None and receipt is None:
        raise KeyError(report_id)
    if row is None or receipt is None or row[0] != receipt[0] or receipt[1] != 'published':
        raise ValueError('incomplete publication')
    return row[0], row[1], {'report_id': report_id, 'batch_id': receipt[0], 'status': receipt[1]}

def publication_binding(report_id):
    try:
        return load_publication(report_id)[0]
    except KeyError:
        return None

def publish_report(report):
    payload = encode_report(report)
    archive = current_archive()
    with archive.transaction() as connection:
        connection.execute('INSERT INTO reports VALUES(?,?,?)', (report['report_id'], report['batch_id'], payload))
        archive.checkpoint('report.after_payload')
        connection.execute("INSERT INTO receipts VALUES(?,?,'published')", (report['report_id'], report['batch_id']))
        archive.checkpoint('report.before_commit')
