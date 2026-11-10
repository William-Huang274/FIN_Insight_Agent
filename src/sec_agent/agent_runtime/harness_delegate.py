"""Configured research delegation using the same native ACP execution primitives."""
import json
import secrets
from pathlib import Path

from .conversation_agent import research_system_prompt
from .harness_acp_session import admitted_acp_session, completed_recovery, _persist
from .harness_dispatch_host import HarnessDispatchHost
from .harness_local_services import harness_local_services
from .harness_profile import profile_overlay
from .harness_provider_transport import HarnessProviderTransport


def delegation_guidance(purpose):
    if purpose not in {'investigate', 'review', 'draft'}:
        raise ValueError('consultation_purpose_invalid')
    common = ('你受主研究者委派，原始用户问题独立提供；委派重点不能改变原题范围。'
              '可以依据材料质疑委派中的假设，必要时自行补查。来源、期间、单位和引用身份保持准确。')
    if purpose == 'draft':
        return common + ('完成委派范围的调查并交回可供主研究者审核的完整草稿，附准确引用及影响主结论的未决事项。'
                         '自行选择结构，不把主研究者的暂定认识当标准答案。此草稿不会直接覆盖用户报告；主研究者负责最终审核、补证和成稿。')
    if purpose == 'review':
        return common + '核查覆盖和影响主结论的推断，给出定位、依据和具体建议动作；保留证据充分的判断。'
    return common + '调查所委派的关系，返回有依据的发现、竞争解释和对当前判断的影响。'


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

    async def __call__(self, *, key, request, bridge, previous_scope=None, **unused):
        o, budget = self.options, self.budget
        directory = self.directory / key
        run = directory / self.rid
        binding = dict(execution_id=self.tid, manifest_digest=self.grant['manifest_digest'],
                       release=self.parent_options['binary_sha256'], model=o['model'])
        if previous_scope:
            recovered = completed_recovery(directory, previous_run_id=previous_scope.split(':')[1], binding=binding)
            if recovered is not None:
                return recovered['text']
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
            provider_headers={'Authorization': 'Bearer '+self.environment[o['provider_key_env']]}, token=token)
        dispatch.wire_usage = transport.meter
        async with harness_local_services(business=bridge, dispatch=dispatch, transport=transport, token=token) as endpoint:
            prompt = research_system_prompt(bridge.tools, delegation_guidance(request['purpose']) +
                '\nResearch as of: '+request['as_of']+
                '\nUse returned citation_handle values and [REF-...] citations; never shorten source IDs.') + request['method_text']
            patch = profile_overlay(model=o['model'], protocol=o['protocol'], endpoint=endpoint, prompt=prompt,
                context_window=o['context_window'], output_tokens=o['output_tokens'], summary_tokens=o['summary_tokens'],
                reasoning=o['reasoning'], compaction_threshold=o.get('compaction_threshold', .8),
                dispatch_plugin=self.root/'integrations/deepseek-harness/dispatch.mjs',
                business_mcp={'Authorization':'Bearer '+token})
            patch_path = run/'profile.patch.json'
            _persist(patch_path, patch)
            env = {k:v for k,v in self.environment.items() if k.upper() in {
                'PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT'}}
            env.update(DSH_HOME=str(directory/'native'), HOME=str(directory), USERPROFILE=str(directory),
                       FIN_HARNESS_LOCAL_TOKEN=token, NO_PROXY='127.0.0.1,localhost')
            # Reuse the task's installed upstream packages; only conversation
            # state is isolated. Do not download/copy a package tree per child.
            shared_cache = self.directory.parent.parent/'.cache/pkg'
            if shared_cache.is_dir():
                package_link = directory/'.cache/pkg'
                package_link.parent.mkdir(parents=True, exist_ok=True)
                if not package_link.exists():
                    package_link.symlink_to(shared_cache, target_is_directory=True)
            async with admitted_acp_session(binary=str(self.binary), arguments=['--profile','sdk-minimal','--patch',str(patch_path)],
                    environment=env, directory=directory, binding=binding, run_id=self.rid,
                    authority=authority, stop=bridge.stop, mcp_servers=[], workspace=directory) as session:
                payload = {k:v for k,v in request.items() if k != 'method_text'}
                payload['readback'] = 'browse_context and read_saved_result provide inherited successful source and calculation receipts.'
                if previous_scope:
                    payload['continuation'] = 'Continue the same assignment using saved successful results; do not repeat completed work.'
                result = await session.prompt(json.dumps(payload, ensure_ascii=False))
                if result['status'] != 'completed' or not result['text'].strip():
                    raise RuntimeError('harness_delegate_not_completed')
                return result['text']
