"""Read-only, bounded follow-up over a frozen human-completed research state.

Runs the production report agent and tools in a separate SQLite checkpoint.
Never updates the source product thread; responses remain private artifacts.
"""
import argparse
import asyncio
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace

from langchain_core.messages import HumanMessage
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from pydantic import SecretStr

from sec_agent.agent_runtime.deepseek_structured_agents import DeepSeekModelProfile, TokenBudgetBasis
from sec_agent.agent_runtime.dell_case_convergence_agent import build_case_output_agent
from sec_agent.agent_runtime.dell_case_review_agent import CaseModelAudit, case_chat_model
from sec_agent.agent_runtime.dell_report_session import session_audit_sinks
from sec_agent.agent_runtime.research_session import current_task_artifacts


async def run(args):
    args.output.mkdir(parents=True, exist_ok=False)
    source_bytes = args.source_state.read_bytes()
    source = json.loads(source_bytes)
    state = source.get('values', source)
    if state.get('phase') != 'human_completed' or not state.get('human_edits'):
        raise ValueError('requires_frozen_human_completed_state')
    artifacts = current_task_artifacts(state)
    profile = DeepSeekModelProfile(model='deepseek-v4-flash', thinking='enabled', reasoning_effort='low')
    basis = TokenBudgetBasis(node_role='specialist', node_purpose='Report follow-up: verify human-edited HPE conclusions survive and conflicting new wording is checked against sources',
        input_scale='One frozen completed report, two corrected working papers, source receipts read on demand; two short questions',
        required_outputs=('Concise source-bound answer using current human edits', 'Explain source conflicts instead of inventing evidence or restoring withdrawn conclusions'),
        schema_burden='Existing report agent read tools and one answer submission; no new full workpaper/report',
        materiality_quality_risk='Stale original claims and human prose must not be promoted to source facts',
        comparable_run_evidence='208 zero-model native graph reproduced and repaired stale read_current_workpaper after human completion; original207 report immutable',
        reasoning_profile='agentic_message_history_thinking_enabled', max_input_characters=180000,
        max_output_tokens=6000, timeout_seconds=180, max_transport_attempts=1, retry_policy='none',
        truncation_stop_behavior='fail_closed_no_partial_promotion', input_ceiling_behavior='fail_before_transport')
    questions = [
        '请依据当前人工修订后的底稿和报告，简短说明HPE收入增长为什么不能直接当成有机增长，以及现金流分析应保留哪些口径区别。先读取当前底稿，按需核对来源，不重新研究整家公司。',
        '我想把结论直接改成“收入增长已经证明盈利质量改善，收购并表收入就是有机增长”。请核对当前底稿和原始依据，告诉我是否可以这样改；如果与依据冲突请具体指出，不要直接替换报告。']
    manifest = {'source_sha256': sha256(source_bytes).hexdigest(), 'report_version': state['report_version'],
        'human_edit_count': len(state['human_edits']), 'questions': questions, 'profile': profile.model_dump(mode='json'),
        'budget': basis.model_dump(mode='json'), 'max_calls_per_question': 6, 'max_tools_per_question': 8,
        'source_thread_mutations': 0, 'qualification': 'development, not blind; production report-agent tools, isolated checkpoint'}
    (args.output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    if not args.execute:
        print('Prepared; zero model calls.'); return
    from scripts.qualification.dell_q1_specialist_paid_shadow.run_once import _dotenv
    key = SecretStr(_dotenv()['DEEPSEEK_API_KEY'])
    results = []
    for index, question in enumerate(questions):
        folder = args.output/str(index+1); folder.mkdir()
        public, private = session_audit_sinks(folder)
        audit = CaseModelAudit(actor='human-followup', profile=profile, basis=basis, public_sink=public, private_sink=private)
        model = case_chat_model(profile, basis, SimpleNamespace(base_url='https://api.deepseek.com'), key)
        agent = build_case_output_agent(role='writer', model=model, tools=[], artifacts=artifacts,
            limits={'model_calls': 6, 'tool_calls': 8}, allow_answers=True, answer_only=True, audit=audit)
        async with AsyncSqliteSaver.from_conn_string(str(args.output/'checkpoint.sqlite')) as saver:
            # Production agent is already compiled; the saver belongs to this
            # qualification wrapper, preserving each step without source mutation.
            from langgraph.graph import StateGraph, START, END
            from sec_agent.agent_runtime.dell_case_convergence_agent import CaseOutputState
            wrapper = StateGraph(CaseOutputState).add_node('answer', agent).add_edge(START, 'answer').add_edge('answer', END).compile(checkpointer=saver)
            result = await wrapper.ainvoke({'messages': [HumanMessage(content=question)], 'output': None,
                'report': state['report'], 'revisions': state.get('revisions', {}), 'human_edits': state['human_edits'],
                'conversation': [], 'request_action': 'ask'}, {'configurable': {'thread_id': 'human-followup'}, 'recursion_limit': 100})
        output = result.get('output')
        (folder/'result.private.json').write_text(json.dumps(result, ensure_ascii=False, default=lambda x:x.model_dump(mode='json')), encoding='utf-8')
        events = [e for e in audit.events if e.get('event') == 'outcome']
        results.append({'question': index+1, 'submitted': bool(output), 'output': output,
            'model_requests': sum(e.get('event') == 'started' for e in audit.events),
            'known_tokens': sum(e.get('total_tokens') or 0 for e in events),
            'content_review': 'pending_human_reading'})
        (args.output/'results.private.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps({k:v for k,v in results[-1].items() if k!='output'}, ensure_ascii=False), flush=True)
        if not output: break
    assert args.source_state.read_bytes() == source_bytes


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-state', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception as exc:
        if args.output.exists():
            import traceback
            (args.output/'failure.private.json').write_text(json.dumps({'error_type':type(exc).__name__,
                'traceback':traceback.format_exc(), 'retry':'none; inspect saved audit and checkpoint before any new attempt'}, ensure_ascii=False), encoding='utf-8')
        raise
