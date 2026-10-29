"""Actual organization capability schema, including the failed real call shapes."""
import asyncio
import json
import pytest
from pydantic import ValidationError
from langchain_core.tools import tool
from langchain_core.utils.function_calling import convert_to_openai_tool

from sec_agent.research_foundation.organization_source_request import OrganizationSourceRequest
from sec_agent.research_foundation.organization_source_navigation import build_organization_source_server
from sec_agent.research_foundation.source_document_navigation import SourceDocumentRequest
from test_organization_source_navigation import navigation


def test_model_schema_only_advertises_current_organization_capabilities():
    @tool
    def read_source_document(request: OrganizationSourceRequest):
        """Read execution-bound sources."""
        return request.model_dump(mode='json')
    schema = convert_to_openai_tool(read_source_document)['function']['parameters']['properties']['request']
    assert schema['properties']['source_space']['const'] == 'organization'
    assert schema['properties']['source_space']['default'] == 'organization'
    assert schema['properties']['operation']['enum'] == ['catalog', 'outline', 'search', 'read']
    assert schema['properties']['query']['maxLength'] == SourceDocumentRequest.model_json_schema()['properties']['query']['maxLength']
    assert not {'company_section','data_kind','page_start','include_domains'} & schema['properties'].keys()
    assert 'company/data/related require' not in json.dumps(schema)
    assert read_source_document.invoke({'request': {'operation':'catalog','query':'NVIDIA'}})['source_space']=='organization'


@pytest.mark.parametrize('space', ['local','library'])
def test_original_real_proposals_rejected_at_schema_without_remapping(navigation, space):
    # Exact two request bodies from the real first response; no handwritten fix.
    proposal = {'operation':'catalog','source_space':space,'query':'NVIDIA'}
    with pytest.raises(ValidationError, match="organization"):
        OrganizationSourceRequest.model_validate(proposal)
    assert proposal['source_space'] == space


def test_legacy_readback_and_shared_navigation_identity_preserved(navigation):
    nav, _, _ = navigation
    catalog = nav.navigate(OrganizationSourceRequest(operation='catalog'))
    document = catalog.items[0]['document_id']
    shared = SourceDocumentRequest(source_space='organization',operation='read',document_id=document)
    request = OrganizationSourceRequest.model_validate(shared.model_dump(mode='json'))
    before, after = nav.navigate(shared), nav.navigate(request)
    assert before.model_dump(mode='json') == after.model_dump(mode='json')
    assert OrganizationSourceRequest.model_validate(after.items[0]['readback']).source_space == 'organization'
    with pytest.raises(ValidationError, match='organization_parameter_not_available:page_start'):
        OrganizationSourceRequest(operation='read',document_id=document,page_start=1)


def test_mcp_uses_same_capability_view_and_executes_catalog(navigation):
    from mcp import Client
    nav, _, _ = navigation
    async def check():
        async with Client(build_organization_source_server(nav),raise_exceptions=False) as client:
            tools=await client.list_tools()
            source=next(t for t in tools.tools if t.name=='read_source_document')
            encoded=json.dumps(source.input_schema)
            assert 'company_section' not in encoded
            result=await client.call_tool('read_source_document',{'request':{'operation':'catalog','query':''}})
            assert not result.is_error
            assert result.structured_content['items'][0]['document_id'].startswith('ORGDOC::')
    asyncio.run(check())
