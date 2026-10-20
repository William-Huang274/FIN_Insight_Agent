"""Static output producers inside the real organization/HITL graph.

The production Java admission, real ReviewAction node, native checkpoints and
report version rules execute unchanged. This does not qualify financial answers,
specialist revision planning or the quality of independent review.
"""
import json
import os
from pathlib import Path
import runpy
from copy import deepcopy

if os.getenv('FIN_ORGANIZATION_REPORT_ACTIONS_QUALIFICATION') != '1':
    raise RuntimeError('isolated_report_actions_qualification_only')
fixture = runpy.run_path(str(Path(__file__).with_name('organization_native_graph.py')))
host = fixture['host']
original_builder = host.build_research_session_graph

from langchain_core.runnables import RunnableLambda
from langgraph.config import get_config
from langgraph.graph import START
from sec_agent.agent_runtime.report_session import build_report_session_graph
from sec_agent.agent_runtime.research_session import ResearchRequest, ResearchSessionState
from sec_agent.agent_runtime.case_artifacts import CaseArtifacts


def interaction_builder(*, promote_orientation=False, review_action_check=None, **phases):
    config = get_config()['configurable']
    if not promote_orientation and not config.get('finsight_organization_report_action'):
        return original_builder(**phases, promote_orientation=promote_orientation, review_action_check=review_action_check)
    artifacts = CaseArtifacts.from_observed_sources({}, case_id='static-organization-actions',
        research_as_of=config['finsight_research_as_of'])
    def produce(value, *, reviewer=False):
        # Production runtime already admitted this exact run. Each producer
        # emits a known-zero fixture audit, never a synthetic token estimate.
        current = get_config()['configurable']
        settings = json.loads(Path(os.environ['FINSIGHT_REPORT_SESSION_SETTINGS']).read_text())
        public, _ = host.session_audit_sinks(Path(settings['audit_root']) / current['thread_id'] / current['run_id'])
        public({'event': 'outcome', 'call_id': f"static-action:{current['run_id']}:{reviewer}",
            'provider_call_attempted': False, 'status': 'qualification_no_provider', 'origin': 'deterministic_fixture'})
        if reviewer:
            output = {'findings': [], 'unresolved_data_requests': [], 'summary': 'Static review only, no financial certification.'}
        elif value['request_action'] == 'ask':
            message = json.loads(value['messages'][0].content)['user_message']
            output = {'kind': 'answer', 'answer_markdown': 'Static answer: ' + message, 'citations': value['report']['citations']}
        else:
            output = deepcopy(value['report'])
            output['narrative_markdown'] += '\n\nStatic explicit revision; not a financial conclusion.'
        return {'output': output}
    writer = RunnableLambda(produce)
    graph = build_report_session_graph(writer=writer, quick_writer=writer,
        verifier=RunnableLambda(lambda value: produce(value, reviewer=True)),
        artifacts=artifacts, initial={}, state_schema=ResearchSessionState, input_schema=ResearchRequest,
        start_at_initialize=False, review_action_check=review_action_check)
    async def deliver(state, config):
        payload = ResearchRequest.model_validate({k: state[k] for k in ('question', 'case_profile', 'research_stage') if k in state}).model_dump(mode='json')
        result = await phases['research'].ainvoke(payload, config)
        assert result['phase'] == 'research_needs_attention'
        passages = [p for receipt in state['research_orientation']['runtime_provenance'].values()
                    for p in receipt.get('result', {}).get('items', []) if p.get('result_state') == 'source_bound_passage']
        assert passages
        citations = {f'C{i}': {'claim': {'statement': p['passage']},
            'sources': [{**deepcopy(p), 'source_id': p['passage_id'], 'text': p['passage']}]}
            for i, p in enumerate(passages, 1)}
        return {'initialized': True, 'phase': 'ready_for_human_review', 'report_version': 1,
            'report': {'title': 'Static business delivery report',
                'narrative_markdown': 'Engineering fixture only.\n\n' + '\n\n'.join(p['passage'] + f' [C{i}]' for i, p in enumerate(passages, 1)),
                'citations': citations, 'charts': []},
            'report_review': {'findings': [], 'unresolved_data_requests': []}, 'revisions': {}, 'conversation': []}
    graph.add_node('deliver_static_report', deliver)
    graph.add_edge(START, 'deliver_static_report')
    graph.add_edge('deliver_static_report', 'human_review')
    return graph


host.build_research_session_graph = interaction_builder
graph = host.research_session_graph
