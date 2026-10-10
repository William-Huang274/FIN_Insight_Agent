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


@pytest.mark.parametrize('options', [
    {'role': 'lead_writer'}, {'role': 'writer'},
    {'role': 'lead_writer', 'report_revision': True},
    {'role': 'lead_writer', 'allow_answers': True},
])
def test_report_writing_method_reaches_native_initial_and_revision_requests(artifacts, options):
    from sec_agent.research_foundation.research_methods import research_writing_guidance

    async def run():
        citation = 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
        report = {'title': 'Synthetic submission for prompt delivery',
            'narrative_markdown': 'Existing source-bound analysis remains available. ' * 8 + f'[{citation}]'}
        model = NativeFixtureModel(marker='writing-method-delivery', replies=[
            [call('submit_case_report', {'report': report}, 'write')]])
        agent = build_case_output_agent(model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 2, 'tool_calls': 2}, **options)
        result = await agent.ainvoke({'request_action': 'revise',
            'messages': [{'role': 'user', 'content': 'Answer the original research question.'}]})
        system = model.contexts[0][0].content
        assert research_writing_guidance('report') in system
        assert research_writing_guidance('workpaper') not in system
        assert result['output']['narrative_markdown'] == report['narrative_markdown']
        assert citation in result['output']['citations']
    asyncio.run(run())


def test_uncited_originals_remain_available_without_promoting_author_prose(artifacts):
    paper = artifacts._papers['P01']['workpaper']
    all_ids = set(artifacts.read_paper('P01', 'sources'))
    paper['claims'] = []  # Deliberately no author-selected evidence in this view.
    assert research_handoff(artifacts, 'P01')['source_count'] == 0
    view = research_handoff(artifacts, 'P01', include_uncited=True, limit=12)
    assert {row['source_id'] for row in view['source_catalog']} == all_ids
    assert all(not row['citation_ids'] for row in view['source_materials'])
    assert paper['thesis'] not in json.dumps(view, ensure_ascii=False)


def test_completed_assignment_is_readable_but_never_injected_as_current_task(artifacts):
    from sec_agent.agent_runtime.report_authoring import historical_assignment, author_overview
    assignment = {'task_id': 'old-task', 'objective': 'HISTORICAL_DIRECTIVE_ONLY',
                  'success_criteria': ['OLD_ACCEPTANCE_RUBRIC']}
    artifacts._papers['P01']['task_context']['assignment'] = deepcopy(assignment)
    before = deepcopy(artifacts._papers)
    fresh = report_authoring_input('CURRENT_USER_QUESTION', artifacts)
    handoff = research_handoff(artifacts, 'P01', limit=1)
    overview = author_overview(artifacts, 'P01')
    wire = json.dumps([fresh, handoff, overview])
    assert 'CURRENT_USER_QUESTION' in wire
    assert 'HISTORICAL_DIRECTIVE_ONLY' not in wire and 'OLD_ACCEPTANCE_RUBRIC' not in wire
    assert 'research_question' not in handoff
    assert handoff['view'] == 'source_materials.v4'
    entry = fresh['catalog']['papers'][0]
    assert entry['topic'] == assignment['task_id']
    assert entry['historical_assignment']['arguments']['section'] == 'assignment'
    assert historical_assignment(artifacts, 'P01')['assignment'] == assignment
    assert artifacts._papers == before
    artifacts._papers['P01']['task_context']['assignment']['topic_title'] = 'Deployment and demand'
    assert authoring_catalog(artifacts)['papers'][0]['topic'] == 'Deployment and demand'


def test_viewpoint_selection_preserves_author_reasoning_sources_and_conditions(artifacts):
    from sec_agent.agent_runtime.report_authoring import author_overview
    paper = artifacts.read_paper('P01')
    overview = author_overview(artifacts, 'P01')
    assert overview['thesis'] == paper['thesis']
    assert 'claims' not in overview and 'mechanism' not in overview
    assert {c['claim_id'] for c in overview['viewpoints']} == {c['claim_id'] for c in paper['claims']}
    chosen = paper['claims'][-1]['claim_id']
    full = author_analysis(artifacts, 'P01')
    subset = author_analysis(artifacts, 'P01', claim_ids=[chosen], fields=['counterevidence', 'what_would_change'])
    assert subset['claims'] == [c for c in full['claims'] if c['citation_id'] == f'P01:{chosen}']
    assert subset['counterevidence'] == paper['counterevidence']
    assert subset['what_would_change'] == paper['what_would_change']
    assert 'mechanism' not in subset and 'open_gaps' not in subset
    assert artifacts.read_paper('P01') == paper
    with pytest.raises(ValueError, match='unknown_claim_ids'):
        author_analysis(artifacts, 'P01', claim_ids=['UNKNOWN'])
    with pytest.raises(ValueError, match='unknown_analysis_fields'):
        author_analysis(artifacts, 'P01', fields=['unknown'])


