"""Configured research delegation using the same native ACP execution primitives."""
import json
import secrets
from pathlib import Path

from .conversation_agent import research_system_prompt
from .harness_acp_session import admitted_acp_session, completed_recovery, _persist
from .harness_dispatch_host import HarnessDispatchHost
from .harness_local_services import harness_local_services
from .harness_profile import profile_overlay
from .harness_provider_transport import HarnessProviderTransport, model_provider_proxy


def delegation_guidance(purpose):
    if purpose not in {'investigate', 'review', 'draft'}:
        raise ValueError('consultation_purpose_invalid')
    common = ('你受主研究者委派，原始用户问题独立提供；委派重点不能改变原题范围。'
              '可以依据材料质疑委派中的假设，必要时自行补查。来源、期间、单位和引用身份保持准确。'
              '在交办范围内完成问题理解、定向取证、比较或计算、条件判断与自查，不只返回搜索摘要。'
              '用 record_research_assessment 的 finding 保存实质结果，scope_explanation 说明实际覆盖，'
              'actions 只留会改变答案的未决事项；该工具仅在实际披露时可用。'
              '交回能独立读懂的结论、关键依据及回读入口、必要假设、最强反证和对总题的影响。'
              '来源仅部分读取且关键段未查时继续分页或定位；执行失败、未做调查与合理公开资料边界分别说明。')
    if purpose == 'draft':
        return common + ('完成委派范围的调查并交回可供主研究者审核的完整草稿，附准确引用及影响主结论的未决事项。'
                         '自行选择结构，不把主研究者的暂定认识当标准答案。此草稿不会直接覆盖用户报告；主研究者负责最终审核、补证和成稿。')
    if purpose == 'review':
        return common + ('核查覆盖和影响主结论的推断，给出定位、依据和具体建议动作；保留证据充分的判断。'
            '同时检查是否把尚未完成的分析变成边界声明；局部核对通过不能认证总题已回答。')
    return common + ('调查所委派的关系，返回有依据的发现、竞争解释和对当前判断的影响。'
        '明确实际取得的客户或需求方证据、竞争或替代方案证据如何检验原解释；'
        '若这些视角与问题无关或没有可得材料，说明具体原因，不机械凑齐来源类别。'
        '可支持的正面发现与仍未解决的关系一起返回，不只交风险清单。'
        '否定一种极端推断后，继续说明可支持的幅度、时间或条件判断；不虚构参数，'
        '有依据的范围可参与分析，敏感性不冒充预测。说明为何更倾向当前解释，或还缺哪项有区分力的观察。')


def delegation_payload(request, *, previous_scope=None, recovery_receipt=None):
    """Project a frozen assignment, not its redundant evidence snapshots.

    The persisted request/digest and inherited canonical tool results stay intact.
    Native recovery already restores the assignment and history; appending them
    again doubles large reports on every interruption.
    """
    from .research_graph_contracts import canonical_sha256
    from .source_references import reference_handle
    report = request.get('report')
    if previous_scope:
        payload = {'continuation': 'Continue the same assignment using saved successful results; do not repeat completed work.',
                   'purpose': request['purpose'], 'question': request['question'],
                   'as_of': request['as_of']}
    else:
        payload = {k: v for k, v in request.items() if k != 'method_text'}
        if report:
            citations, source_catalog = {}, {}
            for source_id, citation in report.get('citations', {}).items():
                citations[source_id] = {
                    'citation_handle': reference_handle(source_id),
                    'readback': {'tool': 'read_research_source', 'arguments': {'source_id': source_id}},
                    'claim': {k: v for k, v in (citation.get('claim') or {}).items()
                              if k in {'kind', 'statement', 'numeric_authority'}},
                    'source_refs': [],
                }
                for source in citation.get('sources', []):
                    entry = {k: v for k, v in source.items() if k in {
                        'source_id', 'title', 'source_url', 'publication_date', 'publication_date_status',
                        'period', 'unit', 'revision', 'source_role', 'numeric_fact_authority',
                    }}
                    # Exact metadata deduplication only: distinct revisions or
                    # units never share a catalog identity.
                    identity = canonical_sha256(entry)
                    source_catalog[identity] = entry
                    if identity not in citations[source_id]['source_refs']:
                        citations[source_id]['source_refs'].append(identity)
            payload['report'] = {**report, 'citations': citations}
            payload['source_catalog'] = source_catalog
            payload['citation_notice'] = ('Citation entries are navigation, not full evidence. '
                'Read the exact inherited original with the supplied readback; original snapshots remain saved.')
        task = payload.get('research_task')
        if task and task.get('observations'):
            from .research_actions import compact_action_view
            observations = task['observations']
            payload['research_task'] = {**task, 'observations': {**observations,
                'prior_actions': compact_action_view(observations.get('prior_actions', {}))}}
    if report:
        payload['reviewed_report_digest'] = canonical_sha256(report)
    payload['readback'] = 'browse_context and read_saved_result provide inherited successful source and calculation receipts.'
    if recovery_receipt:
        payload['runtime_recovery'] = recovery_receipt
    return payload


