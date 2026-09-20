"""Immutable public research library: SQLite FTS + source-bound graph retrieval.

No model extraction or paid corpus rebuild. Edges are retrieval candidates, not
proof of a causal/financial claim. Publication is explicit and never in-place.
"""
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import sqlite3
import os
from functools import lru_cache

from .research_snapshot import ResearchSnapshot, build_snapshot
from .source_document_navigation import SourceDocumentResult, SourceExecutionReceipt


def digest_file(path):
    h = sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


@lru_cache(maxsize=4)
def _cached_library(path, modified, size, manifest_modified):
    return ResearchLibrary(path)


def open_library(path):
    """Validate each immutable release once; replacement invalidates the cache."""
    path=Path(path).resolve(); stat=path.stat()
    return _cached_library(str(path),stat.st_mtime_ns,stat.st_size,
                           path.with_suffix(path.suffix+'.manifest.json').stat().st_mtime_ns)


def publish_library(target, snapshot_paths, *, public_sources_confirmed=False, public_nodes=()):
    """Import verified public snapshots and existing KB nodes into a NEW release.

    Failed publications have no manifest and are never readable as releases.
    Duplicate identities with different content are rejected, never overwritten.
    """
    if not public_sources_confirmed:
        raise ValueError('public_library_requires_public_source_scope_confirmation')
    target = Path(target)
    sources, passages, entities, edges, observations = {}, {}, {}, {}, {}
    receipts, imports = [], []

    def add(table, value):
        if value['id'] in table and table[value['id']] != value:
            raise ValueError('conflicting_identity:' + value['id'])
        table[value['id']] = value

    for path in snapshot_paths:
        snapshot = ResearchSnapshot(path)
        imports.append({'name': Path(path).name, 'sha256': digest_file(path)})
        for row in snapshot._query('SELECT * FROM sources'):
            row['metadata'] = json.loads(row['metadata'])
            add(sources, row)
        for row in snapshot._query('SELECT * FROM passages'):
            if sha256(row['body'].encode()).hexdigest() != row['digest']:
                raise ValueError('passage_integrity_failure')
            add(passages, row)
        for row in snapshot.entities():
            row['aliases'] = sorted(a['alias'] for a in snapshot._query('SELECT alias FROM aliases WHERE entity_id=?', (row['id'],)))
            add(entities, row)
        for row in snapshot._query('SELECT * FROM edges'):
            row['qualifiers'] = json.loads(row['qualifiers'])
            add(edges, row)
        for row in snapshot._query('SELECT * FROM observations'):
            row['payload'] = json.loads(row['payload'])
            add(observations, row)
        receipts.extend(json.loads(r['payload']) for r in snapshot._query('SELECT payload FROM access_receipts'))
    for node in public_nodes:
        body = str(node.get('content') or '')
        if not body:
            continue
        if sha256(body.encode()).hexdigest() != node['content_sha256']:
            raise ValueError('public_node_integrity_failure')
        sid = str(node['parent_document_id'])
        source = {'id': sid, 'title': node['title'], 'url': node['stable_url'],
            'published_at': node.get('publication_date'), 'vintage': 'dated_original',
            'access_state': 'readable', 'digest': node.get('raw_body_sha256') or node['content_sha256'],
            'metadata': {'import_origin': 'existing_public_library', 'coverage': 'indexed_nodes_only'}}
        if sid not in sources:
            add(sources, source)
        elif sources[sid]['url'] != source['url']:
            raise ValueError('public_document_identity_conflict')
        add(passages, {'id': 'PASSAGE::' + node['node_id'] + '::' + node['content_sha256'][:16],
            'source_id': sid, 'locator': str(node.get('section_path') or node['node_id']),
            'body': body, 'digest': node['content_sha256']})
    for edge in edges.values():
        if not any(p['source_id'] == edge['source_id'] for p in passages.values()):
            raise ValueError('edge_requires_readable_source_document:' + edge['id'])
        exact = any(p['source_id'] == edge['source_id'] and p['locator'] == edge['locator'] for p in passages.values())
        edge['qualifiers'] = {**edge['qualifiers'], 'runtime_locator_binding': 'exact_passage' if exact else 'document_only_requires_readback'}
    build_snapshot(target, sources.values(), passages.values(), entities=entities.values(),
                   edges=edges.values(), observations=observations.values(), receipts=receipts)
    with closing(sqlite3.connect(target)) as db, db:
        db.execute("UPDATE snapshot_metadata SET value='published_public_library.v1' WHERE key='state'")
        db.execute('CREATE INDEX edges_subject ON edges(subject)')
        db.execute('CREATE INDEX edges_object ON edges(object)')
        db.execute('CREATE INDEX passages_source ON passages(source_id)')
        db.execute('CREATE INDEX observations_entity ON observations(entity)')
    manifest = {'version': 'research_library.v1', 'access_scope': 'public',
        'sha256': digest_file(target), 'imports': imports,
        'counts': {k: len(v) for k, v in dict(sources=sources, passages=passages,
            entities=entities, edges=edges, observations=observations).items()},
        'retrieval': 'sqlite_fts5_plus_source_bound_graph', 'semantic_model_acceptance': False}
    with target.with_suffix(target.suffix + '.manifest.json').open('x', encoding='utf-8') as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    return manifest