def test_native_readers_route_historical_assignment_and_selected_analysis(artifacts):
    async def run():
        from sec_agent.agent_runtime.report_authoring import author_overview, historical_assignment
        claim = artifacts.read_paper('P01')['claims'][0]['claim_id']
        requests = [
            {'paper_id': 'P01', 'section': 'overview'},
            {'paper_id': 'P01', 'section': 'analysis', 'analysis_fields': ['mechanism']},
            {'paper_id': 'P01', 'section': 'analysis', 'claim_ids': [claim]},
            {'paper_id': 'P01', 'section': 'assignment'}]
        model = NativeFixtureModel(marker='selected-readers', replies=[
            [call('read_current_workpaper', args, str(i))] for i, args in enumerate(requests)])
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 5, 'tool_calls': 5})
        async for value in agent.astream({'messages': [{'role': 'user', 'content': 'Inspect selected viewpoints.'}]}, stream_mode='values'):
            results = [m for m in value['messages'] if isinstance(m, ToolMessage)]
            if len(results) == 4:
                assert all(m.status == 'success' for m in results)
                actual = [json.loads(m.content) for m in results]
                assert actual == [author_overview(artifacts, 'P01'),
                    author_analysis(artifacts, 'P01', fields=['mechanism']),
                    author_analysis(artifacts, 'P01', claim_ids=[claim]), historical_assignment(artifacts, 'P01')]
                system = model.contexts[0][0].content
                assert '过去专家的任务书只用于了解分工' in system
                assert '无法精确测算也不自动否定所有判断' in system
                break
    asyncio.run(run())


def test_optional_topic_title_keeps_historical_task_serialization_unchanged():
    from sec_agent.agent_runtime.research_contracts import ResearchTaskSpec
    from sec_agent.agent_runtime.lead_research_graph import DelegatedResearchTask
    body = dict(task_id='T1', owner_role='analyst', objective='Research the original user question',
        dependency_ids=[], coverage_obligation_ids=['Q2_DEMAND_QUALITY'], success_criteria=['Answer the question'],
        requested_capability_refs=['capability:research:source-document-read'], required_authority_refs=[],
        expected_output_kinds=['branch_notebook'], materiality='high', status='planned')
    for cls in (ResearchTaskSpec, DelegatedResearchTask):
        old = cls.model_validate_json(json.dumps(body))
        assert old.model_dump(mode='json') == body
        titled = cls.model_validate_json(json.dumps({**body, 'topic_title': 'Demand and deployment'}))
        assert titled.model_dump(mode='json') == {**body, 'topic_title': 'Demand and deployment'}


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
            delivered = json.dumps(sources[ref], ensure_ascii=False)
            for q in ([quotes] if isinstance(quotes, str) else quotes):
                assert q in delivered or q in json.dumps(sources[ref].get('reading_context', {}).get('unlocated_quotes', []), ensure_ascii=False)
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
    # Synthetic quotes deliberately do not occur in the original fixture.
    # Keep them as unlocated anchors, never silently present them as verified.
    assert source['reading_context']['unlocated_quotes'].count('Subject A expects, subject to approval, up to 5 GW in 2028.') == 1
    assert 'The facility was not operational at that date.' in source['reading_context']['unlocated_quotes']
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


