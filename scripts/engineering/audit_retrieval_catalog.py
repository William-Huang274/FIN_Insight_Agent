"""Read-only whole-release company/scope audit; never edits published identities."""
import argparse
from collections import defaultdict, Counter
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import zlib
from retrieval.catalog_company_identity import audit_catalog, cover_names, aliases_for
from retrieval.evidence_scope import source_scopes, covers_interval
from retrieval.filing_document_identity import original_filing_key


def query_roundtrip(metadata):
    """Exercise all catalog aliases, not just the evaluation companies."""
    from sec_agent.research_foundation.organization_query_plan import plan_query, select_planned
    examples=defaultdict(set)
    for document,row in metadata.items():
        for alias in aliases_for(row):examples[alias].add(document)
    rows=[]
    for alias,expected in sorted(examples.items()):
        selected,plan=select_planned(metadata,plan_query(alias+' cash',metadata,policy='conservative.v5'))
        rows.append({'alias':alias,'constraint':plan['constraint'],'unresolved':plan['unresolved'],
            'selected_sources':len(selected),'excluded_own_documents':sorted(expected-selected)})
    return {'tested_aliases':len(rows),'aliases_excluding_own_documents':sum(bool(r['excluded_own_documents']) for r in rows),
        'scope':'catalog_consistency_only_not_independent_entity_accuracy','results':rows}


def audit(index_path, metadata_path, output):
    import retrieval.evidence_scope as scope_module
    import retrieval.table_captions as caption_module
    import retrieval.fact_period_matching as period_module
    import retrieval.business_scope_attributes as business_module
    code={Path(m.__file__).name:sha256(Path(m.__file__).read_bytes()).hexdigest()
          for m in (scope_module,caption_module,period_module,business_module)}
    raw = index_path.read_bytes(); index = json.loads(raw); index_hash = sha256(raw).hexdigest(); del raw
    raw = metadata_path.read_bytes(); metadata = json.loads(raw); metadata_hash=sha256(raw).hexdigest()
    metadata = metadata.get('resolved',metadata); del raw
    grouped=defaultdict(list)
    for r in index['records']:grouped[r['document_id']].append(r)
    if set(grouped)-metadata.keys():raise ValueError('catalog_audit_metadata_does_not_cover_release')
    metadata={d:dict(metadata[d]) for d in grouped}
    output.mkdir(parents=True,exist_ok=False)
    counts=Counter(); scopes_file=output/'scope-rows.jsonl'
    with sqlite3.connect(index_path.parent.joinpath('navigation.sqlite').as_uri()+'?mode=ro',uri=True) as db, scopes_file.open('w',encoding='utf8') as out:
        for number,(document,records) in enumerate(grouped.items(),1):
            frames=defaultdict(list)
            original_keys=set()
            for record in records:
                value=db.execute('SELECT payload FROM nodes WHERE node_id=?',(record['node_id'],)).fetchone()
                if not value:raise ValueError('catalog_audit_missing_node')
                raw=zlib.decompress(value[0])
                if sha256(raw).hexdigest()!=record['navigation_sha256']:raise ValueError('catalog_audit_changed_node')
                row=json.loads(raw)
                if row['node_id']!=record['node_id'] or sha256(row['content'].encode()).hexdigest()!=record['content_sha256']:
                    raise ValueError('catalog_audit_changed_body')
                origin=row['original_source']; start=origin.get('source_char_start'); end=origin.get('source_char_end')
                key=original_filing_key(origin.get('source_url'))
                if key:original_keys.add(key)
                frame=None
                if not (type(start) is int and type(end) is int and len(row['content'])==end-start):
                    counts['nodes_without_global_coordinates']+=1
                    frame=origin.get('original_node_id')
                    start,end=origin.get('char_start'),origin.get('char_end')
                    if not frame or type(start) is not int or type(end) is not int or end-start!=len(row['content']):
                        counts['nodes_without_verified_coordinate_frame']+=1
                        continue
                    counts['nodes_with_original_node_coordinates']+=1
                frames[frame].append((start,end,row['node_id'],row['content']))
            if len(original_keys)>1:raise ValueError('catalog_audit_conflicting_original_document_urls')
            if original_keys:metadata[document]['original_filing_key']=next(iter(original_keys))
            known=0;has_scopes=False
            for frame,chunks in frames.items():
                chunks.sort();segments=[]
                for start,end,node,body in chunks:
                    if segments and start<=segments[-1][1]:
                        lo,hi,text=segments[-1]; overlap=min(hi,end)-start
                        if text[start-lo:start-lo+overlap]!=body[:overlap]:raise ValueError('catalog_audit_original_overlap_conflict')
                        if end>hi:segments[-1]=(lo,end,text+body[hi-start:])
                    else:segments.append((start,end,body))
                regions=[]
                for lo,hi,text in segments:
                    for scope in source_scopes(text):
                        regions.append({**scope,'source_char_start':scope['source_char_start']+lo,
                                        'source_char_end':scope['source_char_end']+lo})
                # A node's first character is not the document's cover.
                names=cover_names(segments[0][2]) if frame is None and segments and segments[0][0]==0 else []
                if len(names)==1:metadata[document]['verified_company_names']=names;counts['single_cover_name']+=1
                elif names:
                    metadata[document]['company_name_resolution']='joint_registrants_not_a_unique_owner'
                    counts['joint_cover_names']+=1
                has_scopes=has_scopes or bool(regions)
                for start,end,node,body in chunks:
                    scopes=[s for s in regions if s['source_char_start']<end and s['source_char_end']>start]
                    if scopes:
                        out.write(json.dumps({'document_id':document,'node_id':node,'evidence_scopes':scopes,
                            'source_interval':[start,end],
                            'coordinate_space':{'kind':'original_indexed_node','original_node_id':frame} if frame else {'kind':'original_document'},
                            'evidence_scope_complete':covers_interval(scopes,start,end)},ensure_ascii=False)+'\n');known+=1
            from retrieval.catalog_company_identity import with_original_registrant_identity
            metadata[document]=with_original_registrant_identity(metadata[document])
            counts['documents']+=1;counts['nodes']+=len(records);counts['scoped_nodes']+=known
            counts['documents_with_scopes']+=has_scopes
            if number%100==0:print(json.dumps(dict(counts)),flush=True)
    result={**audit_catalog(metadata),'scope_counts':dict(counts),'index_sha256':index_hash,
        'metadata_sha256':metadata_hash,'code_sha256':code,'provider_calls':0,'published_sources_modified':False,
        'scope_semantics':'exact_contiguous_original_intervals_only_not_financial_answer_validation'}
    (output/'catalog-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    (output/'resolved-metadata.json').write_text(json.dumps(metadata,ensure_ascii=False),encoding='utf8')
    (output/'company-query-roundtrip.json').write_text(json.dumps(query_roundtrip(metadata),ensure_ascii=False,indent=2),encoding='utf8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('index','metadata','output'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();r=audit(a.index.resolve(),a.metadata,a.output)
    print(json.dumps({k:r[k] for k in ('documents','scope_counts','identity_mutations')},ensure_ascii=False))
