"""One summary policy for the main conversation and delegated native work."""
import json
import os
from types import SimpleNamespace
from pydantic import SecretStr


def summary_middleware(specification, *, public, private, access_check, budget_scope):
    from .model_context import RequestSummaryMiddleware
    from .deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
    from .case_review_agent import CaseModelAudit, case_chat_model
    spec = specification['summary']
    profile = DeepSeekModelProfile.model_validate(spec['profile'])
    basis = TokenBudgetBasis.model_validate_json(json.dumps(spec['budget']))
    audit = CaseModelAudit(actor='conversation_summary', profile=profile, basis=basis,
        public_sink=public, private_sink=private, source_access_check=access_check,
        dispatch_guard=budget_scope.guard('context_summary', profile) if budget_scope else None)
    audit.working_note_context = lambda: ''
    policy = specification.get('context_editing', {}).get('policy', 'legacy_window')
    model = case_chat_model(profile, basis, SimpleNamespace(base_url='https://api.deepseek.com'),
        SecretStr(os.environ['DEEPSEEK_API_KEY']),
        # The middleware already selected and projected this bounded prefix.
        # At SDK serialization preserve the same lossless policy, without a
        # second navigation retirement or legacy release_history pass.
        context_editing={'policy': policy, 'trigger_tokens': None} if policy == 'continuous_surface' else None)
    return RequestSummaryMiddleware(model=model, audited_model=audit.model_runnable(model),
        trigger_tokens=spec['trigger_tokens'], keep_tokens=spec['keep_tokens'], max_summaries=2,
        per_user_turn=spec.get('per_user_turn', False),
        context_policy=policy,
        segment_tokens=spec.get('segment_tokens', 32000),
        segment_characters=spec.get('segment_characters', 120000),
        target_tokens=spec.get('target_tokens', 2000),
        audited_model_factory=lambda tools: audit.model_runnable(model, tools=tools),
        navigation_trigger_tokens=specification.get('context_editing', {}).get('trigger_tokens'))
