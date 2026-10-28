"""Published span vectors and BM25, with immutable parent citation identities."""
from contextlib import closing
from hashlib import sha256,file_digest
import json
from pathlib import Path
import sqlite3
import numpy as np
from .semantic_unit_catalog import iter_units

FORMAT='published-original-unit-index.v2'
LEGACY_FORMAT='published-original-unit-index.v1'
FILES=('unit-metadata.sqlite','unit-vectors.npy','unit-lexical.sqlite')


def build(directory,catalog,parent_records,parent_matrix,embedding_reader,*,model,original_reader):
    """Build into a NEW publication directory; callback reads completed receipts.

    This function never submits requests. Every new vector must name its exact
    input digest and model. Reused vectors require exact parent input equality.
    Caller must bind the parent release and source authority before publication.
    """
    from sec_agent.research_foundation.organization_hybrid_retrieval import vector
    from .published_lexical_index import build as build_lexical
    directory=Path(directory)
    parents={r['node_id']:r for r in parent_records}
    count=0;seen=set();last_parent=None;original=None
    with (directory/'unit-metadata.sqlite').open('xb'):pass
    # Reserve the vector artifact before any callbacks to prevent overwriting.
    with (directory/'unit-vectors.npy').open('xb') as vectors,closing(sqlite3.connect(directory/'unit-metadata.sqlite')) as db,db:
        db.executescript('''PRAGMA journal_mode=DELETE; PRAGMA cache_size=-2048;
            CREATE TABLE units(position INTEGER PRIMARY KEY,id TEXT UNIQUE NOT NULL,parent TEXT NOT NULL,
                document TEXT NOT NULL,digest TEXT NOT NULL,input_digest TEXT NOT NULL,
                start INTEGER NOT NULL,end INTEGER NOT NULL,coordinate_space TEXT);
            CREATE INDEX unit_parent ON units(parent);
            CREATE INDEX unit_document ON units(document);''')
        with closing(sqlite3.connect(Path(catalog).resolve().as_uri()+'?mode=ro',uri=True)) as plan:
            expected=plan.execute('SELECT count(*) FROM units').fetchone()[0]
        np.lib.format.write_array_header_1_0(vectors,{'descr':np.lib.format.dtype_to_descr(np.dtype(np.float32)),
            'fortran_order':False,'shape':(expected,1024)})
        def lexical_rows():
            nonlocal count,last_parent,original
            for position,unit,reuse in iter_units(catalog):
                parent=parents.get(unit['parent_node_id'])
                if (parent is None or parent['document_id']!=unit['parent_document_id']
                        or parent['content_sha256']!=unit['parent_content_sha256'] or position!=count):
                    raise ValueError('semantic_index_parent_identity_mismatch')
                if last_parent!=parent['node_id']:
                    original=original_reader(parent);last_parent=parent['node_id']
                from .source_coordinates import origin_bounds
                space,lo,hi=origin_bounds(original['original_source'])
                a,b=unit['source_char_start'],unit['source_char_end']
                if (original['node_id']!=parent['node_id'] or original['parent_document_id']!=parent['document_id']
                        or sha256(original['content'].encode()).hexdigest()!=parent['content_sha256']
                        or unit['original_node_id']!=space or not lo<=a<b<=hi
                        or unit['source_digest']!=original['original_source']['source_digest']
                        or unit['content']!=original['content'][a-lo:b-lo]
                        or unit.get('context_policy')!='document-identity-only.v1'
                        or unit['embedding_context']!=_document_context(original)):
                    raise ValueError('semantic_index_unit_not_bound_to_original')
                if reuse is not None:
                    if reuse!=parent['vector_index'] or parent['embedding_input_sha256']!=unit['embedding_input_sha256']:
                        raise ValueError('semantic_index_cannot_reuse_different_input')
                    values=parent_matrix[reuse]
                else:
                    result=embedding_reader(unit)
                    if result['model']!=model or result['input_sha256']!=unit['embedding_input_sha256']:
                        raise ValueError('semantic_index_embedding_receipt_mismatch')
                    values=result['vector']
                vectors.write(vector(values,1024).tobytes(order='C'))
                db.execute('INSERT INTO units VALUES (?,?,?,?,?,?,?,?,?)',(position,unit['unit_id'],
                    unit['parent_node_id'],unit['parent_document_id'],unit['content_sha256'],unit['embedding_input_sha256'],
                    unit['source_char_start'],unit['source_char_end'],unit['original_node_id']))
                count+=1;seen.add(unit['parent_node_id'])
                # No filing title or neighboring body contributes lexical
                # counts to this unit. Structural context remains separate.
                yield {'node_id':unit['unit_id'],'content':unit['content'],
                    'content_sha256':unit['content_sha256'],'node_kind':'text'}
        lexical_count=build_lexical(directory/'unit-lexical.sqlite',lexical_rows())
        if count!=expected or count!=lexical_count or seen!=set(parents):
            raise ValueError('semantic_index_incomplete_parent_population')
    hashes={}
    for name in FILES:
        with (directory/name).open('rb') as stream:hashes[name]=file_digest(stream,'sha256').hexdigest()
    return {'format':FORMAT,'units':count,'parents':len(seen),'model':model,'dimensions':1024,'files':hashes}


def _document_context(row):
    from .original_input_context import document_context
    return document_context(row)


