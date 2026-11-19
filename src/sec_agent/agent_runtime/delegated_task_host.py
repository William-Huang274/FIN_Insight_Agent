"""B/D assembly for an independently admitted root; no public admission bypass.

C attaches these capabilities to the common root conversation. This function
does not create a graph, choose a workflow, or dispatch a model by itself.
"""
import asyncio
from uuid import UUID


async def admitted_delegation_tools(*, sdk, resources, run_authority, root_thread_id, root_run_id,
                                   specification, settings, environment):
    from .delegated_task_authority import OrganizationTaskAuthority
    from .delegated_task_runtime import DelegatedTaskRuntime
    from .delegated_task_tools import delegation_tools
    from .research_budget import budget_from_host
    from .working_memory import WorkingMemory
    from sec_agent.research_foundation.research_methods import get_research_method
    if environment.get('FINSIGHT_ORGANIZATION_TASK_ACTIONS_ENABLED') != '1':
        return []
    root, run = str(UUID(root_thread_id)), str(UUID(root_run_id))
    if resources.execution_id != root:
        raise ValueError('delegation_root_binding_mismatch')
    grant = await asyncio.to_thread(run_authority)
    if grant['execution_id'] != root or grant['authorized_run_id'] != run:
        raise ValueError('delegation_parent_not_independently_admitted')
    owner = 'organization:' + grant['organization_id']
    parent = await sdk.threads.get(root)
    if parent['metadata'].get('owner_id') != owner:
        raise ValueError('delegation_parent_owner_mismatch')
    budget = await asyncio.to_thread(budget_from_host, settings, thread_id=root,
                                    metadata=parent['metadata'], environment=environment)
    if budget is None:
        raise ValueError('delegation_requires_shared_root_budget')
    def check():
        if run_authority() != grant:
            raise ValueError('delegation_parent_authority_changed')
    async def async_check():
        await asyncio.to_thread(check)
    authority = OrganizationTaskAuthority(resources)
    memory = WorkingMemory(environment['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner, workspace=root,
                           actor='handoff-reader', access_check=check, allow_remote_search=False)
    def child_note(child_grant, note, version, offset):
        if child_grant['execution_id'] != root or child_grant['owner_id'] != owner:
            raise ValueError('delegation_readback_scope_mismatch')
        child_memory = WorkingMemory(environment['FINSIGHT_WORKING_MEMORY_PATH'], owner=owner,
            workspace=child_grant['child_thread_id'], actor='handoff-reader',
            access_check=check, allow_remote_search=False)
        return child_memory.read(note, version=version, offset=offset)
    return delegation_tools(controller=DelegatedTaskRuntime(sdk=sdk, authority=authority),
        parent_thread_id=root, parent_run_id=run, root_budget_id=budget.budget,
        manifest_digest=resources.manifest_digest,
        allowed_methods=[m['method_id'] for m in get_research_method()['methods']],
        note_reader=lambda note, version: memory.read(note, version=version), child_note_reader=child_note,
        access_check=async_check, runtime_configuration=specification)
