"""Organization originals -> maintained source/citation/calculator tools, no providers."""
import asyncio
from copy import deepcopy
from uuid import uuid4

import pytest

from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation, build_organization_source_server
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable, OrganizationSourceSelectionError
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from sec_agent.research_foundation.source_bound_calculator import SourceBoundCalculation, source_items_from_tool
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_at, runtime_grant
from test_model_dispatch_guard import boundary, response


@pytest.fixture
def navigation(tmp_path):
    shared, preparation = fixture(tmp_path)
    grant = runtime_grant(preparation)
    reader, state = runtime_at(shared, grant)
    return OrganizationSourceNavigation(reader, workbench_url='https://workbench.example.test'), state, shared


def request(operation, **kwargs):
    return SourceDocumentRequest(source_space='organization', operation=operation, **kwargs)


def read_first(nav):
    document = nav.navigate(request('catalog')).items[0]['document_id']
    return nav.navigate(request('read', document_id=document))


def test_original_citation_roundtrip_has_version_identity_and_no_preview_authority(navigation, monkeypatch):
    nav, _, _ = navigation
    monkeypatch.setenv('FINSIGHT_SOURCE_HYBRID', '1')
    import retrieval.source_hybrid as hybrid
    monkeypatch.setattr(hybrid, 'rank_sources', lambda *a, **k: pytest.fail('private originals must not reach embedding or rerank'))
    catalog = nav.navigate(request('catalog'))
    document = catalog.items[0]['document_id']
    assert document.startswith('ORGDOC::') and not catalog.items[0]['writer_citable']
    found = nav.navigate(request('search', query='Pinned', document_id=document))
    assert found.items and not source_items_from_tool('read_source_document', found.model_dump(mode='json'))
    read = nav.navigate(found.items[0]['readback'])
    passage = read.items[0]
    assert passage['passage'] == 'Pinned original evidence.'
    assert passage['writer_citable'] and not passage['numeric_fact_authority']
    assert passage['organization_source']['ref'] == nav.reader.catalog()['items'][0]['ref']
    assert '/organization-projects/' in passage['source_url']
    assert nav.source(passage['passage_id']) == passage
    assert source_items_from_tool('read_source_document', read.model_dump(mode='json'))[passage['passage_id']] == passage
    assert read.source_snapshot_sha256 == nav.reader.authority.manifest_digest[7:]


@pytest.mark.parametrize('space', ['local', 'uploads', 'library', 'web'])
def test_other_source_spaces_never_fall_through_to_host(navigation, space):
    nav, state, shared = navigation
    calls = state['calls']
    with pytest.raises(ValueError): nav.navigate(SourceDocumentRequest(source_space=space, operation='search', query='secret'))
    assert state['calls'] == calls


def test_foreign_document_node_and_page_do_not_resolve_by_guessing(navigation):
    nav, _, _ = navigation
    document = nav.navigate(request('catalog')).items[0]['document_id']
    with pytest.raises(OrganizationSourceSelectionError):
        nav.navigate(request('read', document_id='ORGDOC::' + str(uuid4())))
    with pytest.raises(ValueError, match='source_node_not_in_selected_document'):
        nav.navigate(request('read', document_id=document, node_id='ORGSECTION::foreign'))
    with pytest.raises(ValueError, match='no_pdf_page_locator'):
        nav.navigate(request('read', document_id=document, page_start=1))
    with pytest.raises(ValueError, match='not_observed'):
        nav.source('PASSAGE::another-session')


def test_source_identity_changes_with_publication_version(navigation):
    nav, _, _ = navigation
    original = nav.reader.catalog()['items'][0]
    changed = deepcopy(original)
    changed['ref']['version_id'] = 'UPLOAD::' + uuid4().hex
    assert nav._identity(original) != nav._identity(changed)


def test_character_window_and_projection_truncation_remain_explicit(navigation, monkeypatch):
    nav, _, _ = navigation
    read = nav.reader.workspace.read_source
    def longer(*args):
        return {**read(*args), 'text': 'Revenue 123.40 USD; period 2025. ' * 300, 'truncated': True}
    monkeypatch.setattr(nav.reader.workspace, 'read_source', longer)
    document = nav.navigate(request('catalog')).items[0]['document_id']
    outlined = nav.navigate(request('outline', document_id=document))
    assert len(outlined.items) == 2
    first = nav.navigate(request('read', document_id=document, max_characters=2000)).items[0]
    assert first['read_status'] == 'window_required' and not first['writer_citable']
    window = nav.navigate(first['readback']).items[0]
    assert window['truncated'] and window['organization_source']['source_truncated']
    assert window['source_locator']['character_start'] == 0 and len(window['passage']) == 2000
    assert nav.source(window['passage_id']) == window
    adjacent = nav.navigate(window['next_readback']).items[0]
    assert adjacent['source_locator']['character_start'] == 2000
    assert adjacent['passage_id'] != window['passage_id']