class NativeResearchDelegate:
    """No provider loop, duplicate history, artifact writer or independent permission grant."""
    def __init__(self, *, options, parent_options, binary, root, grant, authority, budget,
                 environment, tid, rid, directory, public_sink):
        self.options, self.parent_options = options, parent_options
        self.binary, self.root, self.grant, self.authority = binary, root, grant, authority
        self.budget, self.environment, self.tid, self.rid = budget, environment, tid, rid
        self.directory, self.public_sink = Path(directory), public_sink
        if (options['protocol'] != 'deepseek_messages' or options['model'] != 'deepseek-flash'
                or options['reasoning'] != 'high' or options['model'] not in budget.prices
                or not environment.get(options['provider_key_env'])):
            raise ValueError('native_delegate_provider_not_admitted')

    def completed_result(self, key, previous_scope):
        """Only a bound, terminal native delivery can bypass another model turn."""
        thread, run = previous_scope.split(':', 1)
        if thread != self.tid:
            raise ValueError('consultation_recovery_execution_mismatch')
        binding = dict(execution_id=self.tid, manifest_digest=self.grant['manifest_digest'],
                       release=self.parent_options['binary_sha256'], model=self.options['model'])
        result = completed_recovery(self.directory/key, previous_run_id=run, binding=binding)
        return result if result and result.get('text', '').strip() else None

    async def __call__(self, *, key, request, bridge, previous_scope=None, recovery_receipt=None, **unused):
        o, budget = self.options, self.budget
        directory = self.directory / key
        run = directory / self.rid
        if previous_scope:
            recovered = self.completed_result(key, previous_scope)
            if recovered is not None:
                return recovered['text']
        binding = dict(execution_id=self.tid, manifest_digest=self.grant['manifest_digest'],
                       release=self.parent_options['binary_sha256'], model=o['model'])
        token = secrets.token_urlsafe(32)
        def authority():
            bridge.model_access()
            return self.authority()
        dispatch = HarnessDispatchHost(store=budget.store, owner=budget.owner, budget=budget.budget,
            execution_id=self.tid, run_id=self.rid, manifest_digest=self.grant['manifest_digest'],
            authority=authority, prices=budget.prices[o['model']], provider=o['provider'],
            basis=o['token_budget_basis'], reservation_micros=o['reservation_micros'],
            reservation_basis=o['reservation_basis'], receipts=run/'wire', wire_usage=lambda _: None,
            public_sink=self.public_sink, dispatch_lane='consult:'+key)
        transport = HarnessProviderTransport(dispatch, protocol=o['protocol'], endpoint=o['provider_endpoint'],
            provider_headers={'Authorization': 'Bearer '+self.environment[o['provider_key_env']]}, token=token,
            proxy=model_provider_proxy(self.environment, o['protocol']))
        dispatch.wire_usage = transport.meter
        async with harness_local_services(business=bridge, dispatch=dispatch, transport=transport, token=token) as endpoint:
            prompt = research_system_prompt(bridge.tools, delegation_guidance(request['purpose']) +
                '\nResearch as of: '+request['as_of']+
                '\nUse returned citation_handle values and [REF-...] citations; never shorten source IDs.') + request['method_text']
            if request.get('assessment_contract') == 1:
                prompt += ('\n返回成果前使用 record_research_assessment 保存原题覆盖依据及尚影响主结论的执行事项。'
                           '没有实质缺口可记录空 actions，说明依据；不要为填表制造问题。')
            patch = profile_overlay(model=o['model'], protocol=o['protocol'], endpoint=endpoint, prompt=prompt,
                context_window=o['context_window'], output_tokens=o['output_tokens'], summary_tokens=o['summary_tokens'],
                reasoning=o['reasoning'], compaction_threshold=o.get('compaction_threshold', .8),
                dispatch_plugin=self.root/'integrations/deepseek-harness/dispatch.mjs',
                business_mcp={'Authorization':'Bearer '+token})
            patch_path = run/'profile.patch.json'
            _persist(patch_path, patch)
            from .harness_storage import process_environment
            env = process_environment(self.environment, directory, token)
            # Reuse the task's installed upstream packages; only conversation
            # state is isolated. Do not download/copy a package tree per child.
            shared_cache = self.directory.parent.parent/'.cache/pkg'
            if not self.environment.get('FINSIGHT_HARNESS_NATIVE_STORAGE_ROOT') and shared_cache.is_dir():
                package_link = directory/'.cache/pkg'
                package_link.parent.mkdir(parents=True, exist_ok=True)
                if not package_link.exists():
                    package_link.symlink_to(shared_cache, target_is_directory=True)
            async with admitted_acp_session(binary=str(self.binary), arguments=['--profile','sdk-minimal','--patch',str(patch_path)],
                    environment=env, directory=directory, binding=binding, run_id=self.rid,
                    authority=authority, stop=bridge.stop, mcp_servers=[], workspace=directory) as session:
                payload = delegation_payload(request, previous_scope=previous_scope,
                    recovery_receipt=recovery_receipt)
                result = await session.prompt(json.dumps(payload, ensure_ascii=False))
                if result['status'] != 'completed' or not result['text'].strip():
                    raise RuntimeError('harness_delegate_not_completed')
                return result['text']
