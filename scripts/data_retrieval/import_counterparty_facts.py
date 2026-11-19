"""Import a reviewed extraction pack into an unpublished library build."""
import argparse
import json
from pathlib import Path
import sqlite3
from sec_agent.research_foundation.counterparty_facts import import_reviewed


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True)
    p.add_argument('--reviewed-pack',type=Path,required=True)
    a=p.parse_args()
    if a.build.with_suffix(a.build.suffix+'.manifest.json').exists():
        raise ValueError('immutable_release_cannot_be_modified')
    if not a.build.exists():raise FileNotFoundError(a.build)
    with sqlite3.connect(a.build) as db:
        db.row_factory=sqlite3.Row
        db.execute('PRAGMA foreign_keys=ON')
        result=import_reviewed(db,json.loads(a.reviewed_pack.read_text(encoding='utf8')))
    print(json.dumps(result))


if __name__=='__main__':main()
