"""Read the durable request ledger without changing receipts or retrying work."""
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from sec_agent.adapters.local_records import _unpack


def summarize(directory):
    path = Path(directory).resolve() / 'records-v1.sqlite'
    counts = Counter()
    if path.exists():
        with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as db:
            db.execute('PRAGMA trusted_schema=OFF')
            for (raw,) in db.execute('SELECT value FROM records'):
                record = _unpack(json.loads(raw))
                if record.get('identity', {}).get('format') != 'scoped-rerank.v1':
                    raise ValueError('rerank_receipt_audit_unexpected_record')
                status = record.get('status')
                if status not in {'started', 'completed', 'failed_usage_unknown', 'not_submitted'}:
                    raise ValueError('rerank_receipt_audit_unknown_status')
                counts[status] += 1
    return {
        'scope':'durable_unique_request_records_in_this_run_directory_not_ranked_sample_count',
        'confirmed_submissions':counts['completed'] + counts['failed_usage_unknown'],
        'completed_responses':counts['completed'],
        'failed_usage_unknown':counts['failed_usage_unknown'],
        'submission_status_unknown':counts['started'],
        'not_submitted':counts['not_submitted'],
        'unknown_records_are_not_zero_cost':True,
    }
