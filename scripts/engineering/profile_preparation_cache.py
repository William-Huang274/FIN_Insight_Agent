"""Read-only bounded sample: storage reuse, not historical latency attribution."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from time import perf_counter

from sec_agent.research_foundation.source_verification_cache import (
    SourceVerificationCache, _file_identity, _receipt_rows,
)


def profile(path, limit):
    signature = _file_identity(path)
    with closing(sqlite3.connect(path.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        keys = tuple(r[0] for r in db.execute('SELECT key FROM receipts ORDER BY rowid DESC LIMIT ?', (limit,)))
    _receipt_rows.cache_clear()
    measurements = []
    for _ in range(2):
        start = perf_counter()
        rows = _receipt_rows(str(path.resolve()), signature, keys)
        if rows is None:
            raise ValueError('sample_exceeds_bounded_cache_or_changed')
        read_end = perf_counter()
        for row in rows:
            SourceVerificationCache._decode(row)
        measurements.append({'read_seconds': read_end-start,
                             'decode_seconds': perf_counter()-read_end,
                             'stored_bytes': sum(len(row[0]) for row in rows if row)})
    assert _file_identity(path) == signature
    return {'paid_calls': 0, 'read_only': True, 'sample_size': len(keys),
            'measurements': measurements, 'cache': _receipt_rows.cache_info()._asdict(),
            'scope': 'Current host sample; excludes full candidate reconstruction and authorization. Not attribution of prior recovery delay.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--limit', type=int, default=128)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not 1 <= args.limit <= 512:
        parser.error('limit must be 1..512')
    result = profile(args.cache, args.limit)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))
