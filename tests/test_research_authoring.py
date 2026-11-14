import json
from concurrent.futures import ThreadPoolExecutor
import pytest
from langchain_core.messages import ToolMessage
from sec_agent.agent_runtime.research_workpapers import ResearchWorkpapers, WorkpaperConflict
from sec_agent.agent_runtime.research_authoring import authoring_context_replacements
from sec_agent.agent_runtime.research_graph_contracts import canonical_sha256
from test_research_workpapers import store, paper, dep


def judgment(key, *, refs=(), depends=(), statement=None):
    return dict(id=key,statement=statement or key,rationale='Public comparison explains the conditional inference',
                conditions='Same scope and period',counterevidence='Alternative explanation remains possible',
                remaining='Observe renewal',workpapers=list(refs),depends_on=list(depends))


def section(key, ids, order=0):
    return dict(id=key,title=key,question='What changes?',role='Supports the original decision',judgment_ids=ids,order=order)


def initialized(tmp_path):
    s=store(tmp_path)
    for key in ['cost','competition']:
        s.register(key,'root',key);s.publish(key,0,paper(key),{},key)
    cost=judgment('cost',refs=[dep(s,'root','cost')])
    competition=judgment('competition',refs=[dep(s,'root','competition')])
    thesis=judgment('thesis',depends=['cost'])
    patch=dict(reason='Initial public understanding',judgments=[cost,competition,thesis],
        sections=[section('summary',['thesis']),section('cost',['cost'],1),section('competition',['competition'],2)],lead_judgment_ids=['thesis'])
    s.authoring.update(0,patch,'u1')
    return s,cost,competition,thesis


def test_incremental_state_preserves_unaffected_entries_and_propagates(tmp_path):
    s,cost,competition,thesis=initialized(tmp_path)
    first=s.authoring.context()
    s.publish('cost',1,paper('Costs reverse'),{},'cost2')
    view=s.authoring.context(['cost'])
    assert set(view['requires_reassessment'])=={'cost','thesis'}
    assert set(view['affected_sections'])=={'cost','summary'}
    assert 'competition' not in view['judgments']
    cost['workpapers']=[dep(s,'root','cost')];cost['statement']='New conditional cost'
    update=s.authoring.update(1,dict(reason='New cost evidence',judgments=[cost]),'u2')
    assert set(update['requires_reassessment'])=={'thesis'}
    assert s.authoring.context()['judgments']['competition']==first['judgments']['competition']
    with pytest.raises(WorkpaperConflict,match='reassess_judgments'):
        s.prepare('root',['cost','competition'],'Current selected materials')
    thesis['statement']='Revised overall scope'
    s.authoring.update(2,dict(reason='Propagate changed premise',judgments=[thesis]),'u3')
    assert not s.authoring.context()['requires_reassessment']
    assert s.authoring.context(revision=1)['judgments']==first['judgments']
    assert store(tmp_path).authoring.context()['digest']==s.authoring.context()['digest']


def test_atomic_patch_idempotency_cycles_and_concurrency(tmp_path):
    s,*_=initialized(tmp_path)
    patch=dict(reason='Only wording',sections=[section('cost',['cost'],4)])
    a=s.authoring.update(1,patch,'same');assert s.authoring.update(1,patch,'same')==a
    with pytest.raises(WorkpaperConflict,match='command_changed'):
        s.authoring.update(1,dict(reason='Changed request'),'same')
    with pytest.raises(WorkpaperConflict,match='cycle'):
        s.authoring.update(2,dict(reason='Bad cycle',judgments=[judgment('cost',depends=['thesis'])]),'cycle')
    assert s.authoring.context()['revision']==2
    def attempt(i):
        try:return s.authoring.update(2,dict(reason=str(i)),str(i))
        except WorkpaperConflict:return None
    with ThreadPoolExecutor(2) as pool:
        assert sum(v is not None for v in pool.map(attempt,[1,2]))==1


def test_read_basis_and_source_versions_required(tmp_path):
    s,*_=initialized(tmp_path)
    ref=s.read('root','cost',field='metadata');ref={k:ref[k] for k in ('topic_id','revision','digest')}|{'use':'adopted','rationale':'Test'}
    ref['digest']='invented'
    with pytest.raises(WorkpaperConflict,match='digest'):
        s.authoring.update(1,dict(reason='Bad source',judgments=[judgment('other',refs=[ref])]),'bad')
    with pytest.raises(WorkpaperConflict,match='select_outline'):
        s.prepare('root',['cost'],'Omit competition even though outline uses it')


