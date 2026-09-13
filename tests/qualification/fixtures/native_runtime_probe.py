"""Synthetic native-server graph. Never imports FIN research or provider tools."""
import asyncio
import json
import os
import time
from pathlib import Path
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class ProbeState(TypedDict, total=False):
    label: str
    delay_seconds: float
    require_review: bool
    prepared: bool
    completed: bool
    reviewed: bool
    worker: str
    guard_budget: str
    guard_owner: str
    guard_mode: str


def _event(state, phase):
    # Test evidence only; never used to schedule, lock, or resume work.
    path = Path('/probe-evidence') / f'{os.environ["HOSTNAME"]}.jsonl'
    with path.open('a', encoding='utf-8') as stream:
        stream.write(json.dumps({'label': state['label'], 'phase': phase,
                                 'worker': os.environ['HOSTNAME'], 'at': time.time()}) + '\n')
        stream.flush()
        os.fsync(stream.fileno())


async def prepare(state: ProbeState):
    _event(state, 'prepared')
    return {'prepared': True, 'worker': os.environ['HOSTNAME']}


async def simulate_work(state: ProbeState):
    delay = float(state.get('delay_seconds', 0))
    if not 0 <= delay <= 90:
        raise ValueError('probe_delay_out_of_bounds')
    _event(state, 'work_started')
    if state.get('guard_budget'):
        import sys
        if '/probe' not in sys.path:
            sys.path.insert(0, '/probe')
        from model_dispatch_probe import invoke_model
        await invoke_model(state, _event)
        return {'completed': True, 'worker': os.environ['HOSTNAME']}
    await asyncio.sleep(delay)
    _event(state, 'work_finished')
    return {'completed': True, 'worker': os.environ['HOSTNAME']}


async def review(state: ProbeState):
    if state.get('require_review'):
        accepted = interrupt({'label': state['label'], 'question': 'Accept synthetic result?'})
        if accepted is not True:
            raise ValueError('probe_review_not_accepted')
    return {'reviewed': True}


builder = StateGraph(ProbeState)
builder.add_node('prepare', prepare)
builder.add_node('simulate_work', simulate_work)
builder.add_node('review', review)
builder.add_edge(START, 'prepare')
builder.add_edge('prepare', 'simulate_work')
builder.add_edge('simulate_work', 'review')
builder.add_edge('review', END)
graph = builder.compile()
