"""Delivery shape, frozen wire compatibility and executor admission; no provider."""
import asyncio
from copy import deepcopy
from hashlib import sha256
import json
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from langchain_core.runnables import RunnableLambda
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
import pytest

from sec_agent.agent_runtime.execution_options import ExecutionOptions
from sec_agent.agent_runtime import research_session_runtime as runtime
from sec_agent.agent_runtime.research_session import build_research_session_graph
from sec_agent.agent_runtime.report_session import build_report_session_graph, report_session_graph
from sec_agent.agent_runtime.organization_native_contract import digest, validate_thread
from sec_agent.agent_runtime.task_outcome import task_outcome, public_task_outcome
from test_task_outcome import result_fixture
from test_java_research_intake import intake
from test_organization_native_drafts import organization, prepare, state


@pytest.mark.parametrize('intent', [None, 'report', 'answer', 'workpaper'])
@pytest.mark.parametrize('mode', ['standard', 'auto', 'selected', 'single'])
def test_intent_is_independent_of_actor_selection_and_preserves_omission(intent, mode):
    wire = {'mode': mode, 'branch_ids': ['Q1'] if mode in {'selected', 'single'} else []}
    if intent is not None:
        wire['delivery_intent'] = intent
    original = deepcopy(wire)
    options = ExecutionOptions.model_validate(wire)
    assert options.delivery_intent == (intent or 'report')
    assert options.model_dump(exclude_unset=True) == original == wire
    assert ('delivery_intent' in options.model_dump()) == (intent is not None)
    assert ('delivery_intent' in json.loads(options.model_dump_json())) == (intent is not None)
    assert ExecutionOptions.model_validate(options.model_dump()) == options


@pytest.mark.parametrize('value', [None, '', 'memo', True, 0, [], {}])
def test_explicit_invalid_intent_is_not_a_default_report(value):
    with pytest.raises(ValueError):
        ExecutionOptions(delivery_intent=value)


def test_intent_schema_matches_supported_json_values():
    schema = ExecutionOptions.model_json_schema()
    field = schema['properties']['delivery_intent']
    assert field['type'] == 'string' and field['enum'] == ['answer', 'workpaper', 'report']
    assert 'delivery_intent' not in schema.get('required', [])


@pytest.mark.parametrize('intent', [None, 'report'])
def test_organization_freeze_and_receipt_replay_preserve_exact_intent(organization, monkeypatch, intent):
    # The Java HTTP boundary is simulated by its existing authority fixture.
    # This checks BFF freezing, not Java admission of the new field.
    s = organization
    if intent is not None:
        s.body['execution']['delivery_intent'] = intent
    s.grant['prepare_request_digest'] = 'sha256:' + sha256(json.dumps(s.body, separators=(',', ':')).encode()).hexdigest()
    original = deepcopy(s.grant)
    with TestClient(s.intake.app()) as client:
        response = prepare(client, s)
        assert response.status_code == 200, response.text
        saved = deepcopy(s.intake.threads[s.grant['execution_id']])
        configured = saved['metadata']['organization_run_configuration']
        assert configured['configurable']['finsight_execution'] == s.body['execution']
        assert validate_thread(saved, s.grant)['configuration_digest'] == digest(configured)
        monkeypatch.setattr('apps.workbench.backend.organization_native_drafts.default_configuration',
            lambda: pytest.fail('Frozen receipt reconstructed using current defaults'))
        assert state(client, s).json() == response.json()
    with TestClient(s.intake.app()) as client:
        assert prepare(client, s).json() == response.json()
    assert s.state['creates'] == 1 and not s.intake.runs
    assert s.grant == original and s.intake.threads[s.grant['execution_id']] == saved
    altered = deepcopy(saved)
    config = altered['metadata']['organization_run_configuration']
    wire = config['configurable']['finsight_execution']
    if intent is None:
        wire['delivery_intent'] = 'report'
    else:
        wire.pop('delivery_intent')
    altered['metadata']['configuration_digest'] = digest(config)
    with pytest.raises(ValueError, match='organization_prepared_thread_mismatch'):
        validate_thread(altered, s.grant)


@pytest.mark.parametrize('intent', ['answer', 'workpaper'])
def test_organization_rejects_unsupported_delivery_before_native_creation(organization, intent):
    s = organization
    s.body['execution']['delivery_intent'] = intent
    s.grant['prepare_request_digest'] = 'sha256:' + sha256(json.dumps(s.body, separators=(',', ':')).encode()).hexdigest()
    with TestClient(s.intake.app()) as client:
        response = prepare(client, s)
    assert response.status_code == 422, response.text
    assert 'delivery_intent_not_supported_by_report_workflow' in response.text
    assert s.state['creates'] == 0 and not s.intake.threads and not s.intake.runs


@pytest.mark.parametrize('intent', ['answer', 'workpaper'])
def test_personal_intake_rejects_unsupported_delivery_before_persistence(intake, intent):
    from test_java_research_intake import payload, request
    body = payload(intake)
    body['session']['execution'] = {'delivery_intent': intent}
    with TestClient(intake.app()) as client:
        response = request(client, 'prepare', body)
    assert response.status_code == 422, response.text
    assert 'delivery_intent_not_supported_by_report_workflow' in response.text
    assert not intake.threads and not intake.runs
    assert not intake.library.index('oidc:alice')['assignments']


