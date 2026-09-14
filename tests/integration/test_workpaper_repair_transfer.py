"""Saved public-source development paper through native review/repair tools.

All decisions and revisions are host-authored fixtures, not model-quality proof.
No provider, source download or hidden evaluation data is used.
"""
import asyncio
from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path

from langchain_core.messages import HumanMessage, ToolMessage, messages_to_dict
from mcp import Client
import pytest

from sec_agent.agent_runtime.case_artifacts import CaseArtifacts, revision_review_target
from sec_agent.agent_runtime.case_review_agent import build_case_reviewer, build_case_review_graph, case_mcp_tools
from sec_agent.agent_runtime.report_synthesis_agent import build_case_output_agent, paper_revision_input
from sec_agent.agent_runtime.research_session import responsible_author_feedback
from test_case_review_agent import ScriptedNativeChat, call
from test_report_synthesis_agent import NativeFixtureModel
from test_research_mcp import _build_server

ROOT = Path(__file__).resolve().parents[2]
SEED = ROOT / '.local/fin014/20260914_e3_amzn_transfer_a1/specialist_result.json'


def correction_fixture(artifacts):
    paper = artifacts.read_paper('P01')
    claim = deepcopy(next(c for c in paper['claims'] if c['claim_id'] == 'C6'))
    source1, source2 = (artifacts.source_item(ref)['passage'] for ref in ('P01:S001', 'P01:S002'))
    sales = next(line for line in source1.splitlines() if 'Worldwide (WW) net sales' in line and '167,702' in line)
    income = next(line for line in source2.splitlines() if 'Operating income' in line and '19,171' in line)
    claim['source_ids'] = ['P01:S001', 'P01:S002']
    claim['citation_quotes'] = {'P01:S001': [sales], 'P01:S002': [income, *[
        q for q in claim['citation_quotes']['P01:S002'] if 'Net sales |' in q or 'Operating income |' in q]]}
    findings = {
        'verifier': {'finding_id': 'citation-coverage', 'claim_ids': ['C6'],
            'problematic_quote': next(c for c in paper['claims'] if c['claim_id'] == 'C6')['statement'],
            'diagnosis': 'C6公司销售增速所在0:5虽已读取，主张未绑定对应原文；字符串匹配不等于全部分句有据。',
            'requested_change': '补充公司销售与营业利润增速的准确行引用，保留原值与其余正确核算。',
            'source_checks': [{'source_id': 'P01:S001', 'quote': sales}, {'source_id': 'P01:S002', 'quote': income}]},
        'counter': {'finding_id': 'hypothesis-strength', 'claim_ids': [],
            'problematic_quote': paper['counterevidence'][-1],
            'diagnosis': '现有材料不足以断定阶段性而非结构性，公司技术费用也不是AWS成本分配证明。',
            'requested_change': '保留有条件的投入假设、替代解释及观察信号，移除已确定阶段性的表述，并澄清公司费用口径。',
            'source_checks': []}}
    for finding in findings.values():
        finding.update(paper_id='P01', severity='material')
    revision = {k: deepcopy(paper[k]) for k in ('thesis', 'mechanism', 'narrative_markdown',
                                              'counterevidence', 'what_would_change', 'open_gaps')}
    revision.update(paper_id='P01', claim_updates=[claim], removed_claim_ids=[])
    revision['counterevidence'][-1] = ('AWS营业费用增速高于收入增速；投入前置是待核实假设，价格、业务组合和持续性成本压力也是替代解释。'
        '现有材料不能确定阶段性或结构性，需分部成本/折旧归因及后续收入和利润率变化检验。')
    qualifier = '该费用是公司整体口径，不能未经分配直接解释AWS；投入前置仅是假设，需与价格、组合及持续性成本压力比较。'
    revision['narrative_markdown'] = revision['narrative_markdown'].replace(
        '27,166百万美元，+22%）。', '27,166百万美元，+22%）。' + qualifier)
    assert qualifier in revision['narrative_markdown']
    return findings, revision


