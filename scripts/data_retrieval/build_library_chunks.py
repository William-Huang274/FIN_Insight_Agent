"""Build a new immutable library release with child chunks and graph links."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from retrieval.library_chunks import build_chunks
from sec_agent.research_foundation.research_library import ResearchLibrary, digest_file


def main():
    p=argparse.ArgumentParser();p.add_argument('--library',type=Path,required=True);p.add_argument('--target',type=Path,required=True);p.add_argument('--audit',type=Path,required=True)
    a=p.parse_args();old=ResearchLibrary(a.library)
    a.target.parent.mkdir(parents=True,exist_ok=True)
    with a.target.open('xb'):pass
    with closing(sqlite3.connect(a.library.resolve().as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(a.target)) as dst:
        src.backup(dst)
    result=build_chunks(a.target)
    manifest={**old.manifest,'sha256':digest_file(a.target),'parent_sha256':old.manifest['sha256'],
        'retrieval_chunk_contract':result,'retrieval':'child_chunk_fts_dense_source_bound_graph',
        'new_vector_index_created':False,'semantic_model_acceptance':False}
    a.target.with_suffix(a.target.suffix+'.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    a.audit.parent.mkdir(parents=True,exist_ok=True);a.audit.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
