"""Same-batch persistence/acceptance contracts, not financial qualification."""
import asyncio
from copy import deepcopy

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from mcp import Client

from sec_agent.agent_runtime.case_review_agent import (
    CaseReview, build_case_reviewer, case_mcp_tools, self_contained_review_batch,
)
from sec_agent.agent_runtime.workpaper_changes import paper_versions
from test_case_review_agent import ScriptedNativeChat, call, review_fixture
from test_research_convergence import artifact_fixture
from test_research_mcp import _build_server
from test_review_inspection_recovery import reads


def finding(artifacts):
    claim = artifacts.read_paper('P01')['claims'][0]
    return {'finding_id': 'new', 'paper_id': 'P01', 'claim_ids': [claim['claim_id']],
        'severity': 'material', 'problematic_quote': claim['statement'],
        'diagnosis': 'Synthetic issue requiring author disposition.',
        'requested_change': 'Review the synthetic issue; not a financial verdict.',
        'source_checks': [{'source_id': 'P01:S002', 'quote': '29800'}]}


@pytest.mark.parametrize('reverse', [False, True])
@pytest.mark.parametrize('mode', ['identical', 'missing', 'conflict', 'invalid_source', 'save_only', 'unconfirmed'])
def test_native_batch_keeps_saved_changes_without_premature_acceptance(reverse, mode):
    async def exercise():
        artifacts = artifact_fixture()
        saved = finding(artifacts)
        inline = deepcopy(saved)
        if mode == 'conflict':
            inline['diagnosis'] = 'Different proposed diagnosis must not overwrite sibling save.'
        if mode == 'invalid_source':
            saved['source_checks'][0]['quote'] = 'not present in the original source'
            inline = deepcopy(saved)
        review = {**review_fixture(artifacts), 'completion': 'complete',
            'findings': [] if mode == 'missing' else [inline]}
        if mode == 'unconfirmed':
            review['assessments'] = [a for a in review['assessments'] if a['paper_id'] == 'P01']
        batch = [call('record_case_finding', {'finding': saved}, 'save')]
        if mode != 'save_only':
            batch.append(call('submit_case_review', {'review': review}, 'submit'))
        if reverse:
            batch.reverse()
        # A previous version cannot make a missing concurrent update acceptable.
        old = {**saved, 'diagnosis': 'Previously saved diagnosis.'}
        async with Client(_build_server(case_artifacts=artifacts)) as client:
            agent = build_case_reviewer(role='verifier', artifacts=artifacts,
                tools=await case_mcp_tools(client), max_model_calls=1,
                confirmation=({'paper_version_digests': paper_versions(artifacts),
                    'findings_to_confirm': {'P01': [{'finding_id': 'earlier', 'paper_id': 'P01'}]}}
                    if mode == 'unconfirmed' else None),
                model=ScriptedNativeChat(marker='same-batch', replies=[batch]))
            async for state in agent.astream({'messages': [HumanMessage(content='Review fixture.'), *reads(artifacts)],
                    'recorded_findings': {'new': old} if mode == 'missing' else {}}, stream_mode='values'):
                receipts = {m.tool_call_id: m for m in state['messages'] if isinstance(m, ToolMessage)}
                if {c['id'] for c in batch} <= receipts.keys():
                    break
        assert bool(state.get('review')) == (mode == 'identical')
        if mode == 'invalid_source':
            assert not state.get('recorded_findings')
        else:
            assert receipts['save'].status == 'success'
            assert state['recorded_findings']['new']['diagnosis'] == saved['diagnosis']
        if mode in ('missing', 'conflict'):
            assert receipts['submit'].status == 'error'
            assert 'same_batch_review_not_self_contained' in receipts['submit'].content
        if mode == 'unconfirmed':
            assert receipts['submit'].status == 'error'
        if mode == 'identical':
            assert receipts['submit'].status == 'success'
            assert state['review']['findings'] == [state['recorded_findings']['new']]
            assert state['review']['findings'][0]['severity'] == 'material'
            assert state['review']['findings'][0]['source_checks'][0]['quote'] == '29800'
        # No host rewrite of the original proposal, including rejected versions.
        emitted = next(m for m in state['messages'] if isinstance(m, AIMessage))
        assert emitted.tool_calls == batch
    asyncio.run(exercise())


@pytest.mark.parametrize('mode', ['duplicate_record', 'double_submit', 'malformed', 'withdrawn'])
def test_unsafe_batch_is_not_treated_as_independent(mode):
    artifacts = artifact_fixture()
    value = finding(artifacts)
    review = CaseReview.model_validate({**review_fixture(artifacts), 'findings': [value]})
    records = [call('record_case_finding', {'finding': value}, 'save')]
    if mode == 'duplicate_record':
        records.append(call('record_case_finding', {'finding': value}, 'duplicate'))
    elif mode == 'double_submit':
        records.extend([call('submit_case_review', {}, 's1'), call('submit_case_review', {}, 's2')])
    elif mode == 'malformed':
        records[0]['args'] = {'finding': '{broken'}
    else:
        review.withdrawn_finding_reasons = {'new': 'Cannot concurrently withdraw and save.'}
    with pytest.raises(ValueError):
        self_contained_review_batch(AIMessage(content='', tool_calls=records), review)
