"""Publish a reviewed SQL build as an immutable, compatible library release."""
import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3
from sec_agent.research_foundation.research_library import digest_file


def publish(build,target,*,as_of,acceptance='coverage_review_pending'):
    build=Path(build).resolve();target=Path(target).resolve()
    if target.exists():raise FileExistsError(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    # Online backup gives one consistent snapshot while independent acquisition
    # continues. Only the new file is changed; previous releases stay readable.
    with closing(sqlite3.connect(build.as_uri()+'?mode=ro',uri=True)) as src,closing(sqlite3.connect(target)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('integrity_check_failed')
        if dst.execute('PRAGMA foreign_key_check').fetchone():raise ValueError('foreign_key_check_failed')
        dst.execute("UPDATE snapshot_metadata SET value='published_public_library.v1' WHERE key='state'")
        dst.execute("INSERT OR REPLACE INTO snapshot_metadata VALUES('research_as_of',?)",(as_of,))
        dst.execute("INSERT OR REPLACE INTO snapshot_metadata VALUES('foundation_acceptance',?)",(acceptance,))
        dst.commit()
        counts={t:dst.execute('SELECT count(*) FROM '+t).fetchone()[0] for t in ['sources','passages','entities','edges','observations','company_cards','financial_points','market_prices','filing_catalog','institution_positions']}
        if dst.execute("SELECT 1 FROM sqlite_master WHERE name='derived_financials'").fetchone():
            counts['derived_financials']=dst.execute('SELECT count(*) FROM derived_financials').fetchone()[0]
    manifest={'version':'research_library.v1','access_scope':'public','sha256':digest_file(target),'counts':counts,
        'research_as_of':as_of,'foundation_acceptance':acceptance,'retrieval':'fts5_bm25_source_bound_graph_optional_document_dense_rerank',
        'semantic_model_acceptance':False,'build_backup':'SQLite online backup; immutable release; no overwrite'}
    target.with_suffix(target.suffix+'.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    return manifest


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--target',type=Path,required=True);p.add_argument('--as-of',required=True)
    p.add_argument('--acceptance',choices=['coverage_review_pending','coverage_inventory_recorded'],default='coverage_review_pending')
    a=p.parse_args();print(json.dumps(publish(a.build,a.target,as_of=a.as_of,acceptance=a.acceptance),ensure_ascii=False))
