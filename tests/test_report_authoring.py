import asyncio
from copy import deepcopy
import json
import pytest

from langchain_core.messages import AIMessage, ToolMessage

from test_case_review_agent import artifacts, call
from test_report_synthesis_agent import NativeFixtureModel
from sec_agent.agent_runtime.report_authoring import authoring_catalog, research_handoff, author_analysis, report_authoring_input, citation_index
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent, report_citations
from sec_agent.agent_runtime.model_context import deduplicate_read_results


def test_handoff_reads_sources_while_analysis_preserves_every_author_claim(artifacts):
    paper = artifacts.read_paper('P01')
    before = deepcopy(paper)
    view = research_handoff(artifacts, 'P01')
    analysis = author_analysis(artifacts, 'P01')
    rows = {c['citation_id']: c for c in analysis['claims']}
    sources = {r['source_id']: r for r in view['source_materials']}
    assert set(sources) == {s for c in paper['claims'] for s in c['source_ids']}
    for claim in paper['claims']:
        row = rows['P01:' + claim['claim_id']]
        assert row['statement'] == claim['statement']
        assert row.get('authority_note') == claim.get('authority_note')
        assert row['source_ids'] == claim['source_ids']
        report_citations('[' + row['citation_id'] + ']', artifacts)
        for ref in claim['source_ids']:
            assert row['citation_id'] in sources[ref]['citation_ids']
            quotes = claim['citation_quotes'].get(ref, [])
            assert all(q in sources[ref]['quotes'] for q in ([quotes] if isinstance(quotes, str) else quotes))
    assert analysis['open_gaps'] == paper['open_gaps']
    assert analysis['counterevidence'] == paper['counterevidence']
    assert not {'thesis', 'mechanism', 'facts', 'claims', 'interpretations', 'limitations'} & set(view)
    for ref, row in sources.items():
        source = artifacts.source_item(ref)
        for key in ('value_decimal', 'unit', 'period_start', 'period_end', 'authority_note', 'numeric_fact_authority'):
            if key in source:
                assert row['source'][key] == source[key]
        assert row['readback']['arguments']['source_id'] == ref
    assert artifacts.read_paper('P01') == before
    catalog = authoring_catalog(artifacts)
    assert 'semantic_review_required' not in json.dumps(catalog)
    assert 'NOT a verified report' not in json.dumps(catalog)
    assert view['version'] == catalog['papers'][0]['version']


def test_mixed_author_fact_and_counterargument_do_not_override_original_evidence(artifacts):
    paper = artifacts.read_paper('P01')
    source_id = next(s for s in artifacts.read_paper('P01', 'sources')
        if artifacts.source_item(s)['result_state'] in {'reviewed_evidence', 'source_bound_passage'})
    paper['thesis'] = 'OLD_AUTHOR_THESIS'
    paper['claims'][0].update(kind='reported_fact', statement='MIXED_AUTHOR_JUDGMENT',
        authority_note='AUTHOR_CONDITION_REQUIRES_ANALYSIS', source_ids=[source_id],
        citation_quotes={source_id: ['Subject A expects, subject to approval, up to 5 GW in 2028.']})
    counter = deepcopy(paper['claims'][0])
    counter.update(claim_id='COUNTER_ONLY', kind='inference', statement='AUTHOR_COUNTERARGUMENT')
    counter['citation_quotes'][source_id].append('The facility was not operational at that date.')
    paper['claims'].append(counter)
    current = artifacts.with_revisions({'P01': {'status': 'revision_submitted', 'workpaper': paper}})
    view = research_handoff(current, 'P01')
    body = json.dumps(view)
    assert all(s not in body for s in ('OLD_AUTHOR_THESIS', 'MIXED_AUTHOR_JUDGMENT', 'AUTHOR_COUNTERARGUMENT', 'AUTHOR_CONDITION_REQUIRES_ANALYSIS'))
    source = next(s for s in view['source_materials'] if s['source_id'] == source_id)
    assert source['quotes'].count('Subject A expects, subject to approval, up to 5 GW in 2028.') == 1
    assert 'The facility was not operational at that date.' in source['quotes']
    assert 'P01:COUNTER_ONLY' in source['citation_ids']
    analysis = json.dumps(author_analysis(current, 'P01'))
    assert all(s in analysis for s in ('OLD_AUTHOR_THESIS', 'MIXED_AUTHOR_JUDGMENT', 'AUTHOR_COUNTERARGUMENT', 'AUTHOR_CONDITION_REQUIRES_ANALYSIS'))


