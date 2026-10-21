"""Freeze all source identities and classify complete-source intake readiness.

Read-only; no provider, index build, source fetching or organization publication.
Unrecoverable sources remain in the denominator with explicit reasons.
"""
import argparse
from collections import Counter
from contextlib import closing, ExitStack
import json
from pathlib import Path
import sqlite3

from retrieval.library_source_bundle import recover_source, build_source_bundle, VectorReuseVerifier, validated_stored_chunks, compact_source_bundle
from retrieval.library_vectors import digest, ready_index


def source_protocol(source, parents):
    """Describe historical contracts, without guessing original document order."""
    locators = [p['locator'] for p in parents]
    metadata = json.loads(source['metadata'])
    if locators and all(x.startswith('text-part:') for x in locators):
        return 'overlapping_text_windows', 'parsed_utf8_text'
    if locators and all(x.startswith('raw text chars ') for x in locators):
        return 'raw_text_windows', 'original_bytes_equal_utf8_text_if_verified'
    if locators and all(x.startswith('HTML text chars ') for x in locators):
        return 'html_extraction_windows', 'original_binary'
    if locators and all(x.startswith('PDF page ') for x in locators):
        return 'pdf_page_windows', 'original_binary'
    if (metadata.get('origin') == 'existing_library'
            or metadata.get('import_origin') == 'existing_public_library'):
        return 'hierarchical_indexed_nodes', 'original_binary_or_original_node'
    if metadata.get('import_origin') == '094 frozen public survey originals':
        return 'survey_read_envelope', 'canonical_original_read_envelope'
    return 'unrecognized', 'unconfirmed'


