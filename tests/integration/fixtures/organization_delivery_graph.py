"""Static report delivery fixture, never a research-quality qualification.

Initial orientation and run admission use the production organization factory.
On explicit continuation, the guarded research phase executes once, then this
fixture replaces downstream specialist/review/writer work with a labelled report
containing the exact earlier test passage. No production graph is changed.
"""
import os
from pathlib import Path
import runpy
from copy import deepcopy

if os.getenv('FIN_ORGANIZATION_DELIVERY_QUALIFICATION') != '1':
    raise RuntimeError('isolated_business_delivery_qualification_only')

fixture = runpy.run_path(str(Path(__file__).with_name('organization_native_graph.py')))
host = fixture['host']
original_builder = host.build_research_session_graph

from langgraph.graph import START, END, StateGraph
from langgraph.config import get_stream_writer
from sec_agent.agent_runtime.research_session import ResearchRequest, ResearchSessionState


def delivery_builder(*, promote_orientation=False, **phases):
    if not promote_orientation:
        return original_builder(**phases, promote_orientation=False)

    async def deliver(state, config):
        # Retain the production input guard and current Java admission checks.
        payload = ResearchRequest.model_validate({key:state[key] for key in
            ('question','case_profile','research_stage') if key in state}).model_dump(mode='json')
        result = await phases['research'].ainvoke(payload, config)
        assert result['phase'] == 'research_needs_attention', 'unexpected_scripted_research_result'
        orientation = state['research_orientation']
        passage = next(item for receipt in orientation['runtime_provenance'].values()
            for item in receipt.get('result', {}).get('items', [])
            if item.get('result_state') == 'source_bound_passage')
        assert passage['organization_source']['execution_id'] == config['configurable']['thread_id']
        source = {**deepcopy(passage), 'source_id':passage['passage_id'], 'text':passage['passage']}
        get_stream_writer()({'kind':'stage','actor':'qualification','event':'outcome',
            'objective':'Static report delivery fixture saved; financial quality not assessed.'})
        return {'phase':'ready_for_human_review','report_version':1,
            'report':{'title':'Static business delivery report',
                'narrative_markdown':'Engineering fixture only. No financial conclusion or review acceptance.\n\n'
                    + passage['passage'] + ' [C1]',
                'citations':{'C1':{'sources':[source]}},'charts':[]},
            'report_review':{'findings':[],'unresolved_data_requests':[]}}

    builder = StateGraph(ResearchSessionState, input_schema=ResearchRequest)
    builder.add_node('deliver_static_report', deliver)
    builder.add_edge(START, 'deliver_static_report')
    builder.add_edge('deliver_static_report', END)
    return builder


host.build_research_session_graph = delivery_builder
graph = host.research_session_graph
