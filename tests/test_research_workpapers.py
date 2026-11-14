import json
from concurrent.futures import ThreadPoolExecutor
import pytest

from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers, WorkpaperConflict


def paper(finding='Conditional adoption grows', **overrides):
    return dict(finding=finding, body=('Full public argument: observed delivery gains support adoption only '
        'when review and integration costs remain controlled. Customer renewal is still unobserved. ')*20,
        conditions='Same-risk tasks and controlled review costs', counterevidence='Rework can absorb gains',
        remaining='Renewal observations are not yet available', next_decision='Investigate customer procurement',
        disposition='continue', change='Initial finding', dependencies=[], evidence_receipt_ids=[]) | overrides


def store(tmp_path):
    return ResearchWorkpapers(tmp_path/'papers.sqlite',root_id='authorized-root', question='AI procurement outlook',
                              as_of='2026-11-14',check=lambda:None)


def dep(s, actor, topic):
    row=s.read(actor,topic)
    return {k:row[k] for k in ('topic_id','revision','digest')} | {'use':'qualified','rationale':'Only for controlled tasks'}


def test_three_level_revision_propagation_and_direct_original_readback(tmp_path):
    s=store(tmp_path)
    s.register('customer','root','Customer economics')
    s.register('cost','customer','Full delivery cost')
    s.register('competition','root','Pricing power')
    cost=s.publish('cost',0,paper(),{},'cost-v1')
    s.publish('customer',0,paper(dependencies=[dep(s,'customer','cost')]),{},'customer-v1')
    s.publish('competition',0,paper(dependencies=[dep(s,'competition','customer')]),{},'competition-v1')
    frozen=s.prepare('root',['competition'],'Compare customer and supplier economics; retain unmeasured renewal.')
    assert set(frozen['selected'])=={'cost','customer','competition'}
    assert 'Full public argument' not in json.dumps(frozen)
    for topic in frozen['selected']:
        s.read('root',topic)
    s.bind(frozen['snapshot_id'],'report-v1')
    s.require_current_binding('report-v1')
    # New bottom-level evidence changes the condition. Ancestors are stale, not automatically false.
    s.publish('cost',1,paper('Rework offsets gains',change='Actual cost observation changes prior premise'),{},'cost-v2')
    statuses={r['topic_id']:r['status'] for r in s.catalog()['topics']}
    assert statuses['customer']==statuses['competition']=='needs_reassessment'
    assert s.read('root','cost',1)['digest']==cost['digest']
    with pytest.raises(WorkpaperConflict,match='research_changed'):
        s.require_current_binding('report-v1')
    with pytest.raises(WorkpaperConflict,match='stale'):
        s.prepare('root',['competition'],'Attempt old synthesis')
    s.publish('customer',1,paper('Adoption varies by task',dependencies=[dep(s,'customer','cost')]),{},'customer-v2')
    assert s.read('root','competition')['requires_reassessment']
    s.publish('competition',1,paper('Supplier pricing remains contested',dependencies=[dep(s,'competition','customer')]),{},'competition-v2')
    renewed=s.prepare('root',['competition'],'Updated baseline; cost reversal narrows scope')
    assert renewed['snapshot_id']!=frozen['snapshot_id']
    assert all(r['revision']==2 for r in renewed['selected'].values())


def test_persistence_idempotency_and_failed_atomic_publication(tmp_path):
    s=store(tmp_path); s.register('a','root','A')
    one=s.publish('a',0,paper(),{},'once')
    assert store(tmp_path).publish('a',0,paper(),{},'once')==one
    with pytest.raises(WorkpaperConflict,match='command_changed'):
        s.publish('a',0,paper('Different payload'),{},'once')
    with pytest.raises(WorkpaperConflict,match='evidence_must'):
        s.publish('a',1,paper(evidence_receipt_ids=['missing']),{},'bad')
    assert s.read('root','a')['revision']==1
    s.check=lambda:(_ for _ in ()).throw(PermissionError('access revoked'))
    with pytest.raises(PermissionError):
        s.read('root','a')


def test_concurrent_writers_cannot_silently_replace_each_other(tmp_path):
    s=store(tmp_path);s.register('a','root','A')
    def attempt(i):
        try:return s.publish('a',0,paper(str(i)),{},str(i))
        except WorkpaperConflict:return None
    with ThreadPoolExecutor(2) as pool:
        results=list(pool.map(attempt,[1,2]))
    assert sum(r is not None for r in results)==1
    assert s.read('root','a')['revision']==1


def test_no_adoption_from_metadata_only_and_no_hidden_fulltext_truncation(tmp_path):
    s=store(tmp_path);s.register('a','root','A');s.register('b','root','B')
    s.publish('a',0,paper(),{},'a')
    meta=s.read('b','a',field='metadata')
    d={k:meta[k] for k in ('topic_id','revision','digest')}|{'use':'adopted','rationale':'Test'}
    with pytest.raises(WorkpaperConflict,match='read_dependency'):
        s.publish('b',0,paper(dependencies=[d]),{},'b')
    parts=[];offset=0
    while True:
        chunk=s.read('b','a',offset=offset,max_characters=97)
        parts.append(chunk['body']);offset=chunk['next_offset']
        if offset is None:break
    assert ''.join(parts)==paper()['body']
    assert chunk['conditions']==paper()['conditions']
    s.publish('b',0,paper(dependencies=[d]),{},'b')
    with pytest.raises(WorkpaperConflict,match='cyclic'):
        s.publish('a',1,paper(dependencies=[dep(s,'a','b')]),{},'a2')


def test_duplicate_source_identity_and_workspace_scope(tmp_path):
    s=store(tmp_path);s.register('a','root','A');s.register('b','root','B')
    evidence={'receipt':{'source':'Same original','period':'2026Q3'}}
    p=paper(evidence_receipt_ids=['receipt'])
    s.publish('a',0,p,evidence,'a');s.publish('b',0,p,evidence,'b')
    assert s.evidence('receipt')==evidence['receipt']
    with pytest.raises(RuntimeError,match='collision'):
        s.publish('b',1,p,{'receipt':{'source':'Altered source'}},'b2')
    with pytest.raises(RuntimeError,match='identity_mismatch'):
        ResearchWorkpapers(s.path,root_id='different-owner',question='Other',as_of='2026-11-14',check=lambda:None)
    with pytest.raises(WorkpaperConflict,match='topic_identity_changed'):
        s.register('a','b','A',reuse=True)


def test_snapshot_new_findings_require_explicit_scope_reconsideration(tmp_path):
    s=store(tmp_path);s.register('a','root','A');s.publish('a',0,paper(),{},'a')
    frozen=s.prepare('root',['a'],'A alone answers the bounded question')
    with pytest.raises(WorkpaperConflict,match='read_selected'):
        s.bind(frozen['snapshot_id'],'report')
    s.read('root','a');s.bind(frozen['snapshot_id'],'report')
    s.register('b','root','New unexpected factor');s.publish('b',0,paper('Countercase'),{},'b')
    assert s.snapshot(frozen['snapshot_id'])['changed_topics']==['b']
    with pytest.raises(WorkpaperConflict,match='research_changed'):
        s.require_current_binding('report')
