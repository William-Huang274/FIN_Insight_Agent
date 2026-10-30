"""Selection feedback continues natively; authority/storage faults remain fatal."""
import asyncio
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage

from sec_agent.agent_runtime.conversation_agent import build_conversation_agent, GrantedTool
from sec_agent.agent_runtime.organization_work_session import organization_source_tool
from sec_agent.research_foundation.organization_execution_access import (
    OrganizationAuthorizationUnavailable, OrganizationSourceStorageUnavailable,
    OrganizationSourceSelectionError)
from test_organization_source_navigation import navigation


def call(request, ident='selection'):
    return {'name': 'read_source_document', 'args': {'request': request}, 'id': ident, 'type': 'tool_call'}


def test_bad_document_feedback_preserves_proposal_and_requires_no_storage(navigation, monkeypatch):
    nav, state, _ = navigation
    monkeypatch.setattr(nav.reader.workspace, 'read_source', lambda *a: pytest.fail('invalid document touched storage'))
    tool = organization_source_tool(nav, nav.reader.check)
    proposal = call({'operation': 'search', 'document_id': 'ORGDOC::unknown:version', 'query': 'cash'})
    original = deepcopy(proposal)
    result = tool.invoke(proposal)
    body = json.loads(result.content)
    assert proposal == original and result.tool_call_id == 'selection'
    assert result.status == 'error' and result.artifact is None
    assert body['category'] == 'source_selection' and body['operation_executed'] is False
    assert body['stop_required'] is False and 'document_id' not in body['readback']['request']
    state['status'] = 403
    with pytest.raises(OrganizationAuthorizationUnavailable): tool.invoke(proposal)


def test_search_selection_rejected_before_index_loading(navigation, monkeypatch):
    nav, _, _ = navigation
    # The current grant is checked; no index, body, or provider is needed to
    # reject an ID absent from that fixed descriptor map.
    nav.hybrid = SimpleNamespace(load_frozen=lambda *a: pytest.fail('invalid selection loaded index'))
    with pytest.raises(OrganizationSourceSelectionError):
        nav.navigate({'source_space': 'organization', 'operation': 'search', 'query': 'cash',
                      'document_id': 'ORGDOC::unknown:version'})


@pytest.mark.parametrize('failure', [None, OrganizationAuthorizationUnavailable, OrganizationSourceStorageUnavailable])
def test_native_tool_feedback_or_stop_before_next_model(failure):
    checked = []
    def navigate(request):
        if failure: raise failure()
        if request.operation == 'search': raise OrganizationSourceSelectionError()
        return {'items': [{'document_id': 'ORGDOC::known:v1'}], 'operation': 'catalog'}
    tool = organization_source_tool(SimpleNamespace(navigate=navigate), lambda: checked.append(True))
    class Model(FakeMessagesListChatModel):
        def bind_tools(self, *a, **kw): return self
    model = Model(responses=[
        AIMessage(content='', tool_calls=[call({'operation': 'search', 'document_id': 'bad', 'query': 'cash'})]),
        AIMessage(content='', tool_calls=[call({'operation': 'catalog'}, 'catalog')]),
        AIMessage(content='I can now select the observed document.')])
    graph = build_conversation_agent(model=model, grants=[GrantedTool(tool, 'read', 'fixed')],
        permission_mode='request_standard', checkpointer=None, server_managed_persistence=True)
    async def run():
        if failure:
            with pytest.raises(failure) as exc: await graph.ainvoke({'messages': [('user', 'research')]})
            assert exc.value.feedback()['stop_required'] is True and model.i == 1
        else:
            result = await graph.ainvoke({'messages': [('user', 'research')]})
            messages = [m for m in result['messages'] if m.type == 'tool']
            assert [m.status for m in messages] == ['error', 'success']
            assert json.loads(messages[0].content)['category'] == 'source_selection'
            assert 'ORGDOC::known:v1' in messages[1].content
    asyncio.run(run())


@pytest.mark.parametrize('fault', ['missing', 'wrong_version', 'corrupt', 'denied'])
def test_reader_distinguishes_storage_from_authority(navigation, monkeypatch, fault):
    nav, _, _ = navigation
    reader = nav.reader
    resource = reader.catalog()['items'][0]['resource_id']
    read = reader.workspace.read_source
    def broken(*args):
        if fault == 'missing': raise FileNotFoundError('private path must not leak')
        if fault == 'denied':
            from sec_agent.research_foundation.project_asset_access import ProjectAssetUnavailable
            raise ProjectAssetUnavailable('private identity must not leak')
        if fault == 'corrupt': raise ValueError('body digest invalid')
        value = deepcopy(read(*args)); value['version']['ref']['version_id'] = 'wrong'; return value
    monkeypatch.setattr(reader.workspace, 'read_source', broken)
    expected = OrganizationAuthorizationUnavailable if fault == 'denied' else OrganizationSourceStorageUnavailable
    with pytest.raises(expected) as exc: reader.read_text(resource)
    assert 'private' not in str(exc.value) and exc.value.feedback()['stop_required'] is True


@pytest.mark.parametrize('failure', [OrganizationAuthorizationUnavailable, OrganizationSourceStorageUnavailable])
def test_fatal_feedback_is_retained_in_tool_audit(monkeypatch, failure):
    from sec_agent.agent_runtime.case_review_agent import CaseModelAudit
    monkeypatch.setattr('langgraph.config.get_stream_writer', lambda: lambda event: None)
    audit = object.__new__(CaseModelAudit)
    audit.actor, audit.stream_public, audit.events = 'research_partner', True, []
    audit.activity_sink = lambda event: None
    def access():
        if failure is OrganizationAuthorizationUnavailable: raise failure()
    audit.source_access_check = access
    async def execute(request):
        assert failure is OrganizationSourceStorageUnavailable
        raise failure('source_version_mismatch')
    with pytest.raises(failure):
        asyncio.run(audit.awrap_tool_call(SimpleNamespace(tool_call=call({'operation':'read'})), execute))
    assert audit.events[-1]['status'] == 'error'
    assert audit.events[-1]['source_failure']['category'] == failure.category
    assert audit.events[-1]['source_failure']['stop_required'] is True