def test_citation_readback_blocks_revocation_and_original_corruption(navigation, monkeypatch):
    nav, state, shared = navigation
    passage = read_first(nav).items[0]
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable): nav.source(passage['passage_id'])
    state['status'] = 200
    get = shared.workspace.library.documents.get
    monkeypatch.setattr(shared.workspace.library.documents, 'get', lambda *a, **k: {**get(*a, **k), 'body': b'corrupt'})
    with pytest.raises(OrganizationExecutionUnavailable): nav.source(passage['passage_id'])


def test_real_mcp_and_existing_langchain_adapter_consume_scoped_tools(navigation):
    from mcp import Client
    from sec_agent.agent_runtime.case_review_agent import organization_source_tools
    nav, state, _ = navigation
    async def exercise():
        async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
            tools = {tool.name: tool for tool in await organization_source_tools(client)}
            assert set(tools) == {'read_source_document', 'read_research_source', 'calculate_research_metric'}
            catalog = await client.call_tool('read_source_document', {'request': {'source_space': 'organization', 'operation': 'catalog'}})
            assert not catalog.is_error, catalog
            document = catalog.structured_content['items'][0]['document_id']
            raw = await tools['read_source_document'].ainvoke({'request': {'source_space': 'organization', 'operation': 'read', 'document_id': document}})
            assert 'Pinned original evidence.' in str(raw)
            passage = read_first(nav).items[0]
            raw = await tools['read_research_source'].ainvoke({'source_id': passage['passage_id']})
            assert 'Pinned original evidence.' in str(raw)
            state['status'] = 404
            revoked = await client.call_tool('read_research_source', {'source_id': passage['passage_id']})
            assert revoked.is_error and 'Pinned original evidence.' not in str(revoked)
    asyncio.run(exercise())


def test_calculation_remains_source_bound_and_revocation_blocks_cached_results(navigation, monkeypatch):
    nav, state, _ = navigation
    read = nav.reader.workspace.read_source
    monkeypatch.setattr(nav.reader.workspace, 'read_source', lambda *args: {**read(*args), 'text': 'Revenue 123.40 USD in 2025.'})
    source = read_first(nav).items[0]['passage_id']
    calc = SourceBoundCalculation(expression='revenue * 2', operands={'revenue': {'source_id': source,
        'quote': 'Revenue 123.40 USD in 2025.', 'literal': '123.40'}}, result_unit='USD', rationale='Synthetic arithmetic only')
    result = nav.calculate(calc)
    assert result['value_decimal'] == '246.80' and not result['financial_semantics_verified']
    assert nav.source(result['calculation_id']) == result
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable): nav.calculate(calc)
    with pytest.raises(OrganizationExecutionUnavailable): nav.source(result['calculation_id'])


def test_read_then_revoke_blocks_next_existing_model_boundary(navigation, boundary):
    nav, state, _ = navigation
    assert read_first(nav).items
    boundary.audit.source_access_check = nav.reader.check
    sent = []
    async def provider(request):
        sent.append(True)
        return response()
    asyncio.run(boundary.audit.awrap_model_call(boundary.request, provider))
    reserved = boundary.store.reserve.call_count
    state['status'] = 404
    with pytest.raises(OrganizationExecutionUnavailable):
        asyncio.run(boundary.audit.awrap_model_call(boundary.request, provider))
    assert sent == [True] and boundary.store.reserve.call_count == reserved


