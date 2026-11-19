"""Validate offline candidates or import an independently reviewed job."""
import argparse
import json
from pathlib import Path
import sqlite3
from sec_agent.research_foundation.relationship_extraction import prepare_job, import_job


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--job',type=Path,required=True)
    parser.add_argument('--review',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    path=args.library.resolve()
    if args.review and path.with_suffix(path.suffix+'.manifest.json').exists():
        raise ValueError('immutable_release_cannot_be_modified')
    with sqlite3.connect(path.as_uri()+('?mode=rw' if args.review else '?mode=ro'),uri=True) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        job=json.loads(args.job.read_text(encoding='utf8'))
        result=(import_job(db,job,json.loads(args.review.read_text(encoding='utf8')))
                if args.review else prepare_job(db,job))
    if args.output: args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'errors':result.get('errors',result.get('mechanical_errors',[])),
                      'job_digest':result.get('job_digest'),
                      'relations':len(result['relations']) if isinstance(result['relations'],list) else result['relations'],
                      'disclosures':len(result['disclosures']) if isinstance(result['disclosures'],list) else result['disclosures']},ensure_ascii=False))


if __name__=='__main__':main()
