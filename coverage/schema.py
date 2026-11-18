SCHEMA_VERSION = 1
TABLES = {
    'region_revisions': {'region_id', 'revision', 'geometry'},
    'region_heads': {'region_id', 'revision'},
    'batches': {'batch_id', 'status'},
    'batch_members': {'batch_id', 'region_id', 'revision'},
    'sealed_bindings': {'batch_id', 'signature'},
    'reports': {'report_id', 'batch_id', 'payload'},
    'receipts': {'report_id', 'batch_id', 'status'},
}

def verify_schema(connection):
    if connection.execute('PRAGMA user_version').fetchone()[0] != SCHEMA_VERSION:
        raise ValueError('incompatible archive version')
    for table, columns in TABLES.items():
        found = {row[1] for row in connection.execute('PRAGMA table_info(' + table + ')')}
        if found != columns:
            raise ValueError('incompatible archive schema: ' + table)
    if connection.execute('PRAGMA foreign_key_check').fetchone():
        raise ValueError('archive contains broken references')

def initialize_schema(connection):
    version = connection.execute('PRAGMA user_version').fetchone()[0]
    existing = connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall()
    if version or existing:
        verify_schema(connection)
        return
    statements = (
        'CREATE TABLE region_revisions(region_id TEXT NOT NULL, revision INTEGER NOT NULL CHECK(revision>0), geometry TEXT NOT NULL, PRIMARY KEY(region_id,revision))',
        'CREATE TABLE region_heads(region_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, FOREIGN KEY(region_id,revision) REFERENCES region_revisions(region_id,revision))',
        "CREATE TABLE batches(batch_id TEXT PRIMARY KEY, status TEXT NOT NULL CHECK(status='sealed'))",
        'CREATE TABLE batch_members(batch_id TEXT NOT NULL REFERENCES batches(batch_id), region_id TEXT NOT NULL, revision INTEGER NOT NULL, PRIMARY KEY(batch_id,region_id), FOREIGN KEY(region_id,revision) REFERENCES region_revisions(region_id,revision))',
        'CREATE TABLE sealed_bindings(batch_id TEXT PRIMARY KEY REFERENCES batches(batch_id), signature TEXT NOT NULL)',
        'CREATE TABLE reports(report_id TEXT PRIMARY KEY, batch_id TEXT NOT NULL REFERENCES batches(batch_id), payload TEXT NOT NULL)',
        "CREATE TABLE receipts(report_id TEXT PRIMARY KEY REFERENCES reports(report_id), batch_id TEXT NOT NULL REFERENCES batches(batch_id), status TEXT NOT NULL CHECK(status='published'))",
    )
    connection.execute('BEGIN')
    try:
        for statement in statements:
            connection.execute(statement)
        connection.execute('PRAGMA user_version=1')
        connection.commit()
    except BaseException:
        connection.rollback()
        raise