def test_analysis_is_opt_in_through_native_tool_and_editorial_changes_are_visible(artifacts):
    async def run():
        current = artifacts.with_human_edits([{'number': 1, 'reason': 'User revised the synthesis',
            'papers': [{'paper_id': 'P01', 'after': 'CURRENT_USER_PROSE'}]}])
        model = NativeFixtureModel(marker='evidence-then-analysis', replies=[
            [call('read_current_workpaper', {'paper_id': 'P01'}, 'material')],
            [call('read_current_workpaper', {'paper_id': 'P01', 'section': 'analysis'}, 'analysis')]])
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=current,
            limits={'model_calls': 3, 'tool_calls': 4})
        async for value in agent.astream({'messages': [{'role': 'user', 'content': 'Read materials and optional author analysis.'}]}, stream_mode='values'):
            found = [m for m in value['messages'] if isinstance(m, ToolMessage)]
            if len(found) == 2:
                material, analysis = [json.loads(m.content) for m in found]
                assert 'CURRENT_USER_PROSE' not in found[0].content
                assert material['human_editorial_revision']['number'] == 1
                assert material['current_editorial_prose']['arguments']['section'] == 'analysis'
                assert analysis['current_narrative_markdown'] == 'CURRENT_USER_PROSE'
                assert analysis == author_analysis(current, 'P01')
                break
    asyncio.run(run())


def test_source_read_failure_is_visible_not_replaced_by_author_statement(artifacts, monkeypatch):
    paper = artifacts.read_paper('P01')
    target = paper['claims'][0]['source_ids'][0]
    original = artifacts.source_item
    def read(ref):
        if ref == target:
            raise ValueError('synthetic_source_unavailable')
        return original(ref)
    monkeypatch.setattr(artifacts, 'source_item', read)
    row = next(s for s in research_handoff(artifacts, 'P01')['source_materials'] if s['source_id'] == target)
    assert row['source_read_error'] == 'synthetic_source_unavailable'
    assert 'source' not in row
    assert row['readback']['arguments']['source_id'] == target


def test_citation_directory_reads_ids_then_only_requested_full_claim(artifacts):
    async def run():
        original = artifacts.read_paper('P01')
        index = citation_index(artifacts, 'P01')
        assert index['version'] == research_handoff(artifacts, 'P01')['version']
        assert [c['claim_id'] for c in index['citations']] == [c['claim_id'] for c in original['claims']]
        for preview, full in zip(index['citations'], original['claims']):
            assert preview['statement_preview'] == full['statement'][:160]
        chosen = original['claims'][0]['claim_id']
        model = NativeFixtureModel(marker='citation-index', replies=[
            [call('read_current_workpaper', {'paper_id': 'P01', 'section': 'citations'}, 'index')],
            [call('read_current_workpaper', {'paper_id': 'P01', 'section': 'claims', 'claim_ids': [chosen]}, 'claim')]])
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 3, 'tool_calls': 4})
        # Only consume through the second read; this is an interface test, not authoring.
        async for value in agent.astream({'messages': [{'role': 'user', 'content': 'Read the citation index and one full claim.'}]}, stream_mode='values'):
            found = [m for m in value['messages'] if isinstance(m, ToolMessage)]
            if len(found) == 2:
                assert json.loads(found[0].content) == index
                assert json.loads(found[1].content) == [original['claims'][0]]
                break
    asyncio.run(run())


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