class ResearchLibrary(ResearchSnapshot):
    required_state = 'published_public_library.v1'

    def __init__(self, path, *, retrieval_environment=None):
        self.retrieval_environment=dict(os.environ if retrieval_environment is None else retrieval_environment)
        path = Path(path)
        manifest = json.loads(path.with_suffix(path.suffix + '.manifest.json').read_text(encoding='utf-8'))
        if manifest.get('access_scope') != 'public' or manifest.get('version') != 'research_library.v1' or digest_file(path) != manifest['sha256']:
            raise ValueError('research_library_integrity_or_scope_failure')
        self.manifest = manifest
        super().__init__(path)
        stat = self.path.stat()
        self._release_stat = (stat.st_mtime_ns, stat.st_size)

    def graph_search(self, entity_id, as_of, *, depth=1, max_edges=80):
        if depth not in {1, 2}:
            raise ValueError('graph_depth_out_of_scope')
        known = {e['id'] for e in self.entities()}
        if entity_id not in known:
            return {'status': 'unknown_entity', 'edges': [], 'truncated': False}
        frontier, visited, found = {entity_id}, set(), {}
        from .industry_data import position_relations
        for _ in range(depth):
            next_frontier = set()
            for entity in sorted(frontier - visited):
                visited.add(entity)
                # Reviewed relations must not be crowded out by many literal
                # co-mentions when a graph window reaches its size bound.
                related=sorted(self.related(entity, as_of)+position_relations(self.path,entity,as_of),
                    key=lambda r:2 if r['status']=='needs_semantic_review' else 1 if r['predicate']=='reported_security_position' else 0)
                identities=set()
                for row in related:
                    identity=tuple(row[k] for k in ('subject','object','predicate','source_id'))
                    if identity in identities:continue
                    identities.add(identity)
                    if row['id'] not in found and len(found) >= max_edges:
                        return {'status': 'ok', 'edges': list(found.values()), 'truncated': True}
                    if isinstance(row['qualifiers'],str):row['qualifiers'] = json.loads(row['qualifiers'])
                    row['candidate_only'] = True
                    row['evidence'] = self._query('SELECT id,source_id,locator,digest FROM passages WHERE source_id=? AND locator=?', (row['source_id'], row['locator']))
                    row.setdefault('readback', {'source_space':'library', 'operation':'read', 'document_id':row['source_id']})
                    found[row['id']] = row
                    next_frontier.update([row['subject'], row['object']])
            frontier = next_frontier - visited
        return {'status': 'ok', 'edges': list(found.values()), 'truncated': False}

    def navigate(self, request, as_of):
        stat = self.path.stat()
        if (stat.st_mtime_ns, stat.st_size) != self._release_stat:
            raise ValueError('published_library_changed_during_run')
        if request.source_space != 'library':
            raise ValueError('wrong_library_source_space')
        if request.operation in {'company','data'}:
            from .industry_data import installed, company_detail, data_page
            if not installed(self.path):
                return self._result(request, [], 'company_foundation_not_installed', total=0, next_offset=None)
            entities=self.entities()
            if not any(e['id']==request.entity_id for e in entities):
                needle=request.entity_id.casefold().removeprefix('company::')
                alias_ids={a['entity_id'] for a in self._query('SELECT alias,entity_id FROM aliases') if a['alias'].casefold()==needle}
                suggestions=[{'result_state':'retrieval_candidate','entity_id':e['id'],**e,'identity_match':'suggestion_only_copy_exact_id_then_retry'} for e in entities if e['id'] in alias_ids or needle in (e['name']+' '+e['id']).casefold()]
                return self._result(request,suggestions[:request.limit],'unknown_entity_use_suggested_exact_id',total=len(suggestions),next_offset=None)
            if request.operation == 'company':
                try:
                    detail=company_detail(self.path,request.entity_id,as_of=as_of)
                except KeyError:
                    suggestions=[{'result_state':'retrieval_candidate','entity_id':e['id'],**e,'identity_match':'suggestion_only_copy_exact_id_then_retry'} for e in self.entities() if request.entity_id.casefold().removeprefix('company::') in (e['name']+' '+e['id']).casefold()]
                    return self._result(request, suggestions[:request.limit], 'unknown_entity_use_suggested_exact_id', total=len(suggestions),next_offset=None)
                # The menu stays compact and points at originals. Document lists
                # paginate independently of the company identity/card.
                sources=detail.pop('sources');total=len(sources)
                detail['result_state']='retrieval_candidate'
                detail['sources']=sources[request.offset:request.offset+request.limit]
                for source in detail['sources']:
                    # Cache routing representations are not new research
                    # evidence; keep them in storage, not in agent context.
                    source['metadata'].pop('routing_metadata_v1',None)
                detail['sources_total']=total
                return self._result(request,[detail],'ok',total=total,
                    next_offset=request.offset+request.limit if request.offset+request.limit<total else None)
            page=data_page(self.path,request.entity_id,kind=request.data_kind,query=request.query,group=request.data_group,
                           account=request.account_path,offset=request.offset,limit=request.limit,as_of=as_of)
            if not page['items'] and request.query:
                return self._result(request,[{'result_state':'typed_gap','query_contract':'literal substring, not natural language; dates and metric descriptions are not parsed','original_query':request.query,'retry_arguments':{'source_space':'library','operation':'data','entity_id':request.entity_id,'data_kind':request.data_kind,**({'data_group':request.data_group} if request.data_group else {}),**({'account_path':request.account_path} if request.account_path else {}),'query':'','limit':3},'public_information_gap_proved':False}],'filter_no_match',total=0,next_offset=None)
            return self._result(request,[{'result_state':'retrieval_candidate','numeric_fact_authority':False,**r} for r in page['items']],'ok',total=page['total'],next_offset=page['next_offset'])
        status = 'ok'
        if request.operation == 'catalog':
            rows = [{'result_state': 'retrieval_candidate', 'entity_id': e['id'], **e} for e in self.entities()]
            rows += [{'result_state': 'retrieval_candidate', 'document_id': s['id'], **s} for s in self.catalog(as_of)]
            if request.query.strip() not in {'','*'}:
                terms=request.query.casefold().split()
                aliases={a['entity_id']:[] for a in self._query('SELECT entity_id FROM aliases')}
                for alias in self._query('SELECT * FROM aliases'):
                    aliases[alias['entity_id']].append(alias['alias'])
                rows=[r for r in rows if (any if r.get('entity_id') else all)(t in json.dumps([r,aliases.get(r.get('entity_id'),[])],ensure_ascii=False).casefold() for t in terms)]
        elif request.operation == 'related':
            graph = self.graph_search(request.entity_id, as_of, depth=request.graph_depth)
            status = graph['status']
            rows = [{'result_state': 'retrieval_candidate', **e} for e in graph['edges']]
        elif request.operation == 'search':
            candidates=self.search(request.query.split(), as_of, source_ids=[request.document_id] if request.document_id else (), limit=40)
            retrieval={'mode':'fts5_bm25'}
            if self.retrieval_environment.get('FINSIGHT_LIBRARY_HYBRID')=='1':
                from retrieval.library_hybrid import rank
                cache=self.retrieval_environment.get('FINSIGHT_LIBRARY_RAG_CACHE_PATH')
                if not cache:
                    raise ValueError('library_hybrid_cache_not_configured')
                # Provider/cache failure is explicit. It must not be silently
                # converted into an empty result or public information gap.
                candidates,retrieval=rank(self,request.query,as_of,candidates,path=cache,
                    document_id=request.document_id,entity_id=request.entity_id)
            rows = [{'result_state': 'retrieval_candidate', 'document_id': p['source_id'],
                'node_id': p['id'], 'preview': p['body'][:500], 'digest': p['digest'], 'retrieval':retrieval}
                for p in candidates]
            if request.entity_id:
                rows += [{'result_state': 'retrieval_candidate', **e} for e in self.graph_search(request.entity_id, as_of, depth=request.graph_depth)['edges']]
        elif request.operation == 'observations':
            rows=[{'result_state':'retrieval_candidate', **o, 'numeric_fact_authority':False,
                'readback':{'source_space':'library','operation':'read','document_id':o['source_id']}}
                for o in self.observations(request.entity_id,as_of)]
        else:
            result = self.read(request.document_id, as_of, start=request.offset, limit=request.limit)
            status = result['status']
            source = result.get('source', {})
            passages = result['items']
            if request.node_id:
                # Exact node lookup is independent of document pagination.
                passages = self._query('SELECT * FROM passages WHERE id=? AND source_id=?', (request.node_id, request.document_id)) if status == 'readable' else []
                if not passages and status == 'readable':
                    status = 'unknown_node'
            rows = []
            used = 0
            for p in passages:
                if used + len(p['body']) > request.max_characters:
                    break
                used += len(p['body'])
                rows.append({'result_state': 'source_bound_passage', 'document_id': p['source_id'],
                    'node_id': p['id'], 'passage_id': p['id'] if p['id'].startswith('PASSAGE::') else 'PASSAGE::' + p['id'], 'passage': p['body'],
                    'content_sha256': p['digest'], 'source_url': source['url'], 'writer_citable': True,
                    'numeric_fact_authority': False, 'source_locator': {'document_id': p['source_id'],
                        'node_id': p['id'], 'locator': p['locator'], 'source_url': source['url'], 'content_sha256': p['digest']},
                    'publication_date': source['published_at'], 'authority_note': 'Source text; preserve population, period, unit and qualifiers. Graph edges do not confer authority.'})
            if passages and not rows:
                status = 'block_exceeds_character_budget_increase_max_characters'
            total = self._query('SELECT COUNT(*) AS n FROM passages WHERE source_id=?', (request.document_id,))[0]['n'] if status == 'readable' else 0
            return self._result(request, rows, status, total=1 if request.node_id and total else total,
                next_offset=None if request.node_id or status != 'readable' or request.offset+len(rows)>=total else request.offset+len(rows))
        total = len(rows)
        return self._result(request, rows[request.offset:request.offset+request.limit], status, total=total,
            next_offset=request.offset+request.limit if request.offset+request.limit < total else None)

    def _result(self, request, rows, status, *, total, next_offset):
        value = {'request': request.model_dump(mode='json'), 'status': status, 'items': rows, 'snapshot': self.manifest['sha256']}
        digest = sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        receipt_status = 'ok' if rows else 'scope_ineligible' if status == 'ineligible_vintage_or_date' else 'coverage_boundary' if status not in {'ok', 'readable'} else 'zero_results'
        return SourceDocumentResult(operation=request.operation, items=tuple(rows), total_matches=total,
            next_offset=next_offset, source_snapshot_sha256=self.manifest['sha256'],
            notice=f'Library status={status}; graph candidates are not causal facts. Indexed scope only, not exhaustive public availability. Follow readback or evidence source_id as document_id and evidence id as node_id to read originals. Search returns up to40 lexical candidates; graph expansion capped at80 edges and2 hops. Structured observations retain source/period/unit but are not S2 authority.',
            execution_receipt=SourceExecutionReceipt(receipt_id='EXEC::'+digest,
                operation='read' if request.operation=='read' else 'search', status=receipt_status,
                provider_receipt_digest=digest, document_id=request.document_id))