def test_chart_feedback_locates_all_failed_points_and_preserves_report(artifacts):
    async def run():
        source_id = next(s for s, row in artifacts.read_paper('P01', 'sources').items()
                         if row['result_state'] == 'numeric_fact')
        citation = 'P01:' + artifacts.read_paper('P01')['claims'][0]['claim_id']
        prose = 'Retain the full report while repairing only identified source bindings. ' * 5 + f'[{citation}]'
        chart = {'title': 'Comparison fixture', 'unit': artifacts.source_item(source_id)['unit'],
            'interpretation': 'Synthetic labels share a known source, without a financial comparison.',
            'points': [{'label': label, 'source': {'source_id': source_id}} for label in ('A', 'B')]}
        charts = [deepcopy(chart), deepcopy(chart)]
        charts[0]['points'][1]['source']['source_id'] = 'P01:unknown-first'
        charts[1]['points'][0]['source']['source_id'] = 'P01:unknown-second'
        draft = {'title': 'Report with isolated chart repairs', 'narrative_markdown': prose, 'charts': charts}
        model = NativeFixtureModel(marker='point-feedback', replies=[
            [call('submit_case_report', {'report': draft}, 'draft')],
            [call('repair_report_fields', {'fields': {
                'charts.0.points.1.source.source_id': source_id,
                'charts.1.points.0.source.source_id': source_id}}, 'repair')]])
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 3, 'tool_calls': 3})
        result = await agent.ainvoke({'messages': [{'role': 'user', 'content': 'Write a report.'}]})
        errors = [m for m in result['messages'] if isinstance(m, ToolMessage) and m.status == 'error']
        assert len(errors) == 1
        body = json.loads(errors[0].content)
        assert body['status'] == 'draft_saved_needs_repair'
        assert [e['path'] for e in body['errors']] == ['charts.0.points.1.source', 'charts.1.points.0.source']
        assert [e['source_id'] for e in body['errors']] == ['P01:unknown-first', 'P01:unknown-second']
        assert result['output']['narrative_markdown'] == prose
        assert len(result['output']['charts']) == 2
        assert citation in result['output']['citations']
        assert draft['charts'][0]['points'][1]['source']['source_id'] == 'P01:unknown-first'
    asyncio.run(run())


@pytest.mark.parametrize('invalid_first', [False, True])
def test_field_repair_rebinds_current_report_charts_without_resending_prose(artifacts, invalid_first):
    from test_report_synthesis_agent import saved_calculation_chart

    async def run():
        report, chart, _ = saved_calculation_chart(artifacts)
        before = deepcopy(report)
        fields = {'charts.0.scale_divisor': 1, 'charts.0.title': 'Corrected display scale',
                  'charts.0.points.0.series': 'Current source scope'}
        replies = []
        if invalid_first:
            replies.append([call('repair_report_fields', {'fields': {
                'charts.0.scale_divisor': 7, 'charts.0.title': 'Corrected display scale'}}, 'bad')])
            del fields['charts.0.title']  # The second patch must retain the saved candidate's title.
        replies.append([call('repair_report_fields', {'fields': fields}, 'fixed')])
        model = NativeFixtureModel(marker='current-chart-repair', replies=replies)
        agent = build_case_output_agent(role='lead_writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 3, 'tool_calls': 3}, report_revision=True)
        result = await agent.ainvoke({'request_action': 'revise', 'report': report,
            'messages': [{'role': 'user', 'content': 'Correct the chart fields, retaining the current report.'}]})
        accepted = result['output']
        assert accepted['narrative_markdown'] == before['narrative_markdown']
        assert accepted['title'] == before['title']
        assert accepted['charts'][0]['title'] == 'Corrected display scale'
        assert accepted['charts'][0]['points'][0]['series'] == 'Current source scope'
        assert accepted['charts'][0]['points'][0]['value'] == before['charts'][0]['points'][0]['value'] * 1000
        assert accepted['charts'][0]['points'][0]['source_id'] == before['charts'][0]['points'][0]['source_id']
        assert report == before
        errors = [m for m in result['messages'] if isinstance(m, ToolMessage) and m.status == 'error']
        assert len(errors) == int(invalid_first)
        if invalid_first:
            assert json.loads(errors[0].content)['status'] == 'draft_saved_needs_repair'
        assert all('submit_case_report' != t['name'] for r in replies for t in r)

    asyncio.run(run())


def test_chart_prose_id_alone_gets_actionable_feedback_without_requiring_s2(artifacts):
    from sec_agent.research_foundation.report_charts import ReportChart, ReportChartBindingError, bind_report_charts
    source_id = next(s for s in artifacts.read_paper('P01', 'sources')
        if artifacts.source_item(s)['result_state'] in {'reviewed_evidence', 'source_bound_passage'})
    chart = ReportChart(title='Source paragraph example', unit='USD', interpretation='Exercise source ID semantics only.',
        points=[{'label': label, 'source': {'source_id': source_id}} for label in ('A', 'B')])
    with pytest.raises(ReportChartBindingError) as failure:
        bind_report_charts([chart], artifacts.source_item)
    assert len(failure.value.issues) == 2
    assert failure.value.issues[1]['path'] == 'charts.0.points.1.source'
    assert all('prose_chart_point_requires_literal_and_exact_quote' in e['message'] for e in failure.value.issues)
