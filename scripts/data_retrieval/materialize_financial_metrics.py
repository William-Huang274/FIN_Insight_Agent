"""Precompute versioned financial histories in an unpublished SQL build.

No model calls. Reviewed input imports and security-basis profiles must already
be present. Publication and reader deployment are separate operations.
"""
import argparse
import json
from pathlib import Path
import sqlite3

from sec_agent.research_foundation.derived_financials import materialize
from sec_agent.research_foundation.reporting_periods import rebuild


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True)
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--scope', required=True, help='JSON entities list with entity_id fields')
    args = parser.parse_args()
    from datetime import date
    date.fromisoformat(args.as_of)
    path = Path(args.build).resolve(strict=True)
    if path.with_suffix(path.suffix + '.manifest.json').exists():
        raise ValueError('immutable_release_requires_build')
    scope = json.loads(Path(args.scope).read_text(encoding='utf-8'))
    ids = [item['entity_id'] for item in scope['entities']]
    if not ids or len(set(ids)) != len(ids):
        raise ValueError('nonempty_unique_entity_scope_required')
    with sqlite3.connect(path) as db:
        db.row_factory = sqlite3.Row
        found = {r[0] for r in db.execute('SELECT entity_id FROM company_cards')}
        if set(ids) - found:
            raise ValueError('scope_contains_unknown_entities')
        periods = rebuild(db)
    print(json.dumps({'period_observations': periods, **materialize(path, args.as_of, entity_ids=ids)}))


if __name__ == '__main__':
    main()
