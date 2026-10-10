"""Read-only content fingerprints of every public application table."""
import hashlib
import json
from sqlalchemy import text
from app.database import engine

with engine.connect() as connection:
    connection.execute(text('SET TRANSACTION READ ONLY'))
    tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")).scalars()
    snapshot = {}
    for name in tables:
        if name == 'spatial_ref_sys':
            continue
        rows = sorted(connection.execute(text(f'SELECT row_to_json(t)::text FROM "{name}" t')).scalars())
        snapshot[name] = {'count': len(rows), 'sha256': hashlib.sha256('\n'.join(rows).encode()).hexdigest()}
    print(json.dumps(snapshot, indent=2))