def validate(directory,descriptor,records,model,*,verified_files=False):
    from sec_agent.research_foundation.organization_vector_math import unit_vectors
    directory=Path(directory)
    if (set(descriptor)!={'format','units','parents','model','dimensions','files'} or descriptor['format'] not in {FORMAT,LEGACY_FORMAT}
            or type(descriptor['units']) is not int or descriptor['units']<1
            or descriptor['parents']!=len(records) or descriptor['model']!=model or descriptor['dimensions']!=1024
            or set(descriptor['files'])!=set(FILES)):
        raise ValueError('semantic_index_contract_invalid')
    for name,digest in descriptor['files'].items():
        if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('semantic_index_digest_invalid')
        if name.endswith('.sqlite') and any((directory/(name+suffix)).exists() for suffix in ('-wal','-journal')):
            raise ValueError('semantic_index_unsealed')
        if not verified_files:
            with (directory/name).open('rb') as stream:
                if file_digest(stream,'sha256').hexdigest()!=digest:raise ValueError('semantic_index_file_mismatch')
    matrix=np.load(directory/'unit-vectors.npy',mmap_mode='r',allow_pickle=False)
    if matrix.dtype!=np.float32 or matrix.shape!=(descriptor['units'],1024):raise ValueError('semantic_index_matrix_shape')
    if not verified_files and not unit_vectors(matrix):raise ValueError('semantic_index_invalid_vectors')
    with closing(sqlite3.connect((directory/'unit-metadata.sqlite').as_uri()+'?mode=ro',uri=True)) as db:
        actual=db.execute('SELECT count(*),count(distinct parent),min(position),max(position) FROM units').fetchone()
        if actual!=(descriptor['units'],len(records),0,descriptor['units']-1):raise ValueError('semantic_index_population_mismatch')
        actual_parents={n:d for n,d in db.execute('SELECT DISTINCT parent,document FROM units')}
        if actual_parents!={r['node_id']:r['document_id'] for r in records}:raise ValueError('semantic_index_parent_scope_mismatch')


def select_units(directory,parents,wanted):
    """Metadata only; authority and original scopes come from verified parents."""
    from .evidence_scope import select_scoped
    by_id={r['node_id']:r for r in parents};result=[]
    with closing(sqlite3.connect((Path(directory)/'unit-metadata.sqlite').resolve().as_uri()+'?mode=ro',uri=True)) as db:
        identifiers=list(by_id)
        for offset in range(0,len(identifiers),256):
            chunk=identifiers[offset:offset+256]
            for pos,identifier,parent,document,digest,input_digest,start,end,space in db.execute(
                    'SELECT * FROM units WHERE parent IN ('+','.join('?' for _ in chunk)+') ORDER BY position',chunk):
                original=by_id[parent]
                if original['parent_document_id']!=document:raise ValueError('semantic_query_parent_scope_mismatch')
                result.append({'node_id':identifier,'parent_node_id':parent,'parent_document_id':document,
                    'content_sha256':digest,'lexical_input_sha256':digest,'embedding_input_sha256':input_digest,
                    'vector_index':pos,'source_interval':[start,end],'original_node_id':space,
                    'evidence_scopes':original.get('evidence_scopes',[]),
                    'period_evidence':original.get('period_evidence',[]),
                    'fact_owner':original.get('fact_owner',{}),
                    'evidence_scope_complete':original.get('evidence_scope_complete',False)})
    return select_scoped(result,wanted)[0] if wanted else result


def rank(directory,parents,query_vector,needs,metadata,wanted,*,policy,graph=None,population_cache=None,capture_trace=False,trace_sink=None):
    """Unit scores precede original-parent quotas in both recall channels."""
    from .organization_search_needs import lexical_candidates
    from .candidate_pipeline import fuse_channels
    from sec_agent.research_foundation.organization_vector_math import verified_cosine_scores
    units=select_units(directory,parents,wanted)
    matrix=np.load(Path(directory)/'unit-vectors.npy',mmap_mode='r',allow_pickle=False)
    scores=verified_cosine_scores(matrix,[u['vector_index'] for u in units],query_vector)
    best={};groups={}
    for row,score in zip(units,scores,strict=True):
        groups[row['node_id']]=row['parent_node_id'];key=row['parent_node_id']
        if key not in best or float(score)>best[key][0]:best[key]=(float(score),row)
    lexical,lanes=lexical_candidates(Path(directory)/'unit-lexical.sqlite',units,needs,metadata,
        population_cache=population_cache,capture_trace=capture_trace,result_groups=groups,trace_sink=trace_sink)
    available=[p for p in parents if p['node_id'] in best]
    eligible={p['node_id'] for p in available}
    active_graph=[n for n in graph if n in eligible] if graph is not None else None
    entry,order,limits=fuse_channels(available,[best[p['node_id']][0] for p in available],lexical,
        policy=policy,lexical_policy=needs['policy'],graph=active_graph)
    complete_dense=None
    if capture_trace and trace_sink is not None:
        complete_dense=trace_sink('dense_units',0,(
            {'node_id':u['node_id'],'parent_node_id':u['parent_node_id'],'score':float(score),
             'source_interval':u['source_interval'],'original_node_id':u['original_node_id']}
            for u,score in zip(units,scores,strict=True)))
    receipt={'policy':FORMAT,'unit_population':len(units),'parent_population':len(available),'limits':limits,
        'independent_backfill':entry.get('independent_backfill'),
        '_eligible_parent_ids':list(eligible),
        'lexical_needs':lanes,'dense_trace':{'population_count':len(available),'trace_limit':96,
            'trace_truncated':len(available)>96,'scores':[{'node_id':available[i]['node_id'],
                'score':best[available[i]['node_id']][0],'unit_id':best[available[i]['node_id']][1]['node_id'],
                'rank':number+1} for number,i in enumerate(order[:96])]},
        'dense_unit_spans':{n:{k:best[n][1][k] for k in ('node_id','source_interval','original_node_id')}
                            for n in entry['dense']},
        'scoring_semantics':'maximum_eligible_original_unit_before_parent_quota_not_parent_vector',
        **({'full_dense_units_artifact':complete_dense} if complete_dense else {})}
    return entry,receipt