def test_multiple_issues_independent_resolution_binding_and_reopen(tmp_path):
    s,cost,competition,thesis=initialized(tmp_path)
    report={'narrative_markdown':'Summary sentence. Cost sentence. Competition sentence.'}
    for key,kind,quote in [('gap','missing_link','Cost sentence.'),('wording','expression','Competition sentence.')]:
        s.authoring.open_issue(1,dict(id=key,section_ids=['cost' if key=='gap' else 'competition'],
            kind=kind,question='Explain the relationship',quote=quote),report)
    with pytest.raises(WorkpaperConflict,match='investigation_result'):
        s.authoring.resolve('gap',1,'bounded_answer','No search result',[],report)
    s.authoring.resolve('wording',1,'revised','Clarified the unit',[],report)
    statuses={i['id']:i['status'] for i in s.authoring.context()['issues']}
    assert statuses=={'gap':'open','wording':'resolved'}
    s.register('followup','root','Investigate actual total cost')
    s.publish('followup',0,paper('Net costs after review'),{},'f1',assignment={'authoring_issue_id':'gap','task_id':'actual-task'})
    result=dep(s,'root','followup')
    s.authoring.resolve('gap',1,'retained','This comparison supports the existing condition',[result],report)
    frozen=s.prepare('root',['cost','competition','followup'],'Complete current basis')
    with pytest.raises(WorkpaperConflict,match='bind_each'):
        s.bind(frozen['snapshot_id'],canonical_sha256(report),report=report)
    uses=[dict(section_id=k,excerpt=q) for k,q in [('summary','Summary sentence.'),('cost','Cost sentence.'),('competition','Competition sentence.')]]
    s.bind(frozen['snapshot_id'],canonical_sha256(report),report=report,section_uses=uses)
    s.require_current_binding(canonical_sha256(report))
    s.publish('followup',1,paper('Changed followup'),{},'f2',assignment={'authoring_issue_id':'gap'})
    assert {i['id']:i['status'] for i in s.authoring.context()['issues']}=={'gap':'open','wording':'resolved'}
    assert s.authoring.handoff('gap')['issue']['report_digest']==canonical_sha256(report)


def test_snapshot_understanding_change_and_new_issue_block_old_delivery(tmp_path):
    s,*_=initialized(tmp_path)
    frozen=s.prepare('root',['cost','competition'],'Basis')
    s.authoring.update(1,dict(reason='Changed outline',sections=[section('cost',['cost'],9)]),'u2')
    assert s.snapshot(frozen['snapshot_id'])['understanding_changed']
    with pytest.raises(WorkpaperConflict,match='understanding_changed'):
        s.bind(frozen['snapshot_id'],'report')


def test_issue_identity_wrong_result_and_ambiguous_anchor_are_rejected(tmp_path):
    s,*_=initialized(tmp_path)
    report={'narrative_markdown':'Unique gap. Repeated. Repeated.'}
    issue=dict(id='gap',section_ids=['cost','summary'],kind='missing_link',question='Net cost to procurement?',quote='Repeated.')
    with pytest.raises(WorkpaperConflict,match='unique_saved_passage'):
        s.authoring.open_issue(1,issue,report)
    issue['quote']='Unique gap.';s.authoring.open_issue(1,issue,report)
    wrong=dep(s,'root','competition')
    with pytest.raises(WorkpaperConflict,match='linked_result'):
        s.authoring.resolve('gap',1,'retained','Different task is not this investigation',[wrong],report)
    s.register('new','root','Followup')
    result=s.publish('new',0,paper(),{},'new',assignment={'authoring_issue_id':'gap','task_id':'actual'})
    ref={k:result[k] for k in ('topic_id','revision','digest')}|{'use':'qualified','rationale':'Current task result'}
    with pytest.raises(WorkpaperConflict,match='read_resolution'):
        s.authoring.resolve('gap',1,'retained','Unread result',[ref],report)
    assert s.authoring.context()['issues'][0]['status']=='open'


