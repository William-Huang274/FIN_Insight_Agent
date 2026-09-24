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
from threading import RLock

from .research_snapshot import ResearchSnapshot, build_snapshot
from .source_document_navigation import SourceDocumentResult, SourceExecutionReceipt


def digest_file(path):
    h = sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def _file_identity(path):
    stat = Path(path).stat()
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)


_validation_lock = RLock()


@lru_cache(maxsize=4)
def _validate_release(path, identity, expected_digest):
    if digest_file(path) != expected_digest or _file_identity(path) != identity:
        raise ValueError('research_library_integrity_or_scope_failure')


@lru_cache(maxsize=4)
def _cached_library(path, identity, manifest_identity):
    return ResearchLibrary(path)


def open_library(path):
    """Validate each immutable release once; replacement invalidates the cache."""
    path=Path(path).resolve()
    return _cached_library(str(path),_file_identity(path),
                           _file_identity(path.with_suffix(path.suffix+'.manifest.json')))


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
        path = Path(path).resolve()
        manifest = json.loads(path.with_suffix(path.suffix + '.manifest.json').read_text(encoding='utf-8'))
        if manifest.get('access_scope') != 'public' or manifest.get('version') != 'research_library.v1':
            raise ValueError('research_library_integrity_or_scope_failure')
        # Share only immutable validation, never request configuration or access.
        # Serialize cold validation: lru_cache alone permits duplicate in-flight scans.
        with _validation_lock:
            _validate_release(str(path), _file_identity(path), manifest['sha256'])
        self.manifest = manifest
        super().__init__(path)
        self._release_stat = _file_identity(self.path)
        from retrieval.library_chunks import has_chunks
        self.has_retrieval_chunks = has_chunks(self)

    def search(self, terms, as_of, *, source_ids=(), limit=12):
        if not self.has_retrieval_chunks:
            return super().search(terms,as_of,source_ids=source_ids,limit=limit)
        if not terms or not 1<=limit<=40:raise ValueError('empty_terms_or_invalid_limit')
        eligible=[s['id'] for s in self.catalog(as_of) if s['eligible'] and (not source_ids or s['id'] in source_ids)]
        if not eligible:return []
        expression=' OR '.join('"'+str(t).replace('"','""')+'"' for t in terms)
        return self.chunks_by_ids(self.search_chunk_ids(expression, eligible, limit=limit))

    def search_chunk_ids(self, expression, source_ids, *, limit=12, edge_ids=None):
        """FTS applies eligibility before top K; no body table join while scoring."""
        if not expression or not source_ids or edge_ids == []:
            return []
        marks = ','.join('?' for _ in source_ids)
        conditions = f' AND source_id IN ({marks})'
        parameters = [expression, *source_ids]
        if edge_ids is not None:
            conditions += ' AND id IN (SELECT chunk_id FROM edge_chunk_links WHERE edge_id IN (' + ','.join('?' for _ in edge_ids) + '))'
            parameters.extend(edge_ids)
        # Hidden rank supports FTS5's ranked traversal and keeps existing weights.
        # Graph ties retain the established ID order.
        order = 'rank,id' if edge_ids is not None else 'rank'
        rows = self._query('SELECT id FROM chunk_search WHERE chunk_search MATCH ?'
            + conditions + " AND rank MATCH 'bm25(0,0,0.3,1.0)' ORDER BY " + order + ' LIMIT ?',
            (*parameters, limit))
        return [r['id'] for r in rows]

    def chunks_by_ids(self, ids):
        """Bounded batches; preserve caller ranking and remove duplicate IDs."""
        ids = list(dict.fromkeys(ids))
        found = {}
        for start in range(0, len(ids), 400):
            batch = ids[start:start+400]
            found.update((r['id'], r) for r in self._query(
                'SELECT * FROM retrieval_chunks WHERE id IN (' + ','.join('?' for _ in batch) + ')', batch))
        return [found[cid] for cid in ids if cid in found]

    def read(self, source_id, as_of, *, start=0, limit=8):
        result=super().read(source_id,as_of,start=start,limit=limit)
        if self.has_retrieval_chunks and result['status']=='readable':
            rows=self._query('SELECT c.* FROM retrieval_chunks c JOIN passages p ON p.id=c.parent_id WHERE c.source_id=? ORDER BY p.rowid,c.ordinal LIMIT ? OFFSET ?',
                            (source_id,limit+1,start))
            result.update(items=rows[:limit],next_start=start+limit if len(rows)>limit else None)
        return result

    def graph_search(self, entity_id, as_of, *, depth=1, max_edges=80, predicates=(), direction='both', review='all'):
        if depth not in {1, 2}:
            raise ValueError('graph_depth_out_of_scope')
        if direction not in {'both','outgoing','incoming'} or review not in {'all','reviewed'}:
            raise ValueError('invalid_graph_filter')
        if not 0<=max_edges<=1000 or len(predicates)>16:
            raise ValueError('invalid_graph_window')
        known = {e['id'] for e in self.entities()}
        if entity_id not in known:
            return {'status': 'unknown_entity', 'edges': [], 'truncated': False}
        frontier, visited, found = {entity_id}, set(), {}
        from .industry_data import position_relations_batch
        eligible={s['id'] for s in self.catalog(as_of) if s['eligible']}
        for _ in range(depth):
            next_frontier = set()
            current=sorted(frontier-visited)
            if not current:break
            marks=','.join('?' for _ in current)
            endpoint=(f'e.subject IN ({marks})' if direction=='outgoing' else
                      f'e.object IN ({marks})' if direction=='incoming' else
                      f'(e.subject IN ({marks}) OR e.object IN ({marks}))')
            args=[*current,*(current if direction=='both' else []),self._cutoff(as_of),as_of,as_of]
            clause=''
            if predicates:
                clause+=' AND e.predicate IN ('+','.join('?' for _ in predicates)+')';args.extend(predicates)
            if review=='reviewed':clause+=" AND e.status!='needs_semantic_review'"
            adjacent={eid:[] for eid in current}
            for row in self._query('SELECT e.* FROM edges e WHERE '+endpoint+
                    ' AND e.published_at<=? AND (e.valid_from IS NULL OR e.valid_from<=?) '
                    'AND (e.valid_to IS NULL OR e.valid_to>=?)'+clause+' ORDER BY e.rowid',args):
                if row['source_id'] not in eligible:continue
                endpoints=([row['subject']] if direction=='outgoing' else [row['object']] if direction=='incoming' else [row['subject'],row['object']])
                for eid in set(endpoints) & adjacent.keys():adjacent[eid].append(dict(row))
            positions=position_relations_batch(self.path,current,as_of) if not predicates or 'reported_security_position' in predicates else {}
            for entity in current:
                visited.add(entity)
                # Preserve the published endpoint-index order (subject then
                # object, rowid within each) when batching the OR lookups.
                adjacent[entity].sort(key=lambda r:r['subject']!=entity)
                # Reviewed relations must not be crowded out by many literal
                # co-mentions when a graph window reaches its size bound.
                holdings=[r for r in positions.get(entity,[]) if r['source_id'] in eligible and
                          (direction=='both' or r['subject' if direction=='outgoing' else 'object']==entity)]
                related=sorted(adjacent[entity]+holdings,
                    key=lambda r:2 if r['status']=='needs_semantic_review' else 1 if r['predicate']=='reported_security_position' else 0)
                identities=set()
                for row in related:
                    identity=(row['id'],) if row['id'].startswith('RELATION::') else tuple(row[k] for k in ('subject','object','predicate','source_id'))
                    if identity in identities:continue
                    identities.add(identity)
                    if row['id'] not in found and len(found) >= max_edges:
                        return self._graph_result(found, truncated=True)
                    if isinstance(row['qualifiers'],str):row['qualifiers'] = json.loads(row['qualifiers'])
                    row['candidate_only'] = True
                    found[row['id']] = row
                    next_frontier.update([row['subject'], row['object']])
            frontier = next_frontier - visited
        return self._graph_result(found, truncated=False)

    def _graph_result(self, found, *, truncated):
        from collections import defaultdict
        parents = defaultdict(list)
        keys = list(dict.fromkeys((r['source_id'], r['locator']) for r in found.values()))
        for start in range(0, len(keys), 200):
            batch = keys[start:start+200]
            # VALUES join permits indexed source lookup instead of scanning passages.
            rows = self._query('WITH wanted(source_id,locator) AS (VALUES '
                + ','.join('(?,?)' for _ in batch) + ') '
                'SELECT p.id,p.source_id,p.locator,p.digest FROM wanted w JOIN passages p '
                'ON p.source_id=w.source_id AND p.locator=w.locator ORDER BY p.rowid',
                [value for pair in batch for value in pair])
            for row in rows:
                parents[(row['source_id'], row['locator'])].append(row)
        bindings = {}
        if self.has_retrieval_chunks:
            from retrieval.library_chunks import edge_evidence_batch
            bindings = edge_evidence_batch(self, list(found))
        for row in found.values():
            row['evidence'] = parents[(row['source_id'], row['locator'])]
            if self.has_retrieval_chunks:
                chunks, binding = bindings[row['id']]
                row['parent_evidence'] = row['evidence']
                row['evidence'] = chunks or row['evidence']
                row['chunk_binding'] = binding
                if chunks:
                    row['readback'] = {'source_space':'library','operation':'read','document_id':row['source_id'],'node_id':chunks[0]['id']}
            row.setdefault('readback', {'source_space':'library','operation':'read','document_id':row['source_id']})
        return {'status':'ok','edges':list(found.values()),'truncated':truncated}

    def navigate(self, request, as_of):
        if _file_identity(self.path) != self._release_stat:
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
                from .company_navigation import company_navigation
                detail,total,next_offset=company_navigation(detail,request)
                return self._result(request,[detail],'ok',total=total,next_offset=next_offset)
            if request.data_kind=='metrics':
                from .metric_workspace import query_metrics
                page=query_metrics(self.path,[request.entity_id,*request.compare_entity_ids],section=request.metric_section,
                    metric=request.query,record_id=request.metric_record_id,as_of=as_of,fiscal_year=request.fiscal_year,
                    period_kind=request.metric_period_kind,frequency=request.metric_frequency,alignment=request.metric_alignment,
                    date_start=request.date_start.isoformat() if request.date_start else '',date_end=request.date_end.isoformat() if request.date_end else '',
                    offset=request.offset,limit=request.limit)
                return self._result(request,[{'result_state':'retrieval_candidate','dataset_kind':'metric_dataset','numeric_fact_authority':False,**page}],
                    'ok',total=page['total'],next_offset=page.get('next_offset'))
            if request.data_kind=='disclosures':
                from .disclosure_register import fact_page
                from .industry_data import connect
                from contextlib import closing
                with closing(connect(self.path)) as db:
                    page=fact_page(db,request.entity_id,request.query,request.offset,request.limit,as_of)
            else:
                page=data_page(self.path,request.entity_id,kind=request.data_kind,query=request.query,group=request.data_group,
                               account=request.account_path,offset=request.offset,limit=request.limit,as_of=as_of,
                               fiscal_year=request.fiscal_year,fiscal_period=request.fiscal_period,derived_view=request.derived_view,
                               date_start=request.date_start.isoformat() if request.date_start else '',date_end=request.date_end.isoformat() if request.date_end else '')
            if not page['items'] and request.query:
                return self._result(request,[{'result_state':'typed_gap','query_contract':'literal substring, not natural language; dates and metric descriptions are not parsed','original_query':request.query,'retry_arguments':{'source_space':'library','operation':'data','entity_id':request.entity_id,'data_kind':request.data_kind,**({'data_group':request.data_group} if request.data_group else {}),**({'account_path':request.account_path} if request.account_path else {}),**({'fiscal_year':request.fiscal_year} if request.fiscal_year is not None else {}),**({'fiscal_period':request.fiscal_period} if request.fiscal_period else {}),**({'derived_view':request.derived_view,'date_start':request.date_start.isoformat() if request.date_start else None,'date_end':request.date_end.isoformat() if request.date_end else None} if request.data_kind=='derived' else {}),'query':'','limit':3},'public_information_gap_proved':False}],'filter_no_match',total=0,next_offset=None)
            return self._result(request,[{'result_state':'retrieval_candidate','numeric_fact_authority':False,**r} for r in page['items']],'ok',total=page['total'],next_offset=page['next_offset'])
        status = 'ok'
        if request.operation == 'catalog':
            rows = [{'result_state': 'retrieval_candidate', 'entity_id': e['id'], **e} for e in self.entities()]
            documents = sorted(self.catalog(as_of), key=lambda s: (s['eligible'], s.get('published_at') or '', s['id']), reverse=True)
            rows += [{'result_state': 'retrieval_candidate', 'document_id': s['id'], **s} for s in documents]
            if request.query.strip() not in {'','*'}:
                terms=request.query.casefold().split()
                aliases={a['entity_id']:[] for a in self._query('SELECT entity_id FROM aliases')}
                for alias in self._query('SELECT * FROM aliases'):
                    aliases[alias['entity_id']].append(alias['alias'])
                rows=[r for r in rows if (any if r.get('entity_id') else all)(t in json.dumps([r,aliases.get(r.get('entity_id'),[])],ensure_ascii=False).casefold() for t in terms)]
        elif request.operation == 'related':
            graph = self.graph_search(request.entity_id, as_of, depth=request.graph_depth,
                                      predicates=request.graph_predicates,direction=request.graph_direction,review=request.graph_review)
            status = 'graph_window_truncated' if graph['truncated'] else graph['status']
            rows = [{'result_state': 'retrieval_candidate', **e} for e in graph['edges']]
        elif request.operation == 'search':
            shared_graph = None
            candidates=self.search(request.query.split(), as_of, source_ids=[request.document_id] if request.document_id else (), limit=40)
            retrieval={'mode':'fts5_bm25'}
            if self.retrieval_environment.get('FINSIGHT_LIBRARY_HYBRID')=='1':
                from retrieval.library_hybrid import rank
                cache=self.retrieval_environment.get('FINSIGHT_LIBRARY_RAG_CACHE_PATH')
                if not cache:
                    raise ValueError('library_hybrid_cache_not_configured')
                if self.has_retrieval_chunks and request.entity_id:
                    shared_graph = self.graph_search(request.entity_id, as_of, depth=1, max_edges=1000,
                        predicates=request.graph_predicates,direction=request.graph_direction,review=request.graph_review)
                # Provider/cache failure is explicit. It must not be silently
                # converted into an empty result or public information gap.
                candidates,retrieval=rank(self,request.query,as_of,candidates,path=cache,
                    document_id=request.document_id,entity_id=request.entity_id,graph_result=shared_graph)
            source_ids = list(dict.fromkeys(p['source_id'] for p in candidates))
            source_details = {}
            for start in range(0, len(source_ids), 200):
                batch_ids = source_ids[start:start+200]
                source_details.update({s['id']: s for s in self._query(
                    'SELECT id,title,published_at,vintage,metadata FROM sources WHERE id IN ('
                    + ','.join('?' for _ in batch_ids) + ')', batch_ids)})
            rows = [{'result_state': 'retrieval_candidate', 'document_id': p['source_id'],
                'title': source_details[p['source_id']]['title'],
                'publication_date': source_details[p['source_id']]['published_at'],
                'source_vintage': source_details[p['source_id']]['vintage'],
                'source_known_at': json.loads(source_details[p['source_id']]['metadata'] or '{}').get('known_at'),
                'node_id': p['id'], 'preview': p['body'][:500], 'digest': p['digest'], 'retrieval':retrieval,
                **({'candidate_ranks':p['candidate_ranks'],'rerank_score':p.get('rerank_score')} if 'candidate_ranks' in p else {}),
                **({'parent_node_id':p['parent_id'],'source_char_start':p['char_start'],'source_char_end':p['char_end'],
                    'context':p['context'],'chunk_kind':p['kind']} if p.get('parent_id') else {})}
                for p in candidates]
            if request.entity_id:
                output_graph = shared_graph if shared_graph is not None and request.graph_depth == 1 else self.graph_search(request.entity_id, as_of, depth=request.graph_depth,
                    predicates=request.graph_predicates,direction=request.graph_direction,review=request.graph_review)
                graph_edges = output_graph['edges'][:80]
                if output_graph['truncated'] or len(output_graph['edges'])>80:status='graph_window_truncated'
                rows += [{'result_state': 'retrieval_candidate', **e}
                         for e in graph_edges
                         if not request.document_id or e['source_id'] == request.document_id]
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
                if not passages and status=='readable' and self.has_retrieval_chunks:
                    passages=self._query('SELECT * FROM retrieval_chunks WHERE id=? AND source_id=?',(request.node_id,request.document_id))
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
                if p.get('parent_id'):
                    rows[-1].update(parent_node_id=p['parent_id'],source_char_start=p['char_start'],source_char_end=p['char_end'],
                        context=p['context'],chunk_kind=p['kind'],chunk_flags=json.loads(p['flags']),
                        parent_readback={'source_space':'library','operation':'read','document_id':p['source_id'],'node_id':p['parent_id']})
                    neighbors=self._query('SELECT id,ordinal FROM retrieval_chunks WHERE parent_id=? AND ordinal IN (?,?) ORDER BY ordinal',
                        (p['parent_id'],p['ordinal']-1,p['ordinal']+1))
                    rows[-1]['context_readbacks']=[{'direction':'previous' if n['ordinal']<p['ordinal'] else 'next',
                        'source_space':'library','operation':'read','document_id':p['source_id'],'node_id':n['id']} for n in neighbors]
            if passages and not rows:
                if self.has_retrieval_chunks and request.node_id and not passages[0].get('parent_id'):
                    children=self._query('SELECT id,source_id,parent_id,char_start,char_end,context,digest,body FROM retrieval_chunks WHERE parent_id=? ORDER BY ordinal LIMIT ? OFFSET ?',
                        (request.node_id,request.limit,request.offset))
                    if children:
                        total=self._query('SELECT count(*) AS n FROM retrieval_chunks WHERE parent_id=?',(request.node_id,))[0]['n']
                        return self._result(request,[{'result_state':'retrieval_candidate','node_id':c['id'],
                            'document_id':c['source_id'],'parent_node_id':c['parent_id'],'source_char_start':c['char_start'],
                            'source_char_end':c['char_end'],'context':c['context'],'preview':c['body'][:300],'digest':c['digest'],
                            'readback':{'source_space':'library','operation':'read','document_id':c['source_id'],'node_id':c['id']}} for c in children],
                            'parent_exceeds_character_budget_use_child_readbacks',total=total,
                            next_offset=request.offset+len(children) if request.offset+len(children)<total else None)
                status = 'block_exceeds_character_budget_increase_max_characters'
            table='retrieval_chunks' if self.has_retrieval_chunks else 'passages'
            total = self._query(f'SELECT COUNT(*) AS n FROM {table} WHERE source_id=?', (request.document_id,))[0]['n'] if status == 'readable' else 0
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