@pytest.mark.local_data_integration
def test_saved_amzn_native_review_responsible_repair_and_scoped_readback(tmp_path):
    original_bytes = SEED.read_bytes()
    artifacts = CaseArtifacts([json.loads(original_bytes)])
    original = artifacts.read_paper('P01')
    findings, revision = correction_fixture(artifacts)
    output = Path(os.environ.get('FIN_REPAIR_QUALIFICATION_OUTPUT', str(tmp_path)))
    output.mkdir(parents=True, exist_ok=True)
    def save(name, value):
        (output / (name+'.json')).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')

    async def exercise():
        async with Client(_build_server(case_artifacts=artifacts), raise_exceptions=False) as client:
            tools = await case_mcp_tools(client)
            reviewers = {}
            for role, finding in findings.items():
                review = {'summary': '宿主脚本化复核交接资格，仅测试已知问题传递，不代表模型自主发现或整稿金融验收。',
                    'assessments': [{'paper_id': 'P01', 'assessment': '脚本化检查完整底稿的传输及指定问题交接，保留其他语义问题。'}],
                    'findings': [finding], 'completion': 'complete', 'unresolved_data_requests': []}
                replies = [[call('read_research_artifact', {'paper_id': 'P01'}, 'paper')],
                    [call('read_research_source', {'source_id': ref, 'max_characters': 8000}, ref) for ref in ('P01:S001', 'P01:S002')],
                    [call('submit_case_review', {'review': review}, 'submit')]]
                reviewers[role] = build_case_reviewer(role=role, artifacts=artifacts, tools=tools,
                    model=ScriptedNativeChat(marker=role, replies=replies), max_model_calls=5)
            graph = build_case_review_graph(reviewers=reviewers, artifacts=artifacts, question='019保存原稿本地责任交接资格',
                run_id='local-repair', run_invocation_id='local-repair').compile()
            reviewed = await graph.ainvoke({'run_id': 'local-repair', 'run_invocation_id': 'local-repair'})
            feedback = responsible_author_feedback(reviewed, artifacts)['P01']
            assert {f['finding_id'] for f in feedback} == {'counter:hypothesis-strength', 'verifier:citation-coverage'}
            save('native_review', reviewed)
            revision['finding_responses'] = [{'finding_id': f['finding_id'], 'disposition': 'corrected',
                'explanation': '宿主按原件编写有限修订，原生提交校验通过只证明传输及绑定，不代表模型纠错质量。'} for f in feedback]
            bad = deepcopy(revision)
            bad['claim_updates'][0]['citation_quotes']['P01:S001'] = ['Invented source quote must be rejected.']
            model = NativeFixtureModel(marker='repair', replies=[
                [call('read_current_source', {'source_id': ref, 'max_characters': 8000}, ref) for ref in ('P01:S001', 'P01:S002')],
                [call('submit_paper_revision', {'revision': bad}, 'bad')],
                [call('submit_paper_revision', {'revision': revision}, 'fixed')]])
            author = build_case_output_agent(role='repair', model=model, tools=tools, artifacts=artifacts,
                feedback=feedback, paper_id='P01', limits={'model_calls': 5, 'tool_calls': 8})
            repaired = await author.ainvoke({'messages': [HumanMessage(content=json.dumps(
                paper_revision_input(artifacts, 'P01', feedback), ensure_ascii=False))]})
            errors = [m for m in repaired['messages'] if isinstance(m, ToolMessage) and m.status == 'error']
            assert len(errors) == 1 and 'source_quote_not_exact' in errors[0].content
            assert 'counterevidence' in model.contexts[0][0].content and 'combined claim' in model.contexts[0][0].content
            saved = repaired['output']
            current = artifacts.with_revisions({'P01': saved})
            changed = current.read_paper('P01')
            assert [c for c in original['claims'] if c['claim_id'] != 'C6'] == [c for c in changed['claims'] if c['claim_id'] != 'C6']
            assert '属阶段性而非结构性' not in json.dumps(changed, ensure_ascii=False)
            assert current.source_item('P01:S004') == artifacts.source_item('P01:S004')
            assert current.source_item('P01:S005') == artifacts.source_item('P01:S005')
            assert artifacts.read_paper('P01') == original and SEED.read_bytes() == original_bytes
            target = revision_review_target(artifacts, 'P01', saved)
            assert target['changed_claim_ids'] == ['C6']
            pending = '本次仅检查C6和改变的解释文字；C9组合贡献与C10产品级未披露边界仍需独立检查，不能接受为整稿通过。'
            review = {'summary': '指定修改已通过宿主本地链路检查；整稿语义接受保持开放。',
                'assessments': [{'paper_id': 'P01', 'assessment': pending}], 'findings': [],
                'completion': 'incomplete', 'unresolved_data_requests': [pending]}
            scoped = build_case_reviewer(role='verifier', artifacts=current, tools=tools, revision_target=target,
                model=ScriptedNativeChat(marker='scoped', replies=[[call('read_review_target', {}, 'target')],
                    [call('read_research_source', {'source_id': 'P01:S001', 'max_characters': 8000}, 'source')],
                    [call('submit_case_review', {'review': review}, 'submit')]]), max_model_calls=5)
            checked = await scoped.ainvoke({'messages': [HumanMessage(content='仅复核修订范围，并保留必要的未完成检查。')]})
            assert checked['review']['completion'] == 'incomplete'
            assert checked['review']['review_scope']['kind'] == 'revision_only'
            save('native_repair_messages', messages_to_dict(repaired['messages']))
            save('revision', saved)
            save('revision_review', checked['review'])
            save('scope', target)
            save('qualification', {'provider_calls': 0, 'source_sha256': hashlib.sha256(original_bytes).hexdigest(),
                'changed_claims': ['C6'], 'unchanged_claim_count': 9, 'preserved_calculations': 2,
                'nature': 'host-authored decisions through native tools, not autonomous financial acceptance'})
            (output / 'host_corrected_workpaper.md').write_text(changed['narrative_markdown'], encoding='utf-8')
    asyncio.run(exercise())
