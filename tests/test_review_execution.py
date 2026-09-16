"""Native failure isolation: no paid retry, no partial acceptance, no sibling cancellation."""
import asyncio
from uuid import uuid4

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import ModelCallLimitMiddleware
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool

from sec_agent.agent_runtime.case_review_agent import CaseModelAudit, CaseReviewerState, build_case_review_graph
from sec_agent.agent_runtime.research_session_runtime import load_research_runtime_profile
from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.review_execution import ReviewExecutionControl, ReviewExecutionStopped
from sec_agent.agent_runtime.review_execution import ReviewExecutionBoundary
from sec_agent.agent_runtime.lead_issue_decision import LeadIssueDecision, decision_errors
from sec_agent.agent_runtime.workpaper_changes import paper_versions
from test_research_convergence import artifact_fixture
from test_review_inspection_recovery import recovery_decision


class AsyncReviewModel(BaseChatModel):
    actor: str
    signal: object
    control: object
    calls: object
    failure: str = 'truncated'

    @property
    def _llm_type(self):
        return 'native-failure-isolation-fixture'

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, *args, **kwargs):
        raise AssertionError('Native async path required')

    async def _agenerate(self, messages, **kwargs):
        self.calls.append(self.actor)
        if self.actor == 'counter':
            await self.signal.wait()
            if self.failure == 'provider':
                from httpx import ReadTimeout
                raise ReadTimeout('provider response unavailable')
            raw = AIMessage(content='', additional_kwargs={'reasoning_content':'PRIVATE_TRUNCATED_SENTINEL'},
                tool_calls=[{'name':'read_probe','id':'partial','args':{},'type':'tool_call'}],
                response_metadata={'finish_reason':'length'})
        else:
            self.signal.set()
            while not self.control.stopped.is_set():
                await asyncio.sleep(0)
            raw = AIMessage(content='', tool_calls=[{'name':'read_probe','id':'settled','args':{},'type':'tool_call'}],
                response_metadata={'finish_reason':'tool_calls'})
        return ChatResult(generations=[ChatGeneration(message=raw)])


@pytest.mark.parametrize('failure', ['truncated', 'provider'])
def test_native_review_failure_drains_paid_sibling_and_blocks_new_dispatch(failure):
    async def exercise():
        profile, _ = load_research_runtime_profile('.')
        control, signal, calls, settled, effects, events = ReviewExecutionControl(), asyncio.Event(), [], [], [], []
        unknown = []
        @tool
        def read_probe():
            """A deterministic read used to distinguish executed and rejected actions."""
            effects.append('read')
            return 'observed source'
        class ReceiptGuard:
            def prepare(self, *args, **kwargs):
                return {'call_id':str(uuid4()),'status':'dispatched'}
            async def run_async(self, prior, operation, **kwargs):
                try:
                    response = await operation(prior)
                except BaseException:
                    unknown.append(prior['call_id'])
                    raise
                settled.append(prior['call_id'])
                return response
        reviewers = {}
        for role in ('counter','verifier'):
            node=profile['nodes'][role]
            audit=CaseModelAudit(actor=role, profile=DeepSeekModelProfile.model_validate(node['profile']),
                basis=TokenBudgetBasis.model_validate_json(__import__('json').dumps(node['budget'])),
                public_sink=events.append, private_sink=lambda e:None, dispatch_guard=ReceiptGuard())
            audit.review_execution_control=control
            reviewers[role]=create_agent(model=AsyncReviewModel(actor=role,signal=signal,control=control,calls=calls,failure=failure),
                tools=[read_probe],state_schema=CaseReviewerState,middleware=[ModelCallLimitMiddleware(run_limit=10), *audit.middlewares()])
            reviewers[role].output_channels = [*reviewers[role].output_channels, 'thread_model_call_count']
        graph=build_case_review_graph(reviewers=reviewers,artifacts=artifact_fixture(),question='Synthetic scope',
            run_id='run',run_invocation_id='inv').compile()
        result=await asyncio.wait_for(graph.ainvoke({'run_id':'run','run_invocation_id':'inv'}),timeout=10)
        assert len(settled)==(2 if failure=='truncated' else 1) and sorted(calls)==['counter','verifier']
        assert len(unknown)==(0 if failure=='truncated' else 1)
        assert all(result[role]['model_calls']==1 for role in reviewers)
        assert effects==['read']  # The truncated response's apparent tool is never executed.
        assert result['phase']=='case_review_incomplete'
        assert result['counter']['execution_error']['reason']==('case_review_truncated_no_partial_acceptance'
            if failure=='truncated' else 'review_provider_failure_usage_may_be_unknown')
        assert result['verifier']['execution_error']['reason']=='review_wave_stopped_no_new_dispatch'
        assert all('recovery_state' not in result[r] and result[r]['review'] is None for r in reviewers)
        assert 'PRIVATE_TRUNCATED_SENTINEL' not in __import__('json').dumps(result)
    asyncio.run(exercise())


def test_control_preserves_terminal_reason_and_blocks_further_dispatch():
    control=ReviewExecutionControl()
    with pytest.raises(ReviewExecutionStopped):
        control.stop('known_terminal',{'messages':[HumanMessage(content='saved task')]})
    with pytest.raises(ReviewExecutionStopped,match='no_new_dispatch'):
        control.before_dispatch({'messages':[]})


@pytest.mark.parametrize('error', [RuntimeError('programming defect'), asyncio.CancelledError()])
def test_boundary_preserves_programming_errors_and_user_cancellation(error):
    async def handler(request):
        raise error
    with pytest.raises(type(error)):
        asyncio.run(ReviewExecutionBoundary().awrap_model_call(None, handler))


def test_lead_requires_existing_candidate_and_explicit_available_prerequisite():
    artifacts=artifact_fixture();versions=paper_versions(artifacts)
    decision=LeadIssueDecision.model_validate(recovery_decision(artifacts))
    assert not decision_errors(decision,{},set(versions),incomplete_reviewers=['counter'],current_versions=versions)
    assignment=decision.review_assignments[0]
    assignment.prerequisite='author_revision'
    assert any('prerequisite_unavailable' in e for e in decision_errors(decision,{},set(versions),incomplete_reviewers=['counter'],current_versions=versions))
    assignment.prerequisite='current_candidate';assignment.candidate_versions={'P01':'future-digest'}
    assert any('stale' in e for e in decision_errors(decision,{},set(versions),incomplete_reviewers=['counter'],current_versions=versions))
