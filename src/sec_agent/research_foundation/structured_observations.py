"""Selectors over already observed, digest-bound market records; no retrieval."""
import json
from decimal import Decimal
from hashlib import sha256


def market_fields(item):
    text = item.get('passage', '')
    if (item.get('source_kind') != 'market_observations' or not item.get('writer_citable')
            or sha256(text.encode()).hexdigest() != item.get('content_sha256')):
        return []
    try:
        lines = text.splitlines()
        metadata = json.loads(lines[0])
        rows = [json.loads(line, parse_float=Decimal) for line in lines[1:]]
        result = []
        for row in rows:
            for field in ('open', 'high', 'low', 'close', 'volume'):
                value = row.get(field)
                if isinstance(value, bool) or not isinstance(value, (int, Decimal)):
                    continue
                if not Decimal(value).is_finite():
                    continue
                result.append({'selector': {'start_utc': row['start_utc'], 'end_utc': row['end_utc'], 'field': field},
                    'value_decimal': str(value), 'context': {'metadata': metadata,
                        'exchange_time': row.get('exchange_time'), 'session': row.get('session'),
                        'notice': 'Observed bar field; not a guarantee of official daily close or complete session.'}})
        return result
    except (ValueError, KeyError, TypeError, IndexError):
        return []
