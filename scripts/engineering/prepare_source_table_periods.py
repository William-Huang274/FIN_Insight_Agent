"""Offline, no-network replay of archived HTML into source-bound period overlays.

Input IDs select stored sources, not answers. The output catalog is optional
capture-time configuration; no existing publication, index or service is changed.
"""
import argparse
import gc
from collections import Counter
import json
from pathlib import Path
import re
import sqlite3
import time
import zlib

from retrieval.library_source_bundle import expand_source_bundle, validate_bundle_text
from retrieval.source_table_periods import build_overlay, digest, validate_overlay


def build_compatible_overlay(raw, *, raw_sha256, source_digest):
    """Do not build an HTML DOM for a whole non-HTML holdings XML capture.

    Source availability and source retrieval remain independent of this optional
    overlay. Null-byte encodings abstain from the byte prefilter and retain the
    existing parser, since their ASCII tag bytes need not be contiguous.
    """
    if digest(raw) != raw_sha256:
        raise ValueError('source_raw_digest_mismatch')
    if b'\x00' not in raw and not re.search(rb'<table[\s/>]', raw, re.I):
        raise ValueError('source_original_has_no_html_tables')
    return build_overlay(raw, raw_sha256=raw_sha256, source_digest=source_digest)


def prepare(intake, archive, source_ids, output):
    from retrieval import source_table_periods
    code={str(p):digest(p.read_bytes()) for p in (Path(__file__),Path(source_table_periods.__file__))}
    intake,archive,output=Path(intake),Path(archive),Path(output)
    output.mkdir(parents=True,exist_ok=False)
    manifest_raw=(intake/'result.json').read_bytes()
    manifest=json.loads(manifest_raw)
    available={s['source_id']:s for s in manifest['sources']}
    if len(source_ids)!=len(set(source_ids)) or not source_ids:
        raise ValueError('period_overlay_source_selection_invalid')
    catalog={'format':'source-table-period-catalog.v1','library_sha256':manifest['library_sha256'],'sources':{}}
    report={'status':'running','provider_calls':0,'input_manifest_sha256':digest(manifest_raw),'sources':[],
            'implementation_sha256':code,
            'scope':'archived_original_period_geometry_not_retrieval_quality_or_service_acceptance'}
    try:
        with sqlite3.connect(archive.resolve().as_uri()+'?mode=ro',uri=True) as db:
            for source_id in source_ids:
                started=time.monotonic(); entry=available[source_id]
                raw=(intake/entry['directory']/'source.json').read_bytes()
                if digest(raw)!=entry['files']['source.json']:
                    raise ValueError('period_overlay_intake_changed')
                bundle=expand_source_bundle(json.loads(raw)); validate_bundle_text(bundle)
                source=bundle['source']
                result={'source_id':source_id,'source_digest':source['digest']}
                captured=db.execute('SELECT status,digest,body_zlib FROM raw_captures WHERE url=?',(source['url'],)).fetchone()
                if not captured or captured[0]!=200 or 'node_recovery' in bundle:
                    result.update(status='unavailable_compatible_archive',tables=0,explicit_facts=0)
                else:
                    try:
                        overlay=build_compatible_overlay(zlib.decompress(captured[2]),raw_sha256=captured[1],source_digest=digest(bundle['text']))
                        validate_overlay({**bundle,'table_period_context':overlay})
                    except ValueError as error:
                        result.update(status='unresolved',reason=str(error),tables=0,explicit_facts=0)
                    else:
                        payload=json.dumps(overlay,ensure_ascii=False,separators=(',',':')).encode()
                        name=digest(source_id)+'.json'; (output/name).write_bytes(payload)
                        catalog['sources'][source_id]={'source_digest':source['digest'],'file':name,'sha256':digest(payload)}
                        facts=[f for t in overlay['tables'] for c in t['cells'] for f in c['facts']]
                        result.update(status='verified',raw_sha256=captured[1],tables=len(overlay['tables']),
                            nested_tables_without_bindings=overlay['nested_tables_without_bindings'],
                            table_statuses=dict(Counter(t['status'] for t in overlay['tables'])),
                            explicit_facts=sum(f['period']['status']=='explicit_xbrl_period' for f in facts),
                            unresolved_facts=sum(f['period']['status']!='explicit_xbrl_period' for f in facts),
                            output_bytes=len(payload))
                result['seconds']=time.monotonic()-started
                report['sources'].append(result)
                (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
                print(json.dumps(result,ensure_ascii=False),flush=True)
                # BeautifulSoup's detached tree nodes contain cycles; do not
                # retain prior source DOMs until a later allocation threshold.
                gc.collect()
        if digest((intake/'result.json').read_bytes())!=report['input_manifest_sha256']:
            raise ValueError('period_overlay_intake_changed')
        if any(digest(Path(p).read_bytes())!=sha for p,sha in code.items()):
            raise ValueError('period_overlay_implementation_changed')
        catalog_raw=json.dumps(catalog,ensure_ascii=False,indent=2).encode()
        (output/'catalog.json').write_bytes(catalog_raw)
        report.update(status='completed',catalog_sha256=digest(catalog_raw),verified=len(catalog['sources']))
    except Exception as error:
        report.update(status='failed',error_type=type(error).__name__,error=str(error));raise
    finally:
        (output/'result.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for arg in ('intake','archive','source-ids','output'):p.add_argument('--'+arg,required=True)
    a=p.parse_args()
    prepare(a.intake,a.archive,json.loads(Path(a.source_ids).read_bytes()),a.output)
