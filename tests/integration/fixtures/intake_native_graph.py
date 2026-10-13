"""Deterministic research-shaped graph: real queue/checkpoints, no model adapter.

Only the isolated qualification compose registers this as research_session.
Never import the production research graph or a provider SDK here.
"""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

if os.environ.get('FIN_INTAKE_NATIVE_QUALIFICATION') != '1':
    raise RuntimeError('isolated_native_qualification_only')


class State(TypedDict, total=False):
    question: str
    prepared: bool
    phase: str
    research_failed_workpapers: list
    report: dict
    report_version: int
    report_review: dict
    execution_seen: dict


def record(config, phase):
    values = config['configurable']
    tid = str(values['thread_id'])
    rid = str(values.get('run_id') or config.get('metadata', {}).get('run_id'))
    if rid == 'None':
        raise RuntimeError('native_run_identity_missing')
    evidence = Path(os.environ['FIN_PROBE_EVIDENCE'])
    with (evidence / 'graph-events.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps({'thread_id': tid, 'run_id': rid, 'phase': phase,
            'at': time.time(), 'execution': values.get('finsight_execution'), 'provider_calls': 0}) + '\n')
        out.flush()
        os.fsync(out.fileno())
    # Explicit fixture audit: no started request, no transport, no fabricated tokens.
    folder = Path(os.environ['FIN_PROBE_AUDIT']) / tid / rid
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / 'model-call-events.jsonl').open('a', encoding='utf-8') as out:
        out.write(json.dumps({'event': 'outcome', 'call_id': 'qualification-no-provider',
            'provider_call_attempted': False, 'status': 'qualification_no_provider',
            'origin': 'deterministic_fixture'}) + '\n')
    return evidence, tid


async def prepare(state: State, config: RunnableConfig):
    record(config, 'prepared')
    return {'prepared': True}


async def work(state: State, config: RunnableConfig):
    evidence, tid = record(config, 'work_started')
    if 'slow' in state['question']:
        for _ in range(900):
            if (evidence / ('release-' + tid)).exists():
                break
            await asyncio.sleep(.1)
        else:
            raise RuntimeError('qualification_release_timeout')
    record(config, 'work_finished')
    return {'phase': 'research_needs_attention', 'research_failed_workpapers': [{'task_id': 'synthetic'}]}


async def handoff(state: State, config: RunnableConfig):
    record(config, 'handoff')
    answer = interrupt({'kind': 'research_needs_attention', 'actions': ['continue_remaining']})
    if answer != {'action': 'continue_remaining'}:
        raise ValueError('qualification_expected_explicit_continuation')
    return {'execution_seen': config['configurable']['finsight_execution']}


async def publish(state: State, config: RunnableConfig):
    record(config, 'published')
    return {'phase': 'ready_for_human_review', 'report_version': 1,
        'report': {'title': 'Synthetic lifecycle result', 'narrative_markdown': 'Engineering fixture only.', 'citations': {}},
        'report_review': {'findings': [], 'unresolved_data_requests': []}}


async def human_review(state: State, config: RunnableConfig):
    record(config, 'human_review')
    interrupt({'kind': 'dell_report_review'})
    return {}


builder = StateGraph(State)
for name, node in [('prepare', prepare), ('work', work), ('handoff', handoff), ('publish', publish), ('human_review', human_review)]:
    builder.add_node(name, node)
builder.add_edge(START, 'prepare')
builder.add_edge('prepare', 'work')
builder.add_edge('work', 'handoff')
builder.add_edge('handoff', 'publish')
builder.add_edge('publish', 'human_review')
builder.add_edge('human_review', END)
graph = builder.compile()
