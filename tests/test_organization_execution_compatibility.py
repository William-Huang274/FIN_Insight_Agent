"""New scope options do not rewrite frozen organization commands or weaken ACL."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
import pytest

from sec_agent.agent_runtime import research_session_runtime as runtime
from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime.organization_native_contract import digest, validate_thread
from test_java_research_intake import intake
from test_organization_native_drafts import organization, prepare, state
from test_organization_data_composition import organization as organization_data
from test_organization_phase_factory import phases_for, invoke, forbid_host_data


@pytest.mark.parametrize('coverage',[None,False,True])
def test_prepare_and_restart_preserve_exact_command_shape_and_digest(organization,monkeypatch,coverage):
    s=organization
    execution=s.body['execution']
    execution['mode']='standard'
    if coverage is not None:execution['require_all_branches']=coverage
    s.grant['prepare_request_digest']='sha256:'+sha256(json.dumps(s.body,separators=(',',':')).encode()).hexdigest()
    before=deepcopy(s.grant)
    with TestClient(s.intake.app()) as client:
        response=prepare(client,s)
        assert response.status_code==200,response.text
        thread=s.intake.threads[s.grant['execution_id']]
        frozen=deepcopy(thread)
        wire=thread['metadata']['organization_run_configuration']['configurable']['finsight_execution']
        assert wire==execution and ('require_all_branches' in wire)==(coverage is not None)
        assert ExecutionOptions.model_validate(wire).require_all_branches is bool(coverage)
        checksum=thread['metadata']['configuration_digest']
        assert validate_thread(thread,s.grant)['configuration_digest']==checksum
        # Changed defaults/configuration must not be consulted for saved receipt reads.
        monkeypatch.setattr('apps.workbench.backend.organization_native_drafts.default_configuration',
            lambda:pytest.fail('Reconstructed a frozen configuration'))
        assert state(client,s).json()==response.json()
    with TestClient(s.intake.app()) as client:
        assert prepare(client,s).json()==response.json()
        assert s.intake.threads[s.grant['execution_id']]==frozen and s.grant==before
        assert s.state['creates']==1 and not s.intake.runs
    # Even semantically equivalent absent/false forms cannot silently alter a saved digest.
    changed=deepcopy(frozen)
    config=changed['metadata']['organization_run_configuration']
    changed_wire=config['configurable']['finsight_execution']
    if 'require_all_branches' in changed_wire:changed_wire.pop('require_all_branches')
    else:changed_wire['require_all_branches']=False
    changed['metadata']['configuration_digest']=digest(config)
    with pytest.raises(ValueError,match='organization_prepared_thread_mismatch'):validate_thread(changed,s.grant)


@pytest.mark.parametrize('value',[None,'false','true',0,1,[],{}])
def test_new_coverage_field_rejects_scalar_coercion(value):
    with pytest.raises(ValueError):ExecutionOptions(mode='standard',require_all_branches=value)


@pytest.mark.parametrize('mode',['auto','selected','single'])
def test_full_catalog_is_never_an_implicit_nonstandard_scope(mode):
    with pytest.raises(ValueError):ExecutionOptions(mode=mode,branch_ids=['Q1'] if mode!='auto' else [],require_all_branches=True)


def test_deferred_factory_preserves_authority_and_refuses_mid_run_scope_change(monkeypatch):
    sentinel,check=object(),lambda:None
    calls=[]
    def bound(**kwargs):
        assert kwargs['organization_data_factory'] is sentinel and kwargs['run_access_check'] is check
        calls.append(kwargs['execution'])
        return {'research':RunnableLambda(lambda state:state),'writer':RunnableLambda(lambda state:state)}
    monkeypatch.setattr(runtime,'_create_bound_research_phases',bound)
    phases=runtime.create_research_phase_runnables(organization_data_factory=sentinel,run_access_check=check)
    old={'configurable':{'finsight_execution':{'mode':'standard'}}}
    explicit={'configurable':{'finsight_execution':{'mode':'standard','require_all_branches':False}}}
    asyncio.run(phases['research'].ainvoke({},old));asyncio.run(phases['writer'].ainvoke({},explicit))
    assert len(calls)==1
    with pytest.raises(ValueError,match='changed_within_run'):
        asyncio.run(phases['writer'].ainvoke({}, {'configurable':{'finsight_execution':{'mode':'standard','require_all_branches':True}}}))
    assert len(calls)==1


def test_revocation_between_factory_creation_and_first_invoke_stops_before_provider(organization_data,tmp_path):
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    factory,authority=organization_data
    phases=phases_for(factory,tmp_path)
    authority['status']=404
    with pytest.raises(OrganizationExecutionUnavailable):invoke(phases,'research',{'question':'No provider after revocation'})


@pytest.mark.parametrize('cross_topic',[False,True])
def test_open_topic_assignment_keeps_organization_source_scope(organization_data,cross_topic):
    from test_organization_data_composition import specialist
    from test_lead_research_graph import _task
    from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
    from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
    factory,authority=organization_data
    task=_task()
    task['coverage_obligation_ids']=[b.branch_id for b in factory.foundation.question_branches[:2]] if cross_topic else []
    task['requested_capability_refs']=['capability:research:source-document-read']
    with specialist(factory,research_task=task) as opened:
        assert opened.graph_input.task.objective==task['objective']
        assert opened.graph_input.model_dump(mode='json')['task_context']['assignment']['coverage_obligation_ids']==task['coverage_obligation_ids']
        result=opened.source_reader(SourceDocumentRequest(source_space='organization',operation='catalog'))
        document=next(r['document_id'] for r in result['items'] if r.get('document_id'))
        original=opened.source_reader(SourceDocumentRequest(source_space='organization',operation='read',document_id=document))
        passage=next(r for r in original['items'] if r.get('result_state')=='source_bound_passage')
        assert passage['passage']=='Pinned original evidence.'
        assert original['snapshot_id']==factory.reader.authority.manifest_digest
        assert opened.source_reader(SourceDocumentRequest(source_space='library',operation='catalog'))['status']=='tool_failure'
        authority['status']=404
        with pytest.raises(OrganizationExecutionUnavailable):
            opened.source_reader(SourceDocumentRequest(source_space='organization',operation='read',document_id=document))
