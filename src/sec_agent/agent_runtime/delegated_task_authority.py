"""Task-specific workload admission; does not borrow a parent's run grant."""
import asyncio
import json


class OrganizationTaskAuthority:
    def __init__(self, resources):
        self.resources = resources

    def _request(self, operation, body):
        return self.resources.request(
            f'/v1/runtime/organization-executions/{self.resources.execution_id}/task-commands/{operation}', body)

    async def claim(self, command, fixed_input):
        from langchain_core.tools import ToolException
        body = {'command': command, 'fixed_input': fixed_input}
        if len(json.dumps(body, separators=(',', ':')).encode()) > 65536:
            raise ToolException('交接目录超过命令大小上限，尚未派发；请选择本子任务需要的材料入口，正文按需读取。')
        return await asyncio.to_thread(self._request, 'claim', body)

    def lookup(self, child, command=None, run=None, receipt=None, operation='read'):
        return self._request(operation, {'manifest_digest': self.resources.manifest_digest,
            'child_thread_id': child, 'command_id': command, 'run_id': run, 'receipt': receipt})

    async def read(self, child):
        return await asyncio.to_thread(self.lookup, child)

    async def command(self, child, command):
        return await asyncio.to_thread(self.lookup, child, command)

    async def catalog(self):
        return await asyncio.to_thread(self._request, 'catalog', {'manifest_digest': self.resources.manifest_digest})

    async def check(self, grant, *, read_only=False):
        current = await asyncio.to_thread(self.lookup, grant['child_thread_id'], grant['command_id'])
        if (current['binding'] != grant['binding'] or current['operation_id'] != grant['operation_id']
                or current['owner_id'] != grant['owner_id']):
            raise ValueError('delegated_command_authority_changed')
        if not read_only and current.get('cancel_requested') and grant['action'] != 'cancel':
            raise ValueError('delegated_task_cancelled')

    async def accept(self, grant, receipt):
        return await asyncio.to_thread(self.lookup, grant['child_thread_id'], grant['command_id'],
                                       receipt=receipt, operation='accept')

    def admit(self, child, command, run):
        return self.lookup(child, command, run, operation='admit')