@pytest.mark.parametrize('intent', ['answer', 'workpaper'])
def test_report_factories_refuse_unsupported_intent_before_opening_resources(monkeypatch, intent):
    monkeypatch.setattr(runtime, '_create_bound_research_phases',
        lambda **kwargs: pytest.fail('Opened report resources for unsupported delivery'))
    config = {'configurable': {'finsight_execution': {'delivery_intent': intent}}}
    phases = runtime.create_research_phase_runnables()
    for role in ('research', 'review', 'converge', 'writer', 'revise_research'):
        with pytest.raises(ValueError, match='delivery_intent_not_supported_by_report_workflow'):
            asyncio.run(phases[role].ainvoke({}, config))
    async def open_legacy_report():
        async with report_session_graph(config, SimpleNamespace(execution_runtime=True)):
            pytest.fail('Opened legacy report factory')
    with pytest.raises(ValueError, match='delivery_intent_not_supported_by_report_workflow'):
        asyncio.run(open_legacy_report())


@pytest.mark.parametrize('intent', [None, 'report'])
def test_report_factory_retains_legacy_and_explicit_report_without_changing_options(monkeypatch, intent):
    seen = []
    def bind(**kwargs):
        seen.append(kwargs['execution'].model_dump())
        return {'research': RunnableLambda(lambda value: value)}
    monkeypatch.setattr(runtime, '_create_bound_research_phases', bind)
    wire = {} if intent is None else {'delivery_intent': intent}
    value = asyncio.run(runtime.create_research_phase_runnables()['research'].ainvoke(
        {'existing': 'materials'}, {'configurable': {'finsight_execution': wire}}))
    assert value == {'existing': 'materials'} and len(seen) == 1
    assert ('delivery_intent' in seen[0]) == (intent is not None)


@pytest.mark.parametrize('intent', ['answer', 'workpaper'])
def test_native_research_entry_does_not_silently_generate_report(intent):
    def forbidden(value):
        pytest.fail('A report phase ran for a different deliverable')
    phases = {k: RunnableLambda(forbidden) for k in ('research', 'review', 'converge', 'writer', 'verifier')}
    graph = build_research_session_graph(**phases).compile()
    with pytest.raises(ValueError, match='delivery_intent_not_supported_by_report_workflow'):
        asyncio.run(graph.ainvoke({'question': 'Only return the requested deliverable.'},
            {'configurable': {'finsight_execution': {'delivery_intent': intent}}}))


@pytest.mark.parametrize('in_action', [False, True])
def test_saved_report_cannot_resume_as_an_unimplemented_delivery(in_action):
    initial = {'report': {'title': 'Saved report'}, 'report_review': {'findings': []}, 'revisions': {}}
    def forbidden(value):
        pytest.fail('Unexpected model or artifact rewrite')
    graph = build_report_session_graph(writer=RunnableLambda(forbidden), verifier=RunnableLambda(forbidden),
        artifacts=None, initial=initial).compile(checkpointer=InMemorySaver())
    config = {'configurable': {'thread_id': str(uuid4())}}
    opened = asyncio.run(graph.ainvoke({'open': True}, config))
    assert '__interrupt__' in opened
    changed = {'configurable': {**config['configurable'], 'finsight_execution': {'delivery_intent': 'workpaper'}}}
    action = {'action': 'revise', 'message': 'A local edit'}
    if in_action:
        changed = config
        action['execution'] = {'delivery_intent': 'workpaper'}
    with pytest.raises(ValueError, match='delivery_intent_not_supported_by_report_workflow'):
        asyncio.run(graph.ainvoke(Command(resume=action), changed))
    assert graph.get_state(config).values['report'] == initial['report']


def test_actual_artifact_kind_does_not_claim_request_completion_or_review():
    value, assignment = result_fixture()
    outcome = task_outcome(value, assignment=assignment)
    assert outcome['artifact_kind'] == 'workpaper'
    assert outcome['artifact_status'] == 'submitted'
    assert outcome['author_note']['coverage'][0]['status'] == 'partial'
    assert outcome['review_status'] == 'not_assessed_in_this_record'
    legacy = {k: v for k, v in outcome.items() if k != 'artifact_kind'}
    assert public_task_outcome(legacy) == legacy
    assert public_task_outcome(outcome) == outcome
    assert public_task_outcome({**outcome, 'artifact_kind': 'unknown'}) is None
    original_digest = outcome['artifact_digest']
    candidate = deepcopy(value)
    candidate.update(phase='specialist_human_review_handoff_emitted', final_submission=None,
        last_submission_attempt={'arguments': value['final_submission']})
    projected = task_outcome(candidate, assignment=assignment)
    assert projected['artifact_kind'] == 'workpaper' and projected['artifact_status'] == 'candidate'
    assert projected['artifact_digest'] == original_digest
    empty = task_outcome({}, assignment=assignment, error_type='Interrupted')
    assert empty['artifact_status'] == 'none' and 'artifact_kind' not in empty