def test_native_langgraph_agent_reads_original_with_scripted_model(navigation):
    """Actual framework loop and MCP tools; scripted replies are not research quality."""
    import json
    from langchain.agents import create_agent
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult
    from mcp import Client
    from sec_agent.agent_runtime.case_review_agent import organization_source_tools
    nav, _, _ = navigation
    class ScriptedReader(BaseChatModel):
        @property
        def _llm_type(self): return 'static-organization-navigation-fixture'
        def bind_tools(self, tools, **kwargs):
            assert {t.name for t in tools} == {'read_source_document', 'read_research_source', 'calculate_research_metric'}
            return self
        def _generate(self, messages, stop=None, run_manager=None, **kwargs):
            observed = [m for m in messages if isinstance(m, ToolMessage)]
            if not observed:
                args = {'source_space': 'organization', 'operation': 'catalog'}
            elif len(observed) == 1:
                args = {'source_space': 'organization', 'operation': 'read',
                    'document_id': json.loads(observed[-1].content)['items'][0]['document_id']}
            else:
                passage = json.loads(observed[-1].content)['items'][0]
                assert passage['passage'] == 'Pinned original evidence.' and passage['writer_citable']
                return ChatResult(generations=[ChatGeneration(message=AIMessage(content='Static source read: ' + passage['passage_id']))])
            return ChatResult(generations=[ChatGeneration(message=AIMessage(content='', tool_calls=[{
                'name': 'read_source_document', 'args': {'request': args}, 'id': 'read-' + str(len(observed)), 'type': 'tool_call'}]))])
    async def exercise():
        async with Client(build_organization_source_server(nav), raise_exceptions=False) as client:
            graph = create_agent(ScriptedReader(), tools=await organization_source_tools(client))
            result = await graph.ainvoke({'messages': [HumanMessage(content='Static original reading only.')]})
            assert result['messages'][-1].content.startswith('Static source read: PASSAGE::ORGSECTION::')
            assert len([m for m in result['messages'] if isinstance(m, ToolMessage)]) == 2
    asyncio.run(exercise())


def test_separate_organization_sessions_do_not_share_observations(navigation, tmp_path):
    nav, _, _ = navigation
    first = read_first(nav).items[0]
    shared, preparation = fixture(tmp_path / 'another')
    reader, _ = runtime_at(shared, runtime_grant(preparation))
    other = OrganizationSourceNavigation(reader, workbench_url='https://workbench.example.test')
    with pytest.raises(ValueError, match='not_observed'): other.source(first['passage_id'])
    with pytest.raises(OrganizationSourceSelectionError): other.navigate(first['readback'])


def test_permission_change_after_navigation_drops_entire_response(navigation, monkeypatch):
    nav, state, _ = navigation
    original = nav.reader._after
    def revoked(before):
        state['status'] = 404
        return original(before)
    monkeypatch.setattr(nav.reader, '_after', revoked)
    with pytest.raises(OrganizationExecutionUnavailable): nav.navigate(request('catalog'))



def test_mid_projection_revocation_cannot_publish_observations(navigation, monkeypatch):
    nav, state, _ = navigation
    document = nav.navigate(request('catalog')).items[0]['document_id']
    read = nav.reader.workspace.read_source
    published = []
    def revoke_after_storage(*args):
        result = read(*args)
        state['status'] = 404
        return result
    monkeypatch.setattr(nav.reader.workspace, 'read_source', revoke_after_storage)
    monkeypatch.setattr(nav.observed, 'remember', lambda *args, **kwargs: published.append(args))
    with pytest.raises(OrganizationExecutionUnavailable):
        nav.navigate(request('read', document_id=document))
    assert published == []


def test_catalog_never_reads_or_projects_originals(navigation, monkeypatch):
    nav, _, _ = navigation
    def forbidden(*a, **k): raise AssertionError('catalog read original')
    monkeypatch.setattr(nav.reader, '_read_storage', forbidden)
    monkeypatch.setattr(nav.reader, '_project_sources', forbidden)
    result = nav.navigate(request('catalog'))
    assert result.items and result.items[0]['readback']['operation'] == 'outline'
    assert not result.items[0]['writer_citable']


def test_published_catalog_missing_never_scans(navigation, monkeypatch, tmp_path):
    from types import SimpleNamespace
    nav, _, _ = navigation
    original = nav.reader._grant
    def grant():
        before, manifest, bindings = original()
        manifest = deepcopy(manifest); manifest['retrieval_index'] = {'release_id':'test'}
        return before, manifest, bindings
    monkeypatch.setattr(nav.reader, '_grant', grant)
    monkeypatch.setattr(nav.reader, '_read_storage', lambda *a: pytest.fail('read original'))
    nav.hybrid = SimpleNamespace(root=tmp_path)
    with pytest.raises(ValueError, match='document_catalog_not_published'):
        nav.navigate(request('catalog'))
    from sec_agent.research_foundation.organization_document_catalog import publish
    _, manifest, _ = grant()
    descriptors = {i['resource_id']:{'ref':i['ref'], 'original_metadata':{'company_name':'Example Corp'}} for i in manifest['inputs']}
    publish(tmp_path, manifest, descriptors)
    result = nav.navigate(request('catalog', query='Example'))
    assert result.total_matches == len(descriptors)
    assert nav.navigate(request('catalog', query='missing')).total_matches == 0
