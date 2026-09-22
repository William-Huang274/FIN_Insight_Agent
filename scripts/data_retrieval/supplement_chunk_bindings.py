"""Publish an additive locator review without changing any original fact."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from retrieval.library_chunks import add_reviewed_bindings
from sec_agent.research_foundation.research_library import ResearchLibrary,digest_file


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--target',type=Path,required=True);p.add_argument('--review',type=Path,required=True)
    a=p.parse_args();library=ResearchLibrary(a.library);review=json.loads(a.review.read_text(encoding='utf8'))
    with a.target.open('xb'):pass
    with closing(sqlite3.connect(a.library.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(a.target)) as dst:
        src.backup(dst);dst.row_factory=sqlite3.Row
        with dst:add_reviewed_bindings(dst,review['records'],review['reviewer'])
        counts=dict(dst.execute('SELECT status,count(*) FROM edge_chunk_coverage GROUP BY status').fetchall())
        assert not dst.execute('PRAGMA foreign_key_check').fetchall()
    manifest={**library.manifest,'sha256':digest_file(a.target),'locator_parent_sha256':library.manifest['sha256'],
       'retrieval_chunk_contract':{**library.manifest['retrieval_chunk_contract'],'edge_binding':counts}}
    a.target.with_suffix(a.target.suffix+'.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'sha256':manifest['sha256'],'edge_binding':counts}))


if __name__=='__main__':main()