def test_new_issue_invalidates_bound_report_without_rewriting_understanding(tmp_path):
    s,*_=initialized(tmp_path)
    report={'narrative_markdown':'Summary. Cost. Competition.'}
    frozen=s.prepare('root',['cost','competition'],'Coverage')
    uses=[dict(section_id=k,excerpt=q) for k,q in [('summary','Summary.'),('cost','Cost.'),('competition','Competition.')]]
    digest=canonical_sha256(report)
    s.bind(frozen['snapshot_id'],digest,report=report,section_uses=uses)
    s.require_current_binding(digest)
    before=s.authoring.context()
    s.authoring.open_issue(1,dict(id='word',section_ids=['cost'],kind='expression',question='Define unit',quote='Cost.'),report)
    after=s.authoring.context()
    assert before['digest']==after['digest'] and before['context_generation']!=after['context_generation']
    with pytest.raises(WorkpaperConflict,match='resolve_authoring_issues'):
        s.require_current_binding(digest)
    assert s.authoring.report_map(digest)['judgments']==before['judgments']
    s.authoring.resolve('word',1,'retained','The following sentence already defines the unit',[],report)
    s.require_current_binding(digest)


def test_context_retirement_requires_new_current_same_scope_view(tmp_path):
    s,*_=initialized(tmp_path)
    old=s.authoring.context(['cost'])
    def msg(key,value):return ToolMessage(name='read_authoring_context',tool_call_id=key,content=json.dumps(value))
    s.authoring.update(1,dict(reason='New outline order',sections=[section('cost',['cost'],4)]),'u2')
    current=s.authoring.context(['cost'])
    m1,m2=msg('old',old),msg('new',current)
    assert not authoring_context_replacements([m1],[{'receipt_id':'old'}],current)
    replacement=authoring_context_replacements([m1,m2],[{'receipt_id':'old'}],current)[0]
    assert replacement['receipt']['result']['current_view_receipt_id']=='new'
    historical=msg('history',s.authoring.context(['cost'],revision=1))
    assert not authoring_context_replacements([historical,m2],[{'receipt_id':'history'}],current)
    assert s.authoring.context(revision=1)['judgments']['cost']['conditions']==old['judgments']['cost']['conditions']


def test_authorization_storage_failure_not_downgraded(tmp_path):
    s,*_=initialized(tmp_path)
    s.check=lambda:(_ for _ in ()).throw(PermissionError('Revoked'))
    with pytest.raises(PermissionError):s.authoring.context()


def test_new_understanding_cannot_use_empty_legacy_delivery_bypass(tmp_path):
    s=store(tmp_path)
    s.authoring.update(0,dict(reason='Initial hypothesis',judgments=[judgment('hypothesis')]),'first')
    with pytest.raises(WorkpaperConflict,match='bind_current_report'):
        s.require_current_binding('unknown-report')


def test_title_and_multiple_summary_passages_trace_to_same_judgment(tmp_path):
    s,*_=initialized(tmp_path)
    report={'title':'Overall title','narrative_markdown':'Summary. Cost. Competition. Conclusion.'}
    s.authoring.open_issue(1,dict(id='title',section_ids=['summary'],kind='thesis_conflict',
        question='Does title reflect the current conclusion?',quote='Overall title',field='title'),report)
    s.authoring.resolve('title',1,'retained','Title retains the same explicit scope',[],report)
    snapshot=s.prepare('root',['cost','competition'],'Current outline and title')
    uses=[dict(section_id=k,excerpt=q) for k,q in [('summary','Summary.'),('cost','Cost.'),('competition','Competition.'),('summary','Conclusion.')]]
    uses.append(dict(section_id='summary',field='title',excerpt='Overall title'))
    s.bind(snapshot['snapshot_id'],canonical_sha256(report),report=report,section_uses=uses)
    mapped=s.authoring.report_map(canonical_sha256(report))
    summaries=[row for row in mapped['sections'] if row['section_id']=='summary']
    assert len(summaries)==3 and all(row['basis']==summaries[0]['basis'] for row in summaries)


@pytest.mark.anyio
async def test_offline_authoring_handoffs(tmp_path):
    from scripts.engineering.replay_research_authoring import replay
    result=await replay(tmp_path)
    assert all(result['checks'].values())
    assert result['paid_model_calls']==0


@pytest.fixture
def anyio_backend():return 'asyncio'