def audit(library, output, index=None, as_of=None, recovery_catalog=None, node_catalog=None):
    if as_of is not None:
        from datetime import date
        date.fromisoformat(as_of)
    library, output = Path(library).resolve(), Path(output).resolve()
    if output == library or output.is_relative_to(library.parent):
        raise ValueError('audit_output_must_not_change_source_directory')
    index = Path(index).resolve() if index is not None else None
    if index is not None and (output == index or output.is_relative_to(index)):
        raise ValueError('audit_output_must_not_change_index_directory')
    # Exclusive creation prevents accidental replacement of a prior scope decision.
    with output.open('x', encoding='utf8') as stream:
        json.dump({'status':'incomplete','scope':'all records; no silent exclusion'}, stream)
    library_sha = digest(library)
    rows = []
    with ExitStack() as stack:
        db = stack.enter_context(closing(sqlite3.connect(library.as_uri()+'?mode=ro',uri=True)))
        db.row_factory = sqlite3.Row
        db.execute('BEGIN')
        verifier = None
        if index is not None:
            manifest, matrix, mapping = ready_index(index, library_sha)
            cache = stack.enter_context(closing(sqlite3.connect((index/'chunk-embeddings.sqlite').as_uri()+'?mode=ro',uri=True)))
            cache.execute('BEGIN')
            verifier = VectorReuseVerifier(manifest, matrix, mapping, cache)
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
                row['parent_protocol'], row['source_digest_basis'] = source_protocol(source, parents)
                try:
                    if node_catalog is not None and row['parent_protocol']=='hierarchical_indexed_nodes':
                        recovered=node_catalog.recover(source,parents,library_sha)
                        row.update(intake_status='indexed_node_set_recoverable',indexed_nodes=len(recovered['nodes']),
                                   indexed_node_characters=sum(len(p['body']) for p in parents),complete_original_document=False)
                    elif recovery_catalog is not None and row['parent_protocol'] in {'html_extraction_windows','pdf_page_windows'}:
                        text, _, _ = recovery_catalog.recover(source,parents,library_sha)
                        row.update(intake_status='parsed_text_recoverable', parsed_characters=len(text))
                    else:
                        text, _ = recover_source(source, parents)
                        row.update(intake_status='parsed_text_recoverable', parsed_characters=len(text))
                except (ValueError, KeyError, TypeError) as exc:
                    row.update(intake_status='requires_adapter_or_source_repair', reason=str(exc))
                if verifier is not None and row['intake_status'] in {'parsed_text_recoverable','indexed_node_set_recoverable'}:
                    stage = 'chunks_and_graph'
                    try:
                        bundle = build_source_bundle(db, source['id'], library_sha, recovery_catalog,node_catalog)
                        row['chunks_and_graph_verified'] = True
                        stage = 'vectors'
                        records, _ = verifier.verify(bundle)
                        row.update(vector_compatibility_verified=True, reused_vectors=len(records))
                        payload = {'schema_version':'project_library_source_snapshot.v2',
                                   'kind':'library_source','selection_mode':'indexed_node_set' if 'node_recovery' in bundle else 'complete_parsed_source',
                                   'bundle':compact_source_bundle(bundle)}
                        size = len(json.dumps(payload, ensure_ascii=False).encode())
                        row.update(capture_payload_bytes=size, capture_size_within_limit=size<=20*1024*1024)
                        if as_of is not None:
                            from sec_agent.research_foundation.organization_source_projection import validate_source_cutoff
                            try:
                                validate_source_cutoff(bundle,as_of)
                                row['organization_time_eligible']=True
                            except ValueError as exc:
                                row.update(organization_time_eligible=False,organization_time_failure=str(exc))
                    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                        row.update(verification_failure_stage=stage, verification_failure=str(exc))
                elif verifier is not None:
                    stage = 'stored_parent_chunks'
                    try:
                        chunks = validated_stored_chunks(db, source['id'], parents)
                        row['stored_parent_chunk_coverage_verified'] = True
                        stage = 'vectors'
                        records, _ = verifier.verify(dict(source=source,chunks=chunks,library_sha256=library_sha))
                        row.update(vector_compatibility_verified=True,reused_vectors=len(records),
                                   vector_verification_scope='stored parent surfaces only; complete source unresolved')
                    except (ValueError, KeyError, TypeError, sqlite3.Error) as exc:
                        row.update(verification_failure_stage=stage, verification_failure=str(exc))
            rows.append(row)
            if len(rows) % 25 == 0:
                output.write_text(json.dumps(dict(status='incomplete',sources=rows,
                    library_sha256=library_sha, provider_calls=0),ensure_ascii=False,indent=2),encoding='utf8')
        if index is not None and ready_index(index,library_sha)[0] != manifest:
            raise ValueError('source_vector_index_changed_during_inventory')
    unchanged = digest(library) == library_sha
    report = dict(status='scope_inventory_complete' if unchanged else 'source_changed',
                  library_sha256=library_sha, sources=rows, source_count=len(rows),
                  access_states=dict(Counter(r['access_state'] for r in rows)),
                  intake_statuses=dict(Counter(r['intake_status'] for r in rows)),
                  repair_reasons=dict(Counter(r['reason'] for r in rows if r['intake_status']=='requires_adapter_or_source_repair')),
                  parent_protocols=dict(Counter(r['parent_protocol'] for r in rows if 'parent_protocol' in r)),
                  verified_vector_sources=sum(r.get('vector_compatibility_verified',False) for r in rows),
                  verified_vectors=sum(r.get('reused_vectors',0) for r in rows),
                  verification_failures=dict(Counter(r['verification_failure'] for r in rows if 'verification_failure' in r)),
                  oversized_captures=sum(r.get('capture_size_within_limit') is False for r in rows),
                  research_as_of=as_of,
                  organization_time_eligible_sources=sum(r.get('organization_time_eligible',False) for r in rows),
                  provider_calls=0, organization_publication_verified=False,
                  vector_compatibility_verified=bool(index is not None) and all(
                      r.get('vector_compatibility_verified',False) for r in rows if r['access_state']=='readable'),
                  vector_verification_scope='all readable stored chunks; not complete source or organization acceptance',
                  full_scope_retrieval_accepted=False)
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    if not unchanged:
        raise ValueError('source_library_changed_during_inventory')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--index',type=Path,help='Also verify every recoverable source against this existing index; no provider calls')
    parser.add_argument('--as-of',help='Check organization strict-as-of eligibility independently of physical readability')
    parser.add_argument('--recovery-catalog',type=Path)
    parser.add_argument('--recovery-sha256')
    parser.add_argument('--node-catalog',type=Path)
    parser.add_argument('--node-sha256')
    args=parser.parse_args()
    from retrieval.library_archive_recovery import ArchiveRecoveryCatalog
    if bool(args.recovery_catalog) != bool(args.recovery_sha256):
        parser.error('recovery catalog and SHA256 must be supplied together')
    catalog=ArchiveRecoveryCatalog(args.recovery_catalog,args.recovery_sha256) if args.recovery_catalog else None
    from retrieval.library_node_recovery import NodeRecoveryCatalog
    if bool(args.node_catalog)!=bool(args.node_sha256):parser.error('node catalog and SHA256 must be supplied together')
    nodes=NodeRecoveryCatalog(args.node_catalog,args.node_sha256) if args.node_catalog else None
    result=audit(args.library,args.output,args.index,args.as_of,catalog,nodes)
    print(json.dumps({k:v for k,v in result.items() if k!='sources'},ensure_ascii=False))


if __name__=='__main__': main()
