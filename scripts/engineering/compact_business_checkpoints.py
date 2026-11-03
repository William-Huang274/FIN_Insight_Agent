"""Offline copy/verify of native checkpoint rows into shared object references.

Never alters the input database or changes checkpoint IDs, pending writes,
metadata, errors or billing. The caller must quiesce writers before switching
the verified output into service. Keep the original until recovery is checked.
"""
import argparse
import json
from pathlib import Path
import sqlite3

from sec_agent.agent_runtime.checkpoint_objects import ObjectSerializer


def compact(source, output, objects):
    source, output = Path(source).resolve(), Path(output).resolve()
    if output.exists() or source == output:
        raise ValueError('compact_requires_new_output')
    serializer = ObjectSerializer(objects)
    counts = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with sqlite3.connect(source.as_uri() + '?mode=ro', uri=True) as src, sqlite3.connect(output) as dst:
            src.execute('BEGIN')  # consistent read snapshot; original is untouched
            schema = src.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY type DESC").fetchall()
            for kind, name, sql in schema:
                if kind == 'table':
                    dst.execute(sql)
            for kind, name, sql in schema:
                if kind != 'table':
                    continue
                quoted = '"' + name.replace('"', '""') + '"'
                cursor = src.execute('SELECT * FROM ' + quoted)
                columns = [d[0] for d in cursor.description]
                payload = 'checkpoint' if name == 'checkpoints' else 'value' if name == 'writes' else None
                count = 0
                for row in cursor:
                    row = list(row)
                    if payload and 'type' in columns:
                        ti, pi = columns.index('type'), columns.index(payload)
                        original = serializer.loads_typed((row[ti], row[pi]))
                        row[ti], row[pi] = serializer.dumps_typed(original)
                        # Compare native serializations rather than Python ==
                        # (which is unreliable for NaN/array-like values).
                        if serializer.base.dumps_typed(serializer.loads_typed((row[ti], row[pi]))) != serializer.base.dumps_typed(original):
                            raise ValueError('compact_roundtrip_changed_value')
                    dst.execute('INSERT INTO ' + quoted + ' VALUES (' + ','.join('?' for _ in row) + ')', row)
                    count += 1
                counts[name] = count
            for kind, name, sql in schema:
                if kind != 'table':
                    dst.execute(sql)
            dst.commit()
            if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                raise ValueError('compact_integrity_failure')
    finally:
        serializer.close()
    return {'status': 'copied_all_rows_roundtrip_verified_original_unchanged', 'rows': counts,
            'source_bytes': source.stat().st_size, 'checkpoint_bytes': output.stat().st_size,
            'objects_bytes': Path(objects).stat().st_size}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'output', 'objects'):
        parser.add_argument('--' + name, required=True)
    print(json.dumps(compact(**vars(parser.parse_args()))))
