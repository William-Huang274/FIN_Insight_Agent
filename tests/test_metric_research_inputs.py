"""Published metric cards: cutoff-bound native text/rows, no model transport."""
from copy import deepcopy
from datetime import date, timedelta
from uuid import uuid4
from hashlib import sha256
import json

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from test_metric_card_capture import capture_app, foundation
from test_organization_research_inputs import fixture
from test_organization_execution_access import runtime_at, runtime_grant
from test_project_research_materials import WRITE
from test_java_research_intake import intake
from test_organization_native_drafts import organization, prepare
from sec_agent.research_foundation.asset_workspace import AssetConflict
from sec_agent.research_foundation.project_source_captures import validate_metric_cutoff
from sec_agent.research_foundation.organization_execution_access import OrganizationExecutionUnavailable
from sec_agent.research_foundation.organization_source_navigation import OrganizationSourceNavigation
from apps.workbench.backend.organization_research_inputs import verify_storage


@pytest.fixture
def published_card(tmp_path, capture_app):
    client, workspace, project, card, _, _ = capture_app
    response = client.post('/api/v1/asset-workspace/captures', headers=WRITE, json={
        'project_id':project,'title':'Calculation card','selection':card['capture_selection']})
    assert response.status_code == 200, response.text
    ref = next(a['current']['ref'] for a in workspace.catalog('local-pilot',project)['items']
               if a['current']['ref']['version_id']==response.json()['document_id'])
    shared, preparation = fixture(tmp_path/'organization')
    item = preparation['manifest']['inputs'][0]
    resource = str(uuid4())
    binding = shared.publish(workspace, 'local-pilot', resource, preparation['organization_id'], item['space_id'], ref)
    item.update(resource_id=resource, resource_type='database', ref=deepcopy(binding['ref']))
    preparation['inputs'] = [{'resource_id':resource,'binding':binding}]
    return shared, preparation, card['items'][0]


def test_cutoff_blocks_preparation_and_native_reads_without_filtering_saved_rows(published_card):
    shared, preparation, card = published_card
    cutoff = (date.fromisoformat(card['available_at'])-timedelta(days=1)).isoformat()
    preparation['manifest']['research_as_of'] = cutoff
    with pytest.raises(HTTPException) as error:
        verify_storage(shared, preparation['organization_id'], preparation['inputs'], cutoff)
    assert error.value.status_code == 409 and '可获知日' in error.value.detail
    reader, _ = runtime_at(shared, runtime_grant(preparation))
    resource = preparation['inputs'][0]['resource_id']
    for read in (reader.read_rows, reader.read_text):
        with pytest.raises(OrganizationExecutionUnavailable):
            read(resource)
    # Historical research rejection does not revoke the published reference.
    assert shared.workspace.read('organization:'+preparation['organization_id'],
        preparation['inputs'][0]['binding']['ref'])['capture']['rows'] == [card]


def test_available_on_cutoff_card_enters_native_navigation_as_original_bytes(published_card):
    shared, preparation, card = published_card
    preparation['manifest']['research_as_of'] = card['available_at']
    verify_storage(shared, preparation['organization_id'], preparation['inputs'], card['available_at'])
    reader, _ = runtime_at(shared, runtime_grant(preparation))
    resource = preparation['inputs'][0]['resource_id']
    version, stored = shared.workspace.resolve('organization:'+preparation['organization_id'],
                                               preparation['inputs'][0]['binding']['ref'])
    assert reader.read_rows(resource)['rows'] == [card]
    text = reader.read_text(resource,limit=16000)
    assert text['text'] == stored['body'].decode()
    assert text['version']['ref'] == version['ref']
    navigation = OrganizationSourceNavigation(reader, workbench_url='http://127.0.0.1:9')
    result = navigation.navigate({'source_space':'organization','operation':'read',
        'document_id':navigation._identity(preparation['manifest']['inputs'][0]),'limit':20})
    assert result.items
    assert any(card['id'] in item['passage'] for item in result.items)
    assert not result.numeric_fact_authority


@pytest.mark.parametrize('fault', ['future', 'missing', 'invalid', 'input', 'nested_input'])
def test_metric_availability_dates_cannot_be_replaced_by_period_or_query_date(fault):
    row = {'available_at':'2026-07-29', 'period_end':'2026-06-30'}
    if fault == 'future': row['available_at']='2026-08-01'
    if fault == 'missing': del row['available_at']
    if fault == 'invalid': row['available_at']='2026-99-99'
    if fault == 'input': row['inputs']=[{'available_at':'2026-08-01'}]
    if fault == 'nested_input': row['inputs']=[{'components':[{'filed_at':'2026-08-01'}]}]
    with pytest.raises(AssetConflict):
        validate_metric_cutoff({'query':{'kind':'metric_cards','as_of':'2026-06-01'},'rows':[row]}, '2026-07-29')


def test_forward_guidance_is_allowed_when_disclosed_by_cutoff():
    validate_metric_cutoff({'query':{'kind':'metric_cards','as_of':'9999-12-31'},
        'rows':[{'available_at':'2026-07-29','value_state':'guidance','period_end':'2027-03-31'}]}, '2026-07-29')
    # No invented dating authority for unstructured uploaded evidence.
    validate_metric_cutoff({'kind':'library'}, '2026-07-29')


def test_native_preparation_rejects_future_card_before_creating_thread(organization, capture_app):
    s = organization
    client, workspace, project, card, _, _ = capture_app
    response = client.post('/api/v1/asset-workspace/captures',headers=WRITE,json={
        'project_id':project,'title':'Future to this research','selection':card['capture_selection']})
    assert response.status_code == 200
    ref = next(a['current']['ref'] for a in workspace.catalog('local-pilot',project)['items']
               if a['current']['ref']['version_id']==response.json()['document_id'])
    manifest = json.loads(s.grant['manifest_text'])
    item = manifest['inputs'][0]
    resource = str(uuid4())
    binding = s.shared.publish(workspace,'local-pilot',resource,s.grant['organization_id'],item['space_id'],ref)
    item.update(resource_id=resource,resource_type='database',ref=binding['ref'])
    manifest['research_as_of']='2020-01-01'
    s.grant['manifest_text']=json.dumps(manifest,separators=(',',':'))
    digest='sha256:'+sha256(s.grant['manifest_text'].encode()).hexdigest()
    s.grant['manifest_digest']=s.body['manifest_digest']=digest
    s.grant['inputs']=[{'resource_id':resource,'binding':binding}]
    s.grant['prepare_request_digest']='sha256:'+sha256(json.dumps(s.body,separators=(',',':')).encode()).hexdigest()
    with TestClient(s.intake.app()) as browser:
        response=prepare(browser,s)
        assert response.status_code == 409 and '可获知日' in response.text
    assert s.state['creates'] == 0 and not s.intake.threads and not s.intake.runs
