"""Identical market evidence with different paging is not a new source."""
from copy import deepcopy

from langchain_core.messages import ToolMessage
import pytest

from sec_agent.agent_runtime.report_synthesis_agent import observed_sources
from sec_agent.research_foundation.source_bound_calculator import source_observation_identity


def page():
    return dict(passage_id='PASSAGE::market-fixture', document_id='WEB::market-fixture',
        result_state='source_bound_passage', source_kind='market_observations',
        writer_citable=True, numeric_fact_authority=False, passage='fixture bar close 12.5',
        source_locator=dict(source_url='https://example.com/market', content_sha256='same',
            capture_receipt_digest='same-capture', captured_at='2026-11-11T10:00:00Z',
            character_start=0, character_end=22, offset=0, limit=20),
        readback=dict(tool='read_market_prices', arguments=dict(symbol='FIXTURE',
            start='2026-11-10T14:30:00+00:00', end='2026-11-10T21:00:00+00:00',
            interval='60m', include_extended_hours=False, offset=0, limit=20)))


def receipt(item, ident):
    return ToolMessage(content='read', tool_call_id=ident, name='read_market_prices',
        artifact={'operation':'read', 'items':[item]})


def test_equivalent_navigation_preserves_full_receipts():
    first = page()
    second = deepcopy(first)
    second['source_locator']['limit'] = 100
    second['readback']['arguments'].update(start='2026-11-10T14:30:00Z',
        end='2026-11-10T21:00:00Z', limit=100)
    original = deepcopy([first, second])
    assert source_observation_identity(first) == source_observation_identity(second)
    assert observed_sources([receipt(first,'a'),receipt(second,'b')])[first['passage_id']] == second
    assert [first,second] == original


@pytest.mark.parametrize('path,value', [
    (('passage',), 'changed bar'),
    (('source_locator','capture_receipt_digest'), 'different-capture'),
    (('source_locator','source_url'), 'https://example.com/other'),
    (('source_locator','offset'), 1),
    (('readback','arguments','symbol'), 'OTHER'),
    (('readback','arguments','start'), '2026-11-11T14:30:00Z'),
    (('readback','arguments','interval'), '1d'),
    (('readback','arguments','include_extended_hours'), True),
    (('readback','tool'), 'other_tool'),
])
def test_evidence_and_actual_selection_conflicts_still_stop(path,value):
    first=page();second=deepcopy(first);node=second
    for key in path[:-1]:node=node[key]
    node[path[-1]]=value
    with pytest.raises(ValueError,match='new_source_observation_conflict'):
        observed_sources([receipt(first,'a'),receipt(second,'b')])
