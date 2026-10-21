"""Freeze all source identities and classify complete-source intake readiness.

Read-only; no provider, index build, source fetching or organization publication.
Unrecoverable sources remain in the denominator with explicit reasons.
"""
import argparse
from collections import Counter
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from retrieval.library_source_bundle import recover_source
from retrieval.library_vectors import digest


def audit(library, output):
    library, output = Path(library).resolve(), Path(output).resolve()
    if output == library or output.is_relative_to(library.parent):
        raise ValueError('audit_output_must_not_change_source_directory')
    # Exclusive creation prevents accidental replacement of a prior scope decision.
    with output.open('x', encoding='utf8') as stream:
        json.dump({'status':'incomplete','scope':'all records; no silent exclusion'}, stream)
    library_sha = digest(library)
    rows = []
    with closing(sqlite3.connect(library.as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        for saved in db.execute('SELECT * FROM sources ORDER BY id'):
            source = dict(saved)
            metadata = json.loads(source['metadata'])
            row = {key:source[key] for key in ('id','title','url','digest','access_state','published_at','vintage')}
            row.update(category=metadata.get('category','unknown'), parser=metadata.get('parser'),
                       period_end=metadata.get('period_end'), document_coverage=metadata.get('document_coverage'),
                       parse_revision=metadata.get('parse_revision'), known_at=metadata.get('known_at'))
            if source['access_state'] != 'readable':
                row.update(intake_status='source_not_currently_readable', reason=source['access_state'])
            else:
                parents = [dict(p) for p in db.execute('SELECT * FROM passages WHERE source_id=?',(source['id'],))]
                row['parents'] = len(parents)
                row['chunks'] = db.execute('SELECT count(*) FROM retrieval_chunks WHERE source_id=?',(source['id'],)).fetchone()[0]
                try:
                    text, _ = recover_source(source, parents)
                    row.update(intake_status='parsed_text_recoverable', parsed_characters=len(text))
                except (ValueError, KeyError, TypeError) as exc:
                    row.update(intake_status='requires_adapter_or_source_repair', reason=str(exc))
            rows.append(row)
    unchanged = digest(library) == library_sha
    report = dict(status='scope_inventory_complete' if unchanged else 'source_changed',
                  library_sha256=library_sha, sources=rows, source_count=len(rows),
                  access_states=dict(Counter(r['access_state'] for r in rows)),
                  intake_statuses=dict(Counter(r['intake_status'] for r in rows)),
                  repair_reasons=dict(Counter(r['reason'] for r in rows if r['intake_status']=='requires_adapter_or_source_repair')),
                  provider_calls=0, organization_publication_verified=False,
                  vector_compatibility_verified=False, full_scope_retrieval_accepted=False)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    if not unchanged:
        raise ValueError('source_library_changed_during_inventory')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.library,args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},ensure_ascii=False))


if __name__=='__main__': main()
