import asyncio
from copy import deepcopy
import json
import pytest

from langchain_core.messages import AIMessage, ToolMessage

from test_case_review_agent import artifacts, call
from test_report_synthesis_agent import NativeFixtureModel
from sec_agent.agent_runtime.report_authoring import authoring_catalog, research_handoff, report_authoring_input
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent, report_citations
from sec_agent.agent_runtime.model_context import deduplicate_read_results


def test_handoff_is_lossless_for_claim_meaning_and_keeps_original_readback(artifacts):
    paper = artifacts.read_paper('P01')
    before = deepcopy(paper)
    view = research_handoff(artifacts, 'P01')
    rows = {c['citation_id']: c for group in ('facts', 'interpretations', 'limitations') for c in view[group]}
    assert len(rows) == len(paper['claims'])
    for claim in paper['claims']:
        row = rows['P01:' + claim['claim_id']]
        assert row['statement'] == claim['statement']
        assert row.get('authority_note') == claim.get('authority_note')
        assert row['source_ids'] == claim['source_ids']
        report_citations('[' + row['citation_id'] + ']', artifacts)
    assert view['open_gaps'] == paper['open_gaps']
    assert view['counterevidence'] == paper['counterevidence']
    assert artifacts.read_paper('P01') == before
    catalog = authoring_catalog(artifacts)
    assert 'semantic_review_required' not in json.dumps(catalog)
    assert 'NOT a verified report' not in json.dumps(catalog)
    assert view['version'] == catalog['papers'][0]['version']


def test_fresh_report_and_local_review_have_different_inputs(artifacts):
    body = report_authoring_input('Original question', artifacts)
    assert set(body) == {'question', 'research_as_of', 'catalog', 'authoring_view'}
    report = {'title': 'Current report', 'narrative_markdown': 'Preserve existing argument'}
    review = {'summary': 'OLD REVIEW LOG', 'findings': [{'finding_id': 'F1', 'requested_change': 'Fix period'}],
        'unresolved_data_requests': ['Read the exact period']}
    edited = report_authoring_input('Original question', artifacts, report=report, review=review)
    assert edited['report']['narrative_markdown'] == report['narrative_markdown']
    assert 'OLD REVIEW LOG' not in json.dumps(edited)
    assert edited['revision_request']['findings'] == review['findings']


def test_exact_read_dedup_retains_latest_versions_windows_errors_and_pairs():
    messages = []
    for i, (text, status, offset) in enumerate([('same', 'success', 0), ('same', 'success', 0),
            ('new version', 'success', 0), ('same', 'success', 1), ('same', 'error', 0)]):
        messages.extend([AIMessage(content='', tool_calls=[call('read_current_source', {'source_id': 'S1', 'offset': offset}, str(i))]),
            ToolMessage(content=text, status=status, tool_call_id=str(i), name='read_current_source')])
    original = deepcopy(messages)
    projected = deduplicate_read_results(messages)
    assert json.loads(projected[1].content)['duplicate_of_tool_call_id'] == '1'
    assert projected[3:] == messages[3:]
    assert messages == original
    assert [m.tool_call_id for m in projected if isinstance(m, ToolMessage)] == [str(i) for i in range(5)]


@pytest.mark.parametrize('revision', [False, True])
def test_report_draft_survives_missing_title_and_repeated_local_chart_error(artifacts, revision):
    async def run():
        source_id = next(s for s, row in artifacts.read_paper('P01', 'sources').items() if row['result_state'] == 'numeric_fact')
        unit = artifacts.source_item(source_id)['unit']
        citation = 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
        prose = 'Synthetic report argument, retained exactly while format fields are repaired. ' * 5 + f'[{citation}]'
        draft = {'narrative_markdown': prose, 'charts': [{'title': 'Comparison fixture', 'unit': 'wrong',
            'interpretation': 'Same known source used in two synthetic labels.',
            'points': [{'label': label, 'source': {'source_id': source_id}} for label in ('A', 'B')]}]}
        model = NativeFixtureModel(marker='draft', replies=[
            [call('submit_case_report', {'report': draft}, 'draft')],
            [call('repair_report_fields', {'fields': {'title': 'Retained report'}}, 'title')],
            [call('repair_report_fields', {'fields': {'charts.0.unit': unit}}, 'unit')]])
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 4, 'tool_calls': 5}, report_revision=revision)
        result = await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Write a report.'}]})
        assert result['output']['narrative_markdown'] == prose
        assert result['output']['title'] == 'Retained report'
        assert citation in result['output']['citations']
        assert result['output']['charts'][0]['unit'] == unit
        errors = [m for m in result['messages'] if isinstance(m, ToolMessage) and m.status == 'error']
        assert len(errors) == 2
        assert all(json.loads(m.content)['status'] == 'draft_saved_needs_repair' for m in errors)
        assert prose not in ''.join(m.content for m in errors)
        assert '1-3 useful source-bound comparisons' not in model.contexts[0][0].content
        assert 'Not separately disclosed does not mean not achieved' not in model.contexts[0][0].content
        if revision:
            assert '修正应融入文章' in model.contexts[0][0].content
            assert 'restored explicitly in authoring_context' not in model.contexts[0][0].content
    asyncio.run(run())
