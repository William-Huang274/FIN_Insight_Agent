"""Frozen source-bound graph candidates; no public library or inferred facts.

Uses the original edges/edge_chunk_links contract, one-hop entity navigation and
an independent 12-chunk quota. Only currently authorized nodes can occupy it.
"""
from contextlib import closing
from datetime import date
from hashlib import sha256
import json
from pathlib import Path
import sqlite3

FORMAT = 'organization-source-graph.v1'


def encoded(value):
    return json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(',', ':'),allow_nan=False).encode()


def project(bundle, document):
    from .organization_source_projection import chunk_node_id
    source=bundle['source']
    chunks={r['id']:r for r in bundle['chunks']}
    edges={r['id']:r for r in bundle.get('edges',[])}
    if len(edges)!=len(bundle.get('edges',[])):
        raise ValueError('organization_graph_duplicate_edge')
    for edge in edges.values():
        if edge['source_id']!=source['id'] or any(not isinstance(edge.get(k),str) or not edge[k]
                for k in ('id','subject','object','predicate','status','published_at')):
            raise ValueError('organization_graph_edge_identity_invalid')
        for k in ('published_at','valid_from','valid_to'):
            if edge.get(k) is not None:
                date.fromisoformat(edge[k][:10])
        if edge.get('valid_from') and edge.get('valid_to') and edge['valid_from']>edge['valid_to']:
            raise ValueError('organization_graph_invalid_validity')
    links=[]
    for link in bundle.get('edge_chunk_links',[]):
        chunk=chunks.get(link['chunk_id'])
        if link['edge_id'] not in edges or chunk is None:
            raise ValueError('organization_graph_foreign_evidence')
        lo,hi=link['span_start'],link['span_end']
        if (lo is None)!=(hi is None) or (lo is not None and
                (not 0<=lo<hi or lo>=chunk['char_end'] or hi<=chunk['char_start'])):
            raise ValueError('organization_graph_evidence_span_invalid')
        links.append({**link,'node_id':chunk_node_id(document,chunk['id'])+':leaf',
                      'content_sha256':chunk['digest']})
    return {'document_id':document,'source_id':source['id'],'source_digest':source['digest'],
            'library_sha256':bundle['library_sha256'],
            'edges':sorted(edges.values(),key=lambda r:r['id']),
            'links':sorted(links,key=lambda r:(r['edge_id'],r['node_id'],r['evidence_index']))}


def preparation_graph(reader):
    """Explicit host publication step through the same current Java authority."""
    from .organization_source_navigation import OrganizationSourceNavigation
    before,manifest,_=reader._grant()
    by_resource={item['resource_id']:item for item in manifest['inputs']}
    def capture(resource,result):
        if result.get('truncated') or not result.get('source_bundle'):
            raise ValueError('organization_graph_requires_complete_sources')
        return project(result['source_bundle'],OrganizationSourceNavigation._identity(by_resource[resource]))
    result=list(reader._project_sources(by_resource,capture))
    reader._after(before)
    return result


def build(path, sources, records):
    records={r['node_id']:r for r in records}
    if {s['document_id'] for s in sources}!={r['document_id'] for r in records.values()}:
        raise ValueError('organization_graph_document_scope_mismatch')
    with Path(path).open('xb'):pass
    count=links_count=0
    with closing(sqlite3.connect(path)) as db,db:
        db.executescript('''CREATE TABLE documents(id TEXT PRIMARY KEY,digest TEXT NOT NULL);
          CREATE TABLE edges(document TEXT,id TEXT,subject TEXT,object TEXT,predicate TEXT,
            published TEXT,valid_from TEXT,valid_to TEXT,status TEXT,PRIMARY KEY(document,id));
          CREATE INDEX by_subject ON edges(subject); CREATE INDEX by_object ON edges(object);
          CREATE TABLE links(document TEXT,edge TEXT,node TEXT,digest TEXT,evidence_index INTEGER,
            PRIMARY KEY(document,edge,node,evidence_index));''')
        for source in sources:
            doc=source['document_id']
            db.execute('INSERT INTO documents VALUES (?,?)',(doc,sha256(encoded(source)).hexdigest()))
            for edge in source['edges']:
                db.execute('INSERT INTO edges VALUES (?,?,?,?,?,?,?,?,?)',
                    (doc,edge['id'],edge['subject'],edge['object'],edge['predicate'],edge['published_at'],
                     edge.get('valid_from'),edge.get('valid_to'),edge['status']))
                count+=1
            for link in source['links']:
                node=records.get(link['node_id'])
                if node is None or node['document_id']!=doc or node['content_sha256']!=link['content_sha256']:
                    raise ValueError('organization_graph_node_version_mismatch')
                db.execute('INSERT INTO links VALUES (?,?,?,?,?)',
                    (doc,link['edge_id'],link['node_id'],link['content_sha256'],link['evidence_index']))
                links_count+=1
    return {'documents':len(sources),'edges':count,'links':links_count}


def verify_source(path, bundle, document):
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        saved=db.execute('SELECT digest FROM documents WHERE id=?',(document,)).fetchone()
    if saved is None or saved[0]!=sha256(encoded(project(bundle,document))).hexdigest():
        raise ValueError('organization_graph_original_version_mismatch')


def candidates(path, rows, request, as_of, literal):
    """One hop, reviewed candidates, filters before quota; no inferred traversal."""
    allowed={r['node_id']:r for r in rows}
    endpoint={'both':'(e.subject=? OR e.object=?)','outgoing':'e.subject=?','incoming':'e.object=?'}[request.graph_direction]
    args=[request.entity_id]*(2 if request.graph_direction=='both' else 1)+[as_of]*3
    clause=''
    if request.graph_predicates:
        clause=' AND e.predicate IN ('+','.join('?' for _ in request.graph_predicates)+')'
        args.extend(request.graph_predicates)
    with closing(sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro',uri=True)) as db:
        db.row_factory=sqlite3.Row
        matches=db.execute('SELECT e.*,l.node,l.digest FROM edges e JOIN links l ON '
            'l.document=e.document AND l.edge=e.id WHERE '+endpoint+
            " AND e.status!='needs_semantic_review' AND substr(e.published,1,10)<=?"
            ' AND (e.valid_from IS NULL OR substr(e.valid_from,1,10)<=?)'
            ' AND (e.valid_to IS NULL OR substr(e.valid_to,1,10)>=?)'+clause+
            ' ORDER BY e.published DESC,l.node,e.id',args)
        # SQL adjacency is not truncated. Hidden nodes cannot occupy any quota
        # or influence traversal (one hop only). Only IDs/dates are inspected.
        eligible={}
        for match in matches:
            node=allowed.get(match['node'])
            if node is None:continue
            if node['parent_document_id']!=match['document'] or node['content_sha256']!=match['digest']:
                raise ValueError('organization_graph_candidate_version_mismatch')
            eligible.setdefault(match['node'],dict(match))
    order=list(dict.fromkeys([*(r['node_id'] for r in literal if r['node_id'] in eligible),*eligible]))[:12]
    evidence=[{k:eligible[node][k] for k in ('node','document','id','subject','object','predicate','published','status')}
              for node in order]
    return order,evidence
